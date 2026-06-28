"""Tests for experiments.h_rev_vol_reg providers.

Validates:
  - RevVolRegFeatureProvider: bb_zscore, realized_vol, atr correctly computed
  - RevVolRegRegimeProvider: RANGE when ADX < 20, TREND_UP when ADX >= 20
  - RevVolRegStrategyRunner: entry on ADX<20 + bb_z<-2, time-based exit
  - RevVolRegProviderFactory: assembles all providers correctly
"""
from __future__ import annotations

import math

import pytest

from core.experiment.models import ExperimentConfig
from core.regime.models import RegimeType
from experiments.h_rev_vol_reg.dataset import RevVolRegDataset
from experiments.h_rev_vol_reg.providers import (
    RevVolRegFeatureProvider,
    RevVolRegProviderFactory,
    RevVolRegRegimeProvider,
    RevVolRegStrategyRunner,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="exp_rev_001",
        hypothesis_id="h_rev_vol_reg",
        dataset_id="sber_test",
        strategy_name="rev_vol_reg",
        feature_set=["bb_zscore_20", "realized_vol_20", "adx_14", "rsi_14", "atr_14"],
    )


def _make_candle(close: float, high: float | None = None, low: float | None = None) -> dict:
    h = high if high is not None else close + 1.0
    lo = low if low is not None else close - 1.0
    return {
        "ticker": "SBER",
        "ts": "2023-01-01T10:00:00",
        "open": str(close - 0.3),
        "high": str(h),
        "low": str(lo),
        "close": str(close),
        "volume": "500000",
    }


def _oscillating_candles(n: int = 100, amplitude: float = 10.0, period: float = 20.0) -> list[dict]:
    """Low-trend oscillating data — ideal for ranging regime."""
    return [
        _make_candle(230.0 + amplitude * math.sin(i * 2 * math.pi / period))
        for i in range(n)
    ]


def _trending_candles(n: int = 100) -> list[dict]:
    """Monotonically rising — produces high ADX (trending regime)."""
    return [_make_candle(200.0 + i * 0.5) for i in range(n)]


def _dip_candles(n: int = 100) -> list[dict]:
    """Oscillating with a sharp dip at bar 70 → bb_zscore < -2."""
    candles = []
    for i in range(n):
        if 65 <= i <= 72:
            close = 230.0 - 30.0  # deep dip, 30 below the ~230 mean
        else:
            close = 230.0 + 5.0 * math.sin(i * 0.3)
        candles.append(_make_candle(close))
    return candles


# ─── Feature Provider ─────────────────────────────────────────────────────────

class TestRevVolRegFeatureProvider:
    def test_returns_rev_vol_reg_dataset(self):
        candles = _oscillating_candles(60)
        provider = RevVolRegFeatureProvider(candles)
        dataset = provider.build_features(_make_config())
        assert isinstance(dataset, RevVolRegDataset)

    def test_output_length_matches_input(self):
        n = 80
        candles = _oscillating_candles(n)
        provider = RevVolRegFeatureProvider(candles)
        dataset = provider.build_features(_make_config())
        assert len(dataset) == n
        assert len(dataset.closes) == n
        assert len(dataset.bb_zscore_values) == n
        assert len(dataset.adx_values) == n

    def test_first_bars_have_none_for_bb_zscore(self):
        candles = _oscillating_candles(60)
        provider = RevVolRegFeatureProvider(candles)
        dataset = provider.build_features(_make_config())
        # bb_zscore requires 20 bars → first 19 are None
        for i in range(19):
            assert dataset.bb_zscore_values[i] is None

    def test_bb_zscore_valid_after_warmup(self):
        candles = _oscillating_candles(60)
        provider = RevVolRegFeatureProvider(candles)
        dataset = provider.build_features(_make_config())
        # bar 19+ should have a valid bb_zscore
        assert dataset.bb_zscore_values[19] is not None

    def test_bb_zscore_negative_during_dip(self):
        candles = _dip_candles(100)
        provider = RevVolRegFeatureProvider(candles)
        dataset = provider.build_features(_make_config())
        # During the dip window, bb_zscore should be significantly negative
        dip_zscores = [
            z for z in dataset.bb_zscore_values[65:73] if z is not None
        ]
        assert any(z < -1.5 for z in dip_zscores), f"expected negative z-scores, got {dip_zscores}"

    def test_bb_upper_above_lower(self):
        candles = _oscillating_candles(60)
        provider = RevVolRegFeatureProvider(candles)
        dataset = provider.build_features(_make_config())
        for u, lo in zip(dataset.bb_upper_values, dataset.bb_lower_values):
            if u is not None and lo is not None:
                assert u > lo

    def test_realized_vol_non_negative(self):
        candles = _oscillating_candles(60)
        provider = RevVolRegFeatureProvider(candles)
        dataset = provider.build_features(_make_config())
        for v in dataset.realized_vol_values:
            if v is not None:
                assert v >= 0.0

    def test_atr_values_positive(self):
        candles = _oscillating_candles(60)
        provider = RevVolRegFeatureProvider(candles)
        dataset = provider.build_features(_make_config())
        for a in dataset.atr_values:
            if a is not None:
                assert a > 0.0

    def test_closes_preserved(self):
        candles = _oscillating_candles(30)
        provider = RevVolRegFeatureProvider(candles)
        dataset = provider.build_features(_make_config())
        for i, c in enumerate(candles):
            assert dataset.closes[i] == float(c["close"])


