from __future__ import annotations

from core.paper import PaperExecutionConfig, PaperTradingEngine
from core.risk import RiskCheckRequest, RiskDecision, RiskDecisionType, RiskEngine, RiskLimits, RiskReason
from core.strategy import Signal, SignalAction


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def make_request(
    *,
    side: str = "BUY",
    ticker: str = "SBER",
    quantity: int = 10,
    price: float = 100.0,
    current_position_value: float = 0.0,
    open_positions_count: int = 0,
    portfolio_equity: float = 100_000.0,
) -> RiskCheckRequest:
    return RiskCheckRequest(
        side=side,
        ticker=ticker,
        strategy_name="test_strategy",
        quantity=quantity,
        price=price,
        current_position_value=current_position_value,
        open_positions_count=open_positions_count,
        portfolio_equity=portfolio_equity,
    )


def make_signal(
    action: SignalAction,
    price: float,
    *,
    quantity: int = 10,
    ts: str = "2026-01-01T10:00:00Z",
) -> Signal:
    return Signal(
        action=action,
        ticker="SBER",
        ts=ts,
        strategy_name="test_strategy",
        price=price,
        reason="unit-test",
        metadata={"quantity": quantity},
    )


# ──────────────────────────────────────────────────────────────
# RiskEngine unit tests
# ──────────────────────────────────────────────────────────────

def test_risk_engine_allows_valid_trade() -> None:
    engine = RiskEngine(RiskLimits(max_trade_value=5_000.0, max_open_positions=10))

    decision = engine.check(make_request(quantity=10, price=100.0))  # trade_value = 1_000

    assert decision.allowed is True
    assert decision.decision == RiskDecisionType.ALLOW
    assert decision.reasons == ()


def test_risk_engine_rejects_trade_value_limit() -> None:
    engine = RiskEngine(RiskLimits(max_trade_value=500.0))

    decision = engine.check(make_request(quantity=10, price=100.0))  # trade_value = 1_000 > 500

    assert decision.allowed is False
    assert RiskReason.MAX_TRADE_VALUE_EXCEEDED in decision.reasons


def test_risk_engine_rejects_position_value_limit() -> None:
    engine = RiskEngine(RiskLimits(max_position_value=800.0))

    # existing = 500, new trade = 600 → total = 1_100 > 800
    decision = engine.check(make_request(quantity=6, price=100.0, current_position_value=500.0))

    assert decision.allowed is False
    assert RiskReason.MAX_POSITION_VALUE_EXCEEDED in decision.reasons


def test_risk_engine_rejects_position_pct_limit() -> None:
    engine = RiskEngine(RiskLimits(max_position_pct=0.10))

    # trade_value = 10 * 100 = 1_000; equity = 5_000 → pct = 0.20 > 0.10
    decision = engine.check(make_request(quantity=10, price=100.0, portfolio_equity=5_000.0))

    assert decision.allowed is False
    assert RiskReason.MAX_POSITION_PCT_EXCEEDED in decision.reasons


def test_risk_engine_rejects_max_open_positions() -> None:
    engine = RiskEngine(RiskLimits(max_open_positions=3))

    # 3 positions already open, no existing position → new position would exceed limit
    decision = engine.check(make_request(open_positions_count=3, current_position_value=0.0))

    assert decision.allowed is False
    assert RiskReason.MAX_OPEN_POSITIONS_EXCEEDED in decision.reasons


def test_risk_engine_rejects_short_when_disabled() -> None:
    engine = RiskEngine(RiskLimits(allow_short=False))

    # SELL with no open position → short attempt
    decision = engine.check(make_request(side="SELL", current_position_value=0.0))

    assert decision.allowed is False
    assert RiskReason.SHORT_NOT_ALLOWED in decision.reasons


def test_risk_engine_allows_sell_when_position_exists() -> None:
    engine = RiskEngine(RiskLimits(allow_short=False))

    # SELL with existing position → closing a long, not shorting
    decision = engine.check(make_request(side="SELL", current_position_value=1_000.0))

    assert decision.allowed is True


# ──────────────────────────────────────────────────────────────
# PaperTradingEngine integration tests
# ──────────────────────────────────────────────────────────────

def test_paper_trading_rejects_order_when_risk_engine_rejects() -> None:
    risk_engine = RiskEngine(RiskLimits(max_trade_value=500.0))
    engine = PaperTradingEngine(
        PaperExecutionConfig(initial_cash=100_000.0, commission_rate=0.0),
        risk_engine=risk_engine,
    )

    # trade_value = 10 * 100 = 1_000 > 500 → risk rejects
    result = engine.on_signal(make_signal(SignalAction.BUY, 100.0, quantity=10))

    assert result.filled is False
    assert result.rejected is not None
    assert "MAX_TRADE_VALUE_EXCEEDED" in result.rejected.reason
    assert len(engine.trades) == 0
    assert len(engine.rejected_orders) == 1


def test_paper_trading_works_without_risk_engine() -> None:
    engine = PaperTradingEngine(PaperExecutionConfig(initial_cash=100_000.0, commission_rate=0.0))

    result = engine.on_signal(make_signal(SignalAction.BUY, 100.0, quantity=10))

    assert result.filled is True
    assert result.trade is not None
    assert len(engine.trades) == 1
