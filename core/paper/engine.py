"""Deterministic paper trading engine for strategy signals."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from core.paper.models import (
    PaperExecutionConfig,
    PaperExecutionResult,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperPortfolioSnapshot,
    PaperPosition,
    PaperRejectedOrder,
    PaperTrade,
)
from core.risk.engine import RiskEngine
from core.risk.models import RiskCheckRequest
from core.strategy.signal import Signal, SignalAction
from core.strategy.strategy_engine import StrategyDecision


@dataclass
class PaperTradingState:
    """Mutable state of the paper account."""

    cash: float
    positions: dict[tuple[str, str], PaperPosition] = field(default_factory=dict)
    orders: list[PaperOrder] = field(default_factory=list)
    trades: list[PaperTrade] = field(default_factory=list)
    rejected_orders: list[PaperRejectedOrder] = field(default_factory=list)
    snapshots: list[PaperPortfolioSnapshot] = field(default_factory=list)
    last_prices: dict[str, float] = field(default_factory=dict)


class PaperTradingEngine:
    """Executes BUY/SELL strategy signals against a virtual cash account.

    The engine is intentionally deterministic and side-effect free. It does not
    write to a database; persistence is a separate adapter concern. Current v1.5
    supports long-only execution by default, cash checks, fixed quantity sizing,
    commission, slippage and operation journals.
    """

    def __init__(self, config: PaperExecutionConfig | None = None, risk_engine: RiskEngine | None = None) -> None:
        self.config = config or PaperExecutionConfig()
        self.risk_engine = risk_engine
        self.state = PaperTradingState(cash=float(self.config.initial_cash))

    def reset(self) -> None:
        self.state = PaperTradingState(cash=float(self.config.initial_cash))

    @property
    def orders(self) -> tuple[PaperOrder, ...]:
        return tuple(self.state.orders)

    @property
    def trades(self) -> tuple[PaperTrade, ...]:
        return tuple(self.state.trades)

    @property
    def rejected_orders(self) -> tuple[PaperRejectedOrder, ...]:
        return tuple(self.state.rejected_orders)

    @property
    def positions(self) -> tuple[PaperPosition, ...]:
        return tuple(deepcopy(position) for position in self.state.positions.values())

    def on_decision(self, decision: StrategyDecision) -> list[PaperExecutionResult]:
        """Execute all actionable signals from one StrategyDecision."""

        results: list[PaperExecutionResult] = []
        for signal in decision.actionable_signals:
            results.append(self.on_signal(signal))
        if not results:
            self.snapshot(decision.ts)
        return results

    def on_signal(self, signal: Signal) -> PaperExecutionResult:
        """Convert one strategy signal into a virtual order and execute it."""

        if signal.action == SignalAction.HOLD:
            snapshot = self.snapshot(signal.ts)
            return PaperExecutionResult(order=None, trade=None, rejected=None, snapshot=snapshot)

        if signal.price is None:
            return self._reject_without_order(signal, "signal price is required for paper execution")

        quantity = self._resolve_quantity(signal)
        if quantity <= 0:
            return self._reject_without_order(signal, "quantity must be > 0")

        side = PaperOrderSide(signal.action.value)
        order = PaperOrder(
            order_id=self._new_id("ord"),
            strategy_name=signal.strategy_name,
            ticker=signal.ticker,
            ts=signal.ts,
            side=side,
            quantity=quantity,
            requested_price=float(signal.price),
            reason=signal.reason,
            metadata=dict(signal.metadata),
        )
        self.state.orders.append(order)
        self.state.last_prices[order.ticker] = order.requested_price

        if self.risk_engine is not None:
            risk_decision = self.risk_engine.check(self._build_risk_request(order))
            if not risk_decision.allowed:
                reason = "; ".join(r.value for r in risk_decision.reasons)
                rejected = PaperRejectedOrder(order=order, status=PaperOrderStatus.REJECTED, reason=reason)
                self.state.rejected_orders.append(rejected)
                snapshot = self.snapshot(order.ts)
                return PaperExecutionResult(order=order, trade=None, rejected=rejected, snapshot=snapshot)

        rejection_reason = self._validate_order(order)
        if rejection_reason is not None:
            rejected = PaperRejectedOrder(order=order, status=PaperOrderStatus.REJECTED, reason=rejection_reason)
            self.state.rejected_orders.append(rejected)
            snapshot = self.snapshot(order.ts)
            return PaperExecutionResult(order=order, trade=None, rejected=rejected, snapshot=snapshot)

        trade = self._fill(order)
        self.state.trades.append(trade)
        snapshot = self.snapshot(order.ts)
        return PaperExecutionResult(order=order, trade=trade, rejected=None, snapshot=snapshot)

    def snapshot(self, ts: Any) -> PaperPortfolioSnapshot:
        """Build and store a portfolio snapshot using latest known prices."""

        market_value = 0.0
        unrealized_pnl = 0.0
        realized_pnl = 0.0
        positions: list[PaperPosition] = []

        for position in self.state.positions.values():
            copied = deepcopy(position)
            positions.append(copied)
            realized_pnl += copied.realized_pnl
            mark_price = self.state.last_prices.get(copied.ticker, copied.avg_price)
            market_value += copied.quantity * mark_price
            unrealized_pnl += copied.quantity * (mark_price - copied.avg_price)

        snapshot = PaperPortfolioSnapshot(
            ts=ts,
            cash=self.state.cash,
            equity=self.state.cash + market_value,
            market_value=market_value,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            positions=tuple(positions),
        )
        self.state.snapshots.append(snapshot)
        return snapshot

    def _fill(self, order: PaperOrder) -> PaperTrade:
        execution_price = self._execution_price(order)
        gross_value = execution_price * order.quantity
        commission = self._commission(gross_value)
        slippage = abs(execution_price - order.requested_price) * order.quantity
        position_key = (order.strategy_name, order.ticker)
        position = self.state.positions.setdefault(
            position_key,
            PaperPosition(strategy_name=order.strategy_name, ticker=order.ticker),
        )

        realized_pnl = 0.0
        if order.side == PaperOrderSide.BUY:
            cash_delta = -(gross_value + commission)
            new_quantity = position.quantity + order.quantity
            position.avg_price = (
                ((position.avg_price * position.quantity) + gross_value) / new_quantity
                if new_quantity else 0.0
            )
            position.quantity = new_quantity
        else:
            close_quantity = min(order.quantity, position.quantity)
            realized_pnl = (execution_price - position.avg_price) * close_quantity - commission
            cash_delta = gross_value - commission
            position.quantity -= order.quantity
            if position.quantity <= 0:
                position.quantity = 0
                position.avg_price = 0.0
            position.realized_pnl += realized_pnl

        position.mark_status()
        self.state.cash += cash_delta
        self.state.last_prices[order.ticker] = execution_price

        return PaperTrade(
            trade_id=self._new_id("trd"),
            order_id=order.order_id,
            strategy_name=order.strategy_name,
            ticker=order.ticker,
            ts=order.ts,
            side=order.side,
            quantity=order.quantity,
            price=execution_price,
            gross_value=gross_value,
            commission=commission,
            slippage=slippage,
            cash_delta=cash_delta,
            realized_pnl=realized_pnl,
            reason=order.reason,
            metadata=dict(order.metadata),
        )

    def _validate_order(self, order: PaperOrder) -> str | None:
        execution_price = self._execution_price(order)
        gross_value = execution_price * order.quantity
        commission = self._commission(gross_value)
        position = self.state.positions.get((order.strategy_name, order.ticker))
        current_quantity = 0 if position is None else position.quantity

        if order.side == PaperOrderSide.BUY:
            required_cash = gross_value + commission
            if self.config.reject_on_insufficient_cash and required_cash > self.state.cash:
                return "insufficient cash"
            return None

        if not self.config.allow_short and order.quantity > current_quantity:
            return "insufficient position quantity"
        return None

    def _resolve_quantity(self, signal: Signal) -> int:
        raw_quantity = signal.metadata.get("quantity", self.config.default_quantity)
        return int(raw_quantity)

    def _execution_price(self, order: PaperOrder) -> float:
        slip_multiplier = self.config.slippage_bps / 10_000.0
        if order.side == PaperOrderSide.BUY:
            return order.requested_price * (1.0 + slip_multiplier)
        return order.requested_price * (1.0 - slip_multiplier)

    def _commission(self, gross_value: float) -> float:
        return max(gross_value * self.config.commission_rate, self.config.min_commission)

    def _reject_without_order(self, signal: Signal, reason: str) -> PaperExecutionResult:
        snapshot = self.snapshot(signal.ts)
        return PaperExecutionResult(order=None, trade=None, rejected=None, snapshot=snapshot)

    def _build_risk_request(self, order: PaperOrder) -> RiskCheckRequest:
        execution_price = self._execution_price(order)
        position_key = (order.strategy_name, order.ticker)
        position = self.state.positions.get(position_key)
        current_position_value = (
            position.quantity * self.state.last_prices.get(order.ticker, position.avg_price)
            if position is not None and position.quantity > 0
            else 0.0
        )
        open_positions_count = sum(1 for p in self.state.positions.values() if p.quantity > 0)
        market_value = sum(
            p.quantity * self.state.last_prices.get(p.ticker, p.avg_price)
            for p in self.state.positions.values()
        )
        return RiskCheckRequest(
            side=order.side.value,
            ticker=order.ticker,
            strategy_name=order.strategy_name,
            quantity=order.quantity,
            price=execution_price,
            current_position_value=current_position_value,
            open_positions_count=open_positions_count,
            portfolio_equity=self.state.cash + market_value,
        )

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"
