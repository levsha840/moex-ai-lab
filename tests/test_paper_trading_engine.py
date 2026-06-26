from __future__ import annotations

import pytest

from core.paper import PaperExecutionConfig, PaperOrderSide, PaperPositionStatus, PaperTradingEngine
from core.strategy import Signal, SignalAction


def make_signal(action: SignalAction, price: float, *, quantity: int = 10, ts: str = "2026-01-01T10:00:00Z") -> Signal:
    return Signal(
        action=action,
        ticker="SBER",
        ts=ts,
        strategy_name="test_strategy",
        price=price,
        reason="unit-test",
        metadata={"quantity": quantity},
    )


def test_buy_signal_creates_order_trade_position_and_snapshot() -> None:
    engine = PaperTradingEngine(
        PaperExecutionConfig(initial_cash=100_000.0, commission_rate=0.001, slippage_bps=10)
    )

    result = engine.on_signal(make_signal(SignalAction.BUY, 100.0, quantity=10))

    assert result.filled is True
    assert result.order is not None
    assert result.trade is not None
    assert result.rejected is None
    assert result.order.side == PaperOrderSide.BUY
    assert result.trade.price == pytest.approx(100.1)
    assert result.trade.gross_value == pytest.approx(1001.0)
    assert result.trade.commission == pytest.approx(1.001)
    assert result.snapshot.cash == pytest.approx(98_997.999)
    assert result.snapshot.equity == pytest.approx(99_998.999)

    position = engine.positions[0]
    assert position.quantity == 10
    assert position.avg_price == pytest.approx(100.1)
    assert position.status == PaperPositionStatus.OPEN


def test_sell_signal_closes_position_and_realizes_pnl() -> None:
    engine = PaperTradingEngine(PaperExecutionConfig(initial_cash=10_000.0, commission_rate=0.0))
    engine.on_signal(make_signal(SignalAction.BUY, 100.0, quantity=10))

    result = engine.on_signal(make_signal(SignalAction.SELL, 120.0, quantity=10, ts="2026-01-01T11:00:00Z"))

    assert result.filled is True
    assert result.trade is not None
    assert result.trade.side == PaperOrderSide.SELL
    assert result.trade.realized_pnl == pytest.approx(200.0)
    assert result.snapshot.cash == pytest.approx(10_200.0)
    assert result.snapshot.market_value == pytest.approx(0.0)
    assert result.snapshot.equity == pytest.approx(10_200.0)

    position = engine.positions[0]
    assert position.quantity == 0
    assert position.status == PaperPositionStatus.CLOSED
    assert position.realized_pnl == pytest.approx(200.0)


def test_rejects_buy_when_cash_is_insufficient() -> None:
    engine = PaperTradingEngine(PaperExecutionConfig(initial_cash=100.0, commission_rate=0.0))

    result = engine.on_signal(make_signal(SignalAction.BUY, 100.0, quantity=2))

    assert result.filled is False
    assert result.order is not None
    assert result.trade is None
    assert result.rejected is not None
    assert result.rejected.reason == "insufficient cash"
    assert result.snapshot.cash == pytest.approx(100.0)
    assert len(engine.orders) == 1
    assert len(engine.rejected_orders) == 1


def test_rejects_sell_without_position_in_long_only_mode() -> None:
    engine = PaperTradingEngine(PaperExecutionConfig(initial_cash=100_000.0, allow_short=False))

    result = engine.on_signal(make_signal(SignalAction.SELL, 100.0, quantity=1))

    assert result.filled is False
    assert result.rejected is not None
    assert result.rejected.reason == "insufficient position quantity"
    assert len(engine.trades) == 0


def test_hold_signal_only_creates_snapshot() -> None:
    engine = PaperTradingEngine(PaperExecutionConfig(initial_cash=1234.0))

    result = engine.on_signal(make_signal(SignalAction.HOLD, 100.0))

    assert result.order is None
    assert result.trade is None
    assert result.rejected is None
    assert result.snapshot.cash == pytest.approx(1234.0)
    assert result.snapshot.equity == pytest.approx(1234.0)


def test_invalid_config_is_rejected() -> None:
    with pytest.raises(ValueError, match="default_quantity"):
        PaperExecutionConfig(default_quantity=0)
