"""Tests for experiments/generic — GenericFeatureProvider, GenericStrategyRunner,
GenericRegimeProvider, and all 8 thin hypothesis factories."""
from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from core.walkforward.models import WalkForwardConfig, WalkForwardWindow
from experiments.generic.dataset import GenericOHLCVDataset
from experiments.generic.providers import (
    GenericFeatureProvider,
    GenericProviderFactory,
    GenericRegimeProvider,
    GenericStrategyRunner,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _candles(n: int = 120, start: float = 100.0, step: float = 0.5) -> list[dict]:
    closes = [start + i * step for i in range(n)]
    return [{"open": c - 0.1, "high": c + 1.0, "low": c - 1.0, "close": c} for c in closes]


def _flat_candles(n: int = 120, price: float = 100.0) -> list[dict]:
    return [{"open": price, "high": price + 0.5, "low": price - 0.5, "close": price} for _ in range(n)]


def _build_features(candles=None, n=120):
    if candles is None:
        candles = _candles(n)
    fp = GenericFeatureProvider(candles)
    return fp.build_features(MagicMock(strategy_name="test"))


# ─────────────────────────────────────────────────────────────────────────────
# GenericFeatureProvider
# ─────────────────────────────────────────────────────────────────────────────

class TestGenericFeatureProvider:
    def test_returns_dataset_correct_length(self):
        ds = _build_features()
        assert len(ds) == 120

    def test_all_arrays_same_length(self):
        ds = _build_features()
        n = len(ds)
        assert len(ds.closes) == n
        assert len(ds.highs) == n
        assert len(ds.lows) == n
        assert len(ds.adx_values) == n
        assert len(ds.rsi_values) == n
        assert len(ds.atr_values) == n
        assert len(ds.sma_5_values) == n
        assert len(ds.sma_20_values) == n
        assert len(ds.sma_50_values) == n
        assert len(ds.bb_zscore_values) == n
        assert len(ds.realized_vol_values) == n

    def test_sma5_valid_after_5_bars(self):
        ds = _build_features()
        assert ds.sma_5_values[4] is not None
        assert ds.sma_5_values[3] is None

    def test_sma20_valid_after_20_bars(self):
        ds = _build_features()
        assert ds.sma_20_values[19] is not None
        assert ds.sma_20_values[18] is None

    def test_sma50_valid_after_50_bars(self):
        ds = _build_features()
        assert ds.sma_50_values[49] is not None
        assert ds.sma_50_values[48] is None

    def test_closes_match_input(self):
        candles = _candles(60)
        ds = _build_features(candles)
        assert ds.closes[0] == pytest.approx(candles[0]["close"])
        assert ds.closes[-1] == pytest.approx(candles[-1]["close"])

    def test_bb_zscore_zero_for_flat_data(self):
        candles = _flat_candles(60)
        ds = _build_features(candles)
        # All closes identical → std ≈ 0 → zscore should be None (division by zero guard)
        assert ds.bb_zscore_values[-1] is None

    def test_realized_vol_not_none_after_warmup(self):
        ds = _build_features()
        assert ds.realized_vol_values[-1] is not None

    def test_adx_not_none_at_end(self):
        ds = _build_features()
        assert ds.adx_values[-1] is not None

    def test_rsi_not_none_at_end(self):
        ds = _build_features()
        assert ds.rsi_values[-1] is not None

    def test_dataset_immutable(self):
        ds = _build_features()
        with pytest.raises((AttributeError, TypeError)):
            ds.closes = ()  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# GenericRegimeProvider
# ─────────────────────────────────────────────────────────────────────────────

class TestGenericRegimeProvider:
    def test_range_when_adx_low(self):
        from core.regime.models import RegimeType
        ds = GenericOHLCVDataset(
            closes=(100.0,), highs=(101.0,), lows=(99.0,),
            adx_values=(10.0,), rsi_values=(50.0,), atr_values=(1.0,),
            sma_5_values=(100.0,), sma_20_values=(100.0,), sma_50_values=(100.0,),
            bb_zscore_values=(0.0,), realized_vol_values=(0.01,),
        )
        rp = GenericRegimeProvider()
        snap = rp.classify(ds)
        assert snap.regime == RegimeType.RANGE

    def test_trend_up_when_adx_high(self):
        from core.regime.models import RegimeType
        ds = GenericOHLCVDataset(
            closes=(100.0,), highs=(101.0,), lows=(99.0,),
            adx_values=(30.0,), rsi_values=(60.0,), atr_values=(1.0,),
            sma_5_values=(100.0,), sma_20_values=(99.0,), sma_50_values=(98.0,),
            bb_zscore_values=(0.5,), realized_vol_values=(0.01,),
        )
        rp = GenericRegimeProvider()
        snap = rp.classify(ds)
        assert snap.regime == RegimeType.TREND_UP

    def test_unknown_when_no_valid_adx(self):
        from core.regime.models import RegimeType
        ds = GenericOHLCVDataset(
            closes=(100.0,), highs=(101.0,), lows=(99.0,),
            adx_values=(None,), rsi_values=(None,), atr_values=(None,),
            sma_5_values=(None,), sma_20_values=(None,), sma_50_values=(None,),
            bb_zscore_values=(None,), realized_vol_values=(None,),
        )
        rp = GenericRegimeProvider()
        snap = rp.classify(ds)
        assert snap.regime == RegimeType.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
# Signal Dispatch — GenericStrategyRunner._check_signal
# ─────────────────────────────────────────────────────────────────────────────

def _make_ds(**kwargs) -> GenericOHLCVDataset:
    defaults = dict(
        closes=(100.0,), highs=(101.0,), lows=(99.0,),
        adx_values=(25.0,), rsi_values=(50.0,), atr_values=(1.0,),
        sma_5_values=(100.0,), sma_20_values=(100.0,), sma_50_values=(99.0,),
        bb_zscore_values=(0.0,), realized_vol_values=(0.01,),
    )
    defaults.update(kwargs)
    return GenericOHLCVDataset(**defaults)


def _runner(signal_type, signal_params=None, hold_bars=5):
    from core.costs.engine import ExecutionCostEngine
    from core.walkforward.engine import WalkForwardEngine
    from core.walkforward.window_generator import WalkForwardWindowGenerator
    wf = WalkForwardEngine(WalkForwardWindowGenerator(
        WalkForwardConfig(train_size=10, test_size=5, step_size=5)
    ))
    return GenericStrategyRunner(
        signal_type=signal_type,
        hold_bars=hold_bars,
        signal_params=signal_params or {},
        wf_engine=wf,
        cost_engine=ExecutionCostEngine(),
    )


class TestSignalDispatch:
    def test_rsi_oversold_fires_when_rsi_below_threshold(self):
        r = _runner("rsi_oversold", {"rsi_threshold": 30.0})
        ds = _make_ds(rsi_values=(25.0,))
        assert r._check_signal(ds, 0) is True

    def test_rsi_oversold_silent_when_rsi_above_threshold(self):
        r = _runner("rsi_oversold", {"rsi_threshold": 30.0})
        ds = _make_ds(rsi_values=(45.0,))
        assert r._check_signal(ds, 0) is False

    def test_rsi_oversold_silent_when_none(self):
        r = _runner("rsi_oversold")
        ds = _make_ds(rsi_values=(None,))
        assert r._check_signal(ds, 0) is False

    def test_rsi_momentum_fires_when_both_conditions_met(self):
        r = _runner("rsi_momentum", {"rsi_min": 55.0, "adx_min": 20.0})
        ds = _make_ds(rsi_values=(60.0,), adx_values=(25.0,))
        assert r._check_signal(ds, 0) is True

    def test_rsi_momentum_silent_when_rsi_low(self):
        r = _runner("rsi_momentum", {"rsi_min": 55.0, "adx_min": 20.0})
        ds = _make_ds(rsi_values=(40.0,), adx_values=(25.0,))
        assert r._check_signal(ds, 0) is False

    def test_rsi_momentum_silent_when_adx_low(self):
        r = _runner("rsi_momentum", {"rsi_min": 55.0, "adx_min": 20.0})
        ds = _make_ds(rsi_values=(60.0,), adx_values=(15.0,))
        assert r._check_signal(ds, 0) is False

    def test_sma_crossover_fires_on_golden_cross(self):
        r = _runner("sma_crossover")
        # bar 0: sma20=99, sma50=100 (below) | bar 1: sma20=101, sma50=100 (above)
        ds = GenericOHLCVDataset(
            closes=(100.0, 100.0), highs=(101.0, 101.0), lows=(99.0, 99.0),
            adx_values=(25.0, 25.0), rsi_values=(55.0, 55.0), atr_values=(1.0, 1.0),
            sma_5_values=(100.0, 100.0),
            sma_20_values=(99.0, 101.0), sma_50_values=(100.0, 100.0),
            bb_zscore_values=(0.0, 0.0), realized_vol_values=(0.01, 0.01),
        )
        assert r._check_signal(ds, 0) is False  # bar 0: prev unavailable
        assert r._check_signal(ds, 1) is True   # bar 1: crossover

    def test_sma_crossover_silent_at_bar_zero(self):
        r = _runner("sma_crossover")
        ds = _make_ds()
        assert r._check_signal(ds, 0) is False

    def test_momentum_pullback_fires_when_price_between_smas(self):
        r = _runner("momentum_pullback")
        # close > sma50 AND close < sma20
        ds = _make_ds(closes=(105.0,), sma_20_values=(107.0,), sma_50_values=(103.0,))
        assert r._check_signal(ds, 0) is True

    def test_momentum_pullback_silent_when_price_above_sma20(self):
        r = _runner("momentum_pullback")
        ds = _make_ds(closes=(110.0,), sma_20_values=(107.0,), sma_50_values=(103.0,))
        assert r._check_signal(ds, 0) is False

    def test_vol_breakout_fires_when_rv_and_adx_above_threshold(self):
        r = _runner("vol_breakout", {"vol_threshold": 0.010, "adx_min": 20.0})
        ds = _make_ds(realized_vol_values=(0.020,), adx_values=(25.0,))
        assert r._check_signal(ds, 0) is True

    def test_vol_breakout_silent_when_rv_low(self):
        r = _runner("vol_breakout", {"vol_threshold": 0.010, "adx_min": 20.0})
        ds = _make_ds(realized_vol_values=(0.005,), adx_values=(25.0,))
        assert r._check_signal(ds, 0) is False

    def test_trend_strength_fires_when_adx_and_rsi_above_threshold(self):
        r = _runner("trend_strength", {"adx_min": 30.0, "rsi_min": 50.0})
        ds = _make_ds(adx_values=(35.0,), rsi_values=(60.0,))
        assert r._check_signal(ds, 0) is True

    def test_trend_strength_silent_when_adx_below_threshold(self):
        r = _runner("trend_strength", {"adx_min": 30.0, "rsi_min": 50.0})
        ds = _make_ds(adx_values=(25.0,), rsi_values=(60.0,))
        assert r._check_signal(ds, 0) is False

    def test_bb_squeeze_fires_when_zscore_and_rsi_within_limits(self):
        r = _runner("bb_squeeze", {"bb_z_max": 0.5, "rsi_min": 50.0})
        ds = _make_ds(bb_zscore_values=(0.3,), rsi_values=(55.0,))
        assert r._check_signal(ds, 0) is True

    def test_bb_squeeze_silent_when_zscore_too_large(self):
        r = _runner("bb_squeeze", {"bb_z_max": 0.5, "rsi_min": 50.0})
        ds = _make_ds(bb_zscore_values=(1.5,), rsi_values=(55.0,))
        assert r._check_signal(ds, 0) is False

    def test_dual_ma_trend_fires_when_all_aligned(self):
        r = _runner("dual_ma_trend")
        ds = _make_ds(sma_5_values=(105.0,), sma_20_values=(103.0,), sma_50_values=(100.0,))
        assert r._check_signal(ds, 0) is True

    def test_dual_ma_trend_silent_when_partial_alignment(self):
        r = _runner("dual_ma_trend")
        ds = _make_ds(sma_5_values=(102.0,), sma_20_values=(103.0,), sma_50_values=(100.0,))
        assert r._check_signal(ds, 0) is False  # sma5 < sma20

    def test_unknown_signal_type_returns_false(self):
        r = _runner("nonexistent_signal")
        ds = _make_ds()
        assert r._check_signal(ds, 0) is False


# ─────────────────────────────────────────────────────────────────────────────
# GenericProviderFactory — all 8 thin subclass factories
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("module_path,class_name,expected_type", [
    ("experiments.h_rsi_oversold.providers", "RsiOversoldProviderFactory", "rsi_oversold"),
    ("experiments.h_rsi_momentum.providers", "RsiMomentumProviderFactory", "rsi_momentum"),
    ("experiments.h_sma_crossover.providers", "SmaCrossoverProviderFactory", "sma_crossover"),
    ("experiments.h_momentum_pullback.providers", "MomentumPullbackProviderFactory", "momentum_pullback"),
    ("experiments.h_vol_breakout.providers", "VolBreakoutProviderFactory", "vol_breakout"),
    ("experiments.h_trend_strength.providers", "TrendStrengthProviderFactory", "trend_strength"),
    ("experiments.h_bb_squeeze.providers", "BBSqueezeProviderFactory", "bb_squeeze"),
    ("experiments.h_dual_ma_trend.providers", "DualMaTrendProviderFactory", "dual_ma_trend"),
])
def test_thin_factory_signal_type(module_path, class_name, expected_type):
    import importlib
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    factory = cls()
    assert factory.signal_type == expected_type
    assert isinstance(factory.hold_bars, int)
    assert factory.hold_bars > 0
    assert isinstance(factory, GenericProviderFactory)


def test_generic_factory_create_providers_returns_four_tuple():
    from experiments.h_rsi_oversold.providers import RsiOversoldProviderFactory
    factory = RsiOversoldProviderFactory()
    candles = _candles(120)
    dataset = MagicMock()
    dataset.candles = iter(candles)
    wf_config = WalkForwardConfig(train_size=30, test_size=10, step_size=10)
    providers = factory.create_providers(dataset, wf_config)
    assert len(providers) == 4


def test_generic_feature_provider_run_end_to_end():
    """End-to-end: GenericFeatureProvider + GenericStrategyRunner run successfully."""
    from core.costs.engine import ExecutionCostEngine
    from core.experiment.models import ExperimentConfig
    from core.walkforward.engine import WalkForwardEngine
    from core.walkforward.window_generator import WalkForwardWindowGenerator

    candles = _candles(150)
    fp = GenericFeatureProvider(candles)
    config = ExperimentConfig(
        experiment_id="e1", hypothesis_id="h1", dataset_id="ds1",
        strategy_name="test", feature_set=[],
    )
    ds = fp.build_features(config)

    wf_cfg = WalkForwardConfig(train_size=50, test_size=20, step_size=20)
    runner = GenericStrategyRunner(
        signal_type="rsi_oversold",
        hold_bars=5,
        signal_params={"rsi_threshold": 30.0},
        wf_engine=WalkForwardEngine(WalkForwardWindowGenerator(wf_cfg)),
        cost_engine=ExecutionCostEngine(),
    )
    summary = runner.run(config, ds)
    assert len(summary.runs) > 0