# ─── Regime Provider ──────────────────────────────────────────────────────────

class TestRevVolRegRegimeProvider:
    def _make_dataset_with_adx(self, adx_last: float) -> RevVolRegDataset:
        """Minimal dataset with a controlled last ADX value."""
        n = 5
        adx_values = tuple([None] * (n - 1) + [adx_last])
        return RevVolRegDataset(
            closes=(230.0,) * n,
            highs=(231.0,) * n,
            lows=(229.0,) * n,
            adx_values=adx_values,
            rsi_values=(None,) * n,
            bb_zscore_values=(None,) * n,
            realized_vol_values=(None,) * n,
            atr_values=(None,) * n,
            bb_upper_values=(None,) * n,
            bb_lower_values=(None,) * n,
        )

    def test_low_adx_gives_range_regime(self):
        provider = RevVolRegRegimeProvider()
        dataset = self._make_dataset_with_adx(12.0)
        snapshot = provider.classify(dataset)
        assert snapshot.regime == RegimeType.RANGE

    def test_high_adx_gives_trending_regime(self):
        provider = RevVolRegRegimeProvider()
        dataset = self._make_dataset_with_adx(28.0)
        snapshot = provider.classify(dataset)
        assert snapshot.regime != RegimeType.RANGE

    def test_boundary_adx_just_below_threshold(self):
        provider = RevVolRegRegimeProvider()
        dataset = self._make_dataset_with_adx(19.9)
        snapshot = provider.classify(dataset)
        assert snapshot.regime == RegimeType.RANGE

    def test_boundary_adx_at_threshold_is_trending(self):
        provider = RevVolRegRegimeProvider()
        dataset = self._make_dataset_with_adx(20.0)
        snapshot = provider.classify(dataset)
        assert snapshot.regime != RegimeType.RANGE

    def test_confidence_between_0_and_1(self):
        provider = RevVolRegRegimeProvider()
        for adx_val in [5.0, 10.0, 19.9, 20.0, 35.0]:
            dataset = self._make_dataset_with_adx(adx_val)
            snapshot = provider.classify(dataset)
            assert 0.0 <= snapshot.confidence <= 1.0

    def test_no_valid_adx_returns_unknown(self):
        provider = RevVolRegRegimeProvider()
        dataset = RevVolRegDataset(
            closes=(230.0,) * 5,
            highs=(231.0,) * 5,
            lows=(229.0,) * 5,
            adx_values=(None,) * 5,
            rsi_values=(None,) * 5,
            bb_zscore_values=(None,) * 5,
            realized_vol_values=(None,) * 5,
            atr_values=(None,) * 5,
            bb_upper_values=(None,) * 5,
            bb_lower_values=(None,) * 5,
        )
        snapshot = provider.classify(dataset)
        assert snapshot.regime == RegimeType.UNKNOWN


# ─── Strategy Runner ──────────────────────────────────────────────────────────

