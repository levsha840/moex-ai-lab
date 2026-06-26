import pytest

from core.replay import ReplayConfig, ReplayEngine
from core.strategy import (
    BaseStrategy,
    EngineStrategyRegistry,
    Signal,
    SignalAction,
    StrategyContext,
    StrategyEngine,
    StrategyEngineConfig,
    ThresholdCloseStrategy,
)


def candles():
    return [
        {"ticker": "SBER", "ts": "2026-01-01T10:00:00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
        {"ticker": "SBER", "ts": "2026-01-01T10:01:00", "open": 100, "high": 103, "low": 100, "close": 102, "volume": 1100},
        {"ticker": "SBER", "ts": "2026-01-01T10:02:00", "open": 102, "high": 104, "low": 101, "close": 103, "volume": 1200},
    ]


class BuyOnSecondCandle(BaseStrategy):
    strategy_name = "BUY_ON_SECOND_CANDLE"

    def on_event(self, context: StrategyContext) -> Signal:
        if context.index == 1:
            return Signal(
                action=SignalAction.BUY,
                ticker=context.ticker,
                ts=context.ts,
                strategy_name=self.strategy_name,
                confidence=0.9,
                reason="index == 1",
                price=context.close,
            )
        return self.hold(context, "not second candle")


class LegacyStrategy:
    strategy_name = "LEGACY_BUY"

    def generate_signal(self, row):
        class OldSignal:
            action = "BUY"
            confidence = 0.8
            reason = "legacy adapter"

        return OldSignal()


def test_strategy_engine_runs_over_replay_events():
    replay_events = ReplayEngine(candles(), config=ReplayConfig(warmup_candles=2)).run()
    engine = StrategyEngine([BuyOnSecondCandle()])

    decisions = engine.run(replay_events)

    assert len(decisions) == 3
    assert decisions[1].signals[0].action == SignalAction.BUY
    assert decisions[1].signals[0].price == 102
    assert engine.state.events_processed == 3


def test_strategy_engine_can_suppress_hold_signals():
    replay_events = ReplayEngine(candles()).run()
    engine = StrategyEngine(
        [BuyOnSecondCandle()],
        config=StrategyEngineConfig(emit_hold=False),
    )

    decisions = engine.run(replay_events)

    assert decisions[0].signals == ()
    assert decisions[1].actionable_signals[0].action == SignalAction.BUY


def test_strategy_engine_adapts_legacy_generate_signal():
    event = ReplayEngine(candles()).step()
    engine = StrategyEngine([LegacyStrategy()])

    decision = engine.on_event(event)

    assert decision.signals[0].action == SignalAction.BUY
    assert decision.signals[0].strategy_name == "LEGACY_BUY"
    assert decision.signals[0].metadata["adapter"] == "legacy_generate_signal"


def test_threshold_close_strategy_generates_actions():
    replay_events = ReplayEngine(candles()).run()
    engine = StrategyEngine([ThresholdCloseStrategy(buy_above=103, sell_below=100)])

    decisions = engine.run(replay_events)

    assert decisions[0].signals[0].action == SignalAction.SELL
    assert decisions[1].signals[0].action == SignalAction.HOLD
    assert decisions[2].signals[0].action == SignalAction.BUY


def test_registry_registers_and_rejects_duplicates():
    registry = EngineStrategyRegistry()
    strategy = BuyOnSecondCandle()

    registry.register(strategy)

    assert registry.names() == ["BUY_ON_SECOND_CANDLE"]
    assert registry.get("BUY_ON_SECOND_CANDLE") is strategy
    with pytest.raises(ValueError):
        registry.register(strategy)


def test_signal_validates_confidence():
    with pytest.raises(ValueError):
        Signal(
            action=SignalAction.BUY,
            ticker="SBER",
            ts="2026-01-01T10:00:00",
            strategy_name="BAD",
            confidence=2.0,
        )
