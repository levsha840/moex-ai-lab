"""ApprovedCandidatePaperEngine — Research Service -> Paper Trading bridge.

Safety invariants (enforced at both __init__ and run() time):
  1. Only StrategyCandidate with status=APPROVED_FOR_PAPER is accepted.
  2. MOEX_ENABLE_LIVE_TRADING must be false; engine blocks at construction
     if live trading is enabled.
  3. Engine never calls T-Invest API or any external service.
  4. Engine never touches real money.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.paper.engine import PaperTradingEngine as _InnerEngine
from core.paper.models import PaperExecutionConfig
from core.risk.engine import RiskEngine
from core.risk.models import RiskLimits
from core.strategy.signal import Signal, SignalAction

from trading.models import (
    ExecutionReport,
    PaperOrderRecord,
    PaperPortfolio,
    PositionSizingRule,
    RiskLimit,
    StrategyCandidate,
    StrategyCandidateStatus,
    TradeDirection,
    TradeSignal,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ApprovedCandidatePaperEngine:
    """Paper trading engine gated on StrategyCandidate approval.

    Architecture
    ------------
    This engine is a thin bridge:

      StrategyCandidate (APPROVED_FOR_PAPER)
        -> TradeSignal list
           -> PositionSizingRule.compute_lots()
              -> RiskLimit checks (drawdown stop, position size cap)
                 -> core.paper.PaperTradingEngine (inner, manages cash/positions)
                    -> PaperOrderRecord journal
                       -> ExecutionReport

    The inner core.paper.PaperTradingEngine handles per-trade execution,
    commission, slippage, and position accounting. This engine adds the
    approval gate, strategy-level risk controls, and journal/reporting.

    Parameters
    ----------
    sizing_rule:
        Determines lot count per signal.
    risk_limit:
        Strategy-level constraints (max drawdown, max position size, etc.).
    initial_equity:
        Starting paper account equity in rubles.
    journal_dir:
        Directory where per-candidate JSON journals are written.
        Created automatically if it does not exist.
    """

    def __init__(
        self,
        sizing_rule: PositionSizingRule,
        risk_limit: RiskLimit,
        initial_equity: float = 1_000_000.0,
        journal_dir: Path | str | None = None,
    ) -> None:
        from core.config.settings import TRADING_SETTINGS

        if TRADING_SETTINGS.enable_live_trading:
            raise RuntimeError(
                "SAFETY BLOCK: MOEX_ENABLE_LIVE_TRADING=true detected. "
                "ApprovedCandidatePaperEngine cannot operate while live trading is "
                "enabled. Set MOEX_ENABLE_LIVE_TRADING=false to use paper trading."
            )

        if initial_equity <= 0:
            raise ValueError("initial_equity must be > 0")

        self._sizing_rule = sizing_rule
        self._risk_limit = risk_limit
        self._initial_equity = float(initial_equity)
        self._journal_dir = Path(journal_dir) if journal_dir else Path("paper_journal")

        # Build inner risk engine from strategy-level RiskLimit
        inner_limits = RiskLimits(
            max_position_pct=min(risk_limit.max_position_pct, 1.0),
            max_open_positions=risk_limit.max_open_positions,
            allow_short=risk_limit.allow_short,
        )
        inner_config = PaperExecutionConfig(
            initial_cash=self._initial_equity,
            commission_rate=0.0005,
            allow_short=risk_limit.allow_short,
        )
        self._inner = _InnerEngine(
            config=inner_config,
            risk_engine=RiskEngine(limits=inner_limits),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(
        self,
        candidate: StrategyCandidate,
        signals: list[TradeSignal],
    ) -> ExecutionReport:
        """Execute all signals for an approved candidate; return a report.

        Parameters
        ----------
        candidate:
            Must have status=APPROVED_FOR_PAPER; raises ValueError otherwise.
        signals:
            Ordered list of trade signals to execute (oldest first).

        Returns
        -------
        ExecutionReport with full P&L accounting, drawdown, and trade journal.
        """
        self._check_candidate(candidate)
        self._check_live_trading_disabled()

        self._inner.reset()
        journal: list[PaperOrderRecord] = []
        peak_equity = self._initial_equity

        for sig in signals:
            current_equity = self._compute_equity()

            # Strategy-level drawdown stop
            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown_pct = (
                (peak_equity - current_equity) / peak_equity
                if peak_equity > 0 else 0.0
            )
            if drawdown_pct >= self._risk_limit.max_drawdown_pct:
                break

            quantity = self._sizing_rule.compute_lots(
                equity=current_equity,
                price=sig.entry_price,
            )

            inner_signal = Signal(
                action=SignalAction.BUY if sig.direction == TradeDirection.LONG else SignalAction.SELL,
                ticker=sig.instrument,
                ts=sig.ts,
                strategy_name=candidate.candidate_id,
                confidence=sig.confidence,
                reason=sig.reason,
                price=sig.entry_price,
                metadata={"quantity": quantity},
            )

            result = self._inner.on_signal(inner_signal)

            if result.filled and result.trade is not None:
                t = result.trade
                journal.append(PaperOrderRecord(
                    order_id=t.order_id,
                    signal_id=sig.signal_id,
                    instrument=sig.instrument,
                    direction=sig.direction.value,
                    quantity=t.quantity,
                    price=t.price,
                    commission=t.commission,
                    slippage=t.slippage,
                    realized_pnl=t.realized_pnl,
                    ts=str(sig.ts),
                    status="FILLED",
                ))
            elif result.rejected is not None:
                order = result.order
                journal.append(PaperOrderRecord(
                    order_id=order.order_id if order else "N/A",
                    signal_id=sig.signal_id,
                    instrument=sig.instrument,
                    direction=sig.direction.value,
                    quantity=quantity,
                    price=sig.entry_price,
                    commission=0.0,
                    slippage=0.0,
                    realized_pnl=0.0,
                    ts=str(sig.ts),
                    status="REJECTED",
                    reject_reason=result.rejected.reason,
                ))

        # Final snapshot drives metric computation
        last_ts = signals[-1].ts if signals else "N/A"
        final_snap = self._inner.snapshot(last_ts)

        trades = self._inner.trades
        wins = sum(1 for t in trades if t.realized_pnl > 0)
        losses = sum(1 for t in trades if t.realized_pnl < 0)
        close_trades = wins + losses
        win_rate = wins / close_trades if close_trades else 0.0

        peak_snap, max_dd = self._compute_peak_and_drawdown()
        max_dd_pct = max_dd / peak_snap if peak_snap > 0 else 0.0

        snapshots = self._inner.state.snapshots
        open_snaps = sum(1 for s in snapshots if len(s.positions) > 0)
        exposure_pct = open_snaps / len(snapshots) if snapshots else 0.0

        self._write_journal(candidate.candidate_id, journal)

        return ExecutionReport(
            report_id=f"exec_{uuid4().hex[:8]}",
            candidate_id=candidate.candidate_id,
            instrument=candidate.instrument,
            initial_equity=self._initial_equity,
            final_equity=final_snap.equity,
            peak_equity=peak_snap,
            realized_pnl=final_snap.realized_pnl,
            realized_pnl_pct=final_snap.realized_pnl / self._initial_equity,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            trades_count=len(trades),
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            exposure_pct=exposure_pct,
            journal=tuple(journal),
            generated_at=_utcnow_iso(),
        )

    def portfolio(self, ts: str = "now") -> PaperPortfolio:
        """Return a point-in-time portfolio snapshot from current engine state."""
        state = self._inner.state
        market_value = sum(
            p.quantity * state.last_prices.get(p.ticker, p.avg_price)
            for p in state.positions.values()
        )
        equity = state.cash + market_value
        realized_pnl = sum(p.realized_pnl for p in state.positions.values())
        open_positions = sum(1 for p in state.positions.values() if p.quantity > 0)

        snapshots = self._inner.state.snapshots
        peak_snap = max((s.equity for s in snapshots), default=self._initial_equity)
        peak_snap = max(peak_snap, equity)
        drawdown = max(0.0, peak_snap - equity)
        drawdown_pct = drawdown / peak_snap if peak_snap > 0 else 0.0

        return PaperPortfolio(
            initial_equity=self._initial_equity,
            cash=state.cash,
            market_value=market_value,
            equity=equity,
            realized_pnl=realized_pnl,
            open_positions=open_positions,
            peak_equity=peak_snap,
            current_drawdown=drawdown,
            current_drawdown_pct=drawdown_pct,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_candidate(self, candidate: StrategyCandidate) -> None:
        if candidate.status != StrategyCandidateStatus.APPROVED_FOR_PAPER:
            raise ValueError(
                f"StrategyCandidate '{candidate.candidate_id}' has status "
                f"'{candidate.status.value}'. "
                f"Only APPROVED_FOR_PAPER candidates are accepted. "
                f"Approve the candidate before submitting to paper trading."
            )

    def _check_live_trading_disabled(self) -> None:
        from core.config.settings import TRADING_SETTINGS
        if TRADING_SETTINGS.enable_live_trading:
            raise RuntimeError(
                "SAFETY BLOCK: live trading is enabled; paper engine cannot run."
            )

    def _compute_equity(self) -> float:
        state = self._inner.state
        market_value = sum(
            p.quantity * state.last_prices.get(p.ticker, p.avg_price)
            for p in state.positions.values()
        )
        return state.cash + market_value

    def _compute_peak_and_drawdown(self) -> tuple[float, float]:
        """Return (peak_equity, max_drawdown) across all snapshots."""
        peak = self._initial_equity
        max_dd = 0.0
        for snap in self._inner.state.snapshots:
            if snap.equity > peak:
                peak = snap.equity
            dd = peak - snap.equity
            if dd > max_dd:
                max_dd = dd
        return peak, max_dd

    def _write_journal(
        self,
        candidate_id: str,
        journal: list[PaperOrderRecord],
    ) -> None:
        self._journal_dir.mkdir(parents=True, exist_ok=True)
        path = self._journal_dir / f"{candidate_id}_journal.json"
        records = [
            {
                "order_id": r.order_id,
                "signal_id": r.signal_id,
                "instrument": r.instrument,
                "direction": r.direction,
                "quantity": r.quantity,
                "price": r.price,
                "commission": r.commission,
                "slippage": r.slippage,
                "realized_pnl": r.realized_pnl,
                "ts": r.ts,
                "status": r.status,
                "reject_reason": r.reject_reason,
            }
            for r in journal
        ]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)
