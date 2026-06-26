from core.features.feature_factory import FeatureFactory, FeatureFactoryConfig
from core.replay import ReplayConfig, ReplayEngine, replay


def candles():
    return [
        {"ticker": "SBER", "ts": "2026-01-01T10:02:00", "open": 102, "high": 104, "low": 101, "close": 103, "volume": 1200},
        {"ticker": "SBER", "ts": "2026-01-01T10:00:00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
        {"ticker": "SBER", "ts": "2026-01-01T10:01:00", "open": 100, "high": 103, "low": 100, "close": 102, "volume": 1100},
    ]


def test_replay_engine_sorts_and_steps():
    engine = ReplayEngine(candles())

    first = engine.step()
    second = engine.step()

    assert first is not None
    assert second is not None
    assert first.index == 0
    assert first.candle["ts"] == "2026-01-01T10:00:00"
    assert second.candle["ts"] == "2026-01-01T10:01:00"
    assert engine.state.events_emitted == 2


def test_replay_engine_run_returns_all_events():
    events = replay(candles())

    assert len(events) == 3
    assert events[-1].candle["close"] == 103


def test_replay_engine_warmup_history():
    engine = ReplayEngine(candles(), config=ReplayConfig(warmup_candles=1))

    events = engine.run()

    assert len(events[0].history) == 1
    assert len(events[1].history) == 2
    assert len(events[2].history) == 2


def test_replay_engine_integrates_feature_factory():
    factory = FeatureFactory(
        FeatureFactoryConfig(
            sma_periods=(2,),
            ema_periods=(2,),
            rsi_period=2,
            atr_period=2,
            volatility_period=2,
        )
    )
    engine = ReplayEngine(candles(), feature_builder=factory.build)

    events = engine.run()

    assert events[0].features is not None
    assert "feature_close_return_1" in events[1].features
    assert "feature_sma_2" in events[2].features


def test_replay_engine_reset():
    engine = ReplayEngine(candles())
    engine.step()
    engine.reset()

    assert engine.state.position == 0
    assert engine.state.events_emitted == 0
    assert engine.step().candle["ts"] == "2026-01-01T10:00:00"