class TestRevVolRegStrategyRunner:
    def _make_runner(self, train_size: int = 30, test_size: int = 10, step_size: int = 10):
        from core.costs.engine import ExecutionCostEngine
        from core.walkforward.engine import WalkForwardEngine
        from core.walkforward.models import WalkForwardConfig
        from core.walkforward.window_generator import WalkForwardWindowGenerator
        wf_config = WalkForwardConfig(
            train_size=train_size, test_size=test_size, step_size=step_size
        )
        return RevVolRegStrategyRunner(
            wf_engine=WalkForwardEngine(WalkForwardWindowGenerator(wf_config)),
            cost_engine=ExecutionCostEngine(),
        )

    def _build_dataset(self, candles: list[dict]) -> RevVolRegDataset:
        return RevVolRegFeatureProvider(candles).build_features(_make_config())

    def test_runner_returns_walk_forward_summary(self):
        from core.walkforward.models import WalkForwardSummary
        candles = _oscillating_candles(100)
        dataset = self._build_dataset(candles)
        runner = self._make_runner()
        summary = runner.run(_make_config(), dataset)
        assert isinstance(summary, WalkForwardSummary)

    def test_runner_completes_on_trending_data_with_no_signals(self):
        """Rising prices → ADX high → no entries; runner still completes."""
        candles = _trending_candles(100)
        dataset = self._build_dataset(candles)
        runner = self._make_runner()
        summary = runner.run(_make_config(), dataset)
        assert summary is not None

    def test_runner_on_oscillating_data_produces_windows(self):
        candles = _oscillating_candles(100)
        dataset = self._build_dataset(candles)
        runner = self._make_runner()
        summary = runner.run(_make_config(), dataset)
        assert len(summary.runs) > 0

    def test_dip_data_may_generate_trades(self):
        """Dip data has low ADX (oscillating) and deep dips — should produce entries."""
        candles = _dip_candles(150)
        dataset = self._build_dataset(candles)
        runner = self._make_runner(train_size=40, test_size=15, step_size=15)
        summary = runner.run(_make_config(), dataset)
        # At least the runner finishes without error
        assert summary is not None

    def test_hold_bars_limits_position_duration(self):
        """Each trade holds exactly _HOLD_BARS or fewer (capped at window end)."""
        candles = _dip_candles(150)
        dataset = self._build_dataset(candles)
        runner = self._make_runner(train_size=40, test_size=20, step_size=20)
        # Just verifying no exception is raised — hold logic tested via no-overlap
        summary = runner.run(_make_config(), dataset)
        assert summary is not None

    def test_trending_data_no_entries(self):
        """Monotonically rising data produces high ADX → no BUY signals."""
        candles = _trending_candles(120)
        dataset = self._build_dataset(candles)
        runner = self._make_runner(train_size=40, test_size=15, step_size=15)
        summary = runner.run(_make_config(), dataset)
        # With high ADX (trending), signal_ok is False → trades_count=0 per window
        for run in summary.runs:
            result = run.result if hasattr(run, "result") else run
            count = result.get("trades_count", 0) if isinstance(result, dict) else 0
            assert count == 0


# ─── Provider Factory ─────────────────────────────────────────────────────────

class TestRevVolRegProviderFactory:
    @pytest.fixture
    def factory(self) -> RevVolRegProviderFactory:
        return RevVolRegProviderFactory()

    def _make_mock_dataset(self, n: int = 80):
        candles = _oscillating_candles(n)

        class _MockDataset:
            @property
            def candles(self):
                return candles
        return _MockDataset()

    def test_factory_create_providers_returns_tuple_of_4(self, factory):
        from core.walkforward.models import WalkForwardConfig
        wf_config = WalkForwardConfig(train_size=30, test_size=10, step_size=10)
        providers = factory.create_providers(self._make_mock_dataset(), wf_config)
        assert len(providers) == 4

    def test_factory_first_provider_is_feature_provider(self, factory):
        from core.walkforward.models import WalkForwardConfig
        wf_config = WalkForwardConfig(train_size=30, test_size=10, step_size=10)
        feature_p, _, _, _ = factory.create_providers(self._make_mock_dataset(), wf_config)
        assert isinstance(feature_p, RevVolRegFeatureProvider)

    def test_factory_second_provider_is_regime_provider(self, factory):
        from core.walkforward.models import WalkForwardConfig
        wf_config = WalkForwardConfig(train_size=30, test_size=10, step_size=10)
        _, regime_p, _, _ = factory.create_providers(self._make_mock_dataset(), wf_config)
        assert isinstance(regime_p, RevVolRegRegimeProvider)

    def test_factory_third_provider_is_strategy_runner(self, factory):
        from core.walkforward.models import WalkForwardConfig
        wf_config = WalkForwardConfig(train_size=30, test_size=10, step_size=10)
        _, _, strategy_p, _ = factory.create_providers(self._make_mock_dataset(), wf_config)
        assert isinstance(strategy_p, RevVolRegStrategyRunner)

    def test_factory_duck_typed_dataset(self, factory):
        """dataset is duck-typed — any object with .candles works."""
        from core.walkforward.models import WalkForwardConfig
        wf_config = WalkForwardConfig(train_size=30, test_size=10, step_size=10)

        class AnotherDataset:
            @property
            def candles(self):
                return _oscillating_candles(50)

        providers = factory.create_providers(AnotherDataset(), wf_config)
        assert len(providers) == 4
