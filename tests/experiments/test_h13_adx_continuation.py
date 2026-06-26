"""Integration tests for H-13 ADX Continuation synthetic experiment.

All tests use deterministic synthetic OHLCV data (no real market data, no I/O).
The experiment must pass the full cycle:
  Hypothesis → H13FeatureProvider → H13RegimeProvider → H13StrategyRunner
             → ValidationReport → KnowledgeBase

Tests verify pipeline integrity, not trading edge quality.
"""
from __future__ import annotations

import math

import pytest

from core.experiment.models import ExperimentConfig, ExperimentStage
from core.hypothesis.service import HypothesisRegistry
from core.knowledge.models import KnowledgeType
from core.knowledge.service import KnowledgeBase
from core.regime.models import RegimeType
from core.research_pipeline.pipeline import ResearchPipelineResult
from experiments.h13_adx_continuation.dataset import H13Dataset
from experiments.h13_adx_continuation.experiment import run_h13_experiment
from experiments.h13_adx_continuation.providers import H13FeatureProvider, H13RegimeProvider


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic data generator
# ──────────────────────────────────────────────────────────────────────────────

def _make_uptrend_candles(n: int = 400) -> list[dict]:
    """Generate n synthetic OHLCV bars in a strong uptrend.

    Trend: +0.25% per bar.  Oscillation: ±0.4% (sin-based, period ≈ 21 bars).
    This ensures:
      - ADX > 25 after warm-up (strong directional movement).
      - SMA(20) > SMA(50) after 50 bars.
      - RSI periodically dips into [40, 60] on pullback phases → H-13 signals fire.
      - Buying on pullbacks in uptrend is profitable after costs.
    """
    candles: list[dict] = []
    price = 100.0
    for i in range(n):
        trend = 0.0025
        oscillation = math.sin(i * 0.30) * 0.004
        change = trend + oscillation

        open_ = price
        close = price * (1.0 + change)
        high = max(open_, close) * (1.0 + abs(math.cos(i * 0.71)) * 0.003)
        low = min(open_, close) * (1.0 - abs(math.sin(i * 0.53)) * 0.003)

        candles.append(
            {
                "ticker": "SYNTHETIC",
                "ts": f"2024-{i // 30 + 1:02d}-{i % 30 + 1:02d}",
                "open": round(open_, 6),
                "high": round(high, 6),
                "low": round(low, 6),
                "close": round(close, 6),
                "volume": 1_000_000.0,
            }
        )
        price = close
    return candles


_CANDLES = _make_uptrend_candles(400)


# ──────────────────────────────────────────────────────────────────────────────
# H13FeatureProvider
# ──────────────────────────────────────────────────────────────────────────────

def _dummy_config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="test_exp",
        hypothesis_id="h13",
        dataset_id="synthetic",
        strategy_name="adx_trend_continuation",
        feature_set=["adx_14"],
    )


def test_feature_provider_returns_h13dataset():
    provider = H13FeatureProvider(_CANDLES)
    result = provider.build_features(_dummy_config())
    assert isinstance(result, H13Dataset)


def test_feature_provider_dataset_length_matches_candles():
    provider = H13FeatureProvider(_CANDLES)
    result = provider.build_features(_dummy_config())
    assert len(result) == len(_CANDLES)


def test_feature_provider_adx_has_non_none_values():
    provider = H13FeatureProvider(_CANDLES)
    result = provider.build_features(_dummy_config())
    non_none = [v for v in result.adx_values if v is not None]
    assert len(non_none) > 0


def test_feature_provider_adx_exceeds_25_in_strong_uptrend():
    """With 400 bars of strong uptrend, final ADX must exceed 25."""
    provider = H13FeatureProvider(_CANDLES)
    result = provider.build_features(_dummy_config())
    non_none = [v for v in result.adx_values if v is not None]
    assert non_none[-1] > 25.0, f"ADX too low: {non_none[-1]:.2f}"


def test_feature_provider_sma_fast_above_slow_in_uptrend():
    """After 400 uptrend bars, SMA(20) must be above SMA(50)."""
    provider = H13FeatureProvider(_CANDLES)
    result = provider.build_features(_dummy_config())
    last_fast = next(v for v in reversed(result.sma_fast_values) if v is not None)
    last_slow = next(v for v in reversed(result.sma_slow_values) if v is not None)
    assert last_fast > last_slow


# ──────────────────────────────────────────────────────────────────────────────
# H13RegimeProvider
# ──────────────────────────────────────────────────────────────────────────────

def test_regime_provider_returns_regime_snapshot():
    from core.regime.models import RegimeSnapshot

    provider = H13FeatureProvider(_CANDLES)
    dataset = provider.build_features(_dummy_config())
    regime_provider = H13RegimeProvider()
    snapshot = regime_provider.classify(dataset)
    assert isinstance(snapshot, RegimeSnapshot)


def test_regime_provider_classifies_uptrend_as_trend_up():
    provider = H13FeatureProvider(_CANDLES)
    dataset = provider.build_features(_dummy_config())
    regime_provider = H13RegimeProvider()
    snapshot = regime_provider.classify(dataset)
    assert snapshot.regime == RegimeType.TREND_UP, (
        f"Expected TREND_UP, got {snapshot.regime} (ADX may be below threshold)"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Full pipeline: run_h13_experiment
# ──────────────────────────────────────────────────────────────────────────────

def test_pipeline_returns_research_pipeline_result():
    result = run_h13_experiment(_CANDLES)
    assert isinstance(result, ResearchPipelineResult)


def test_pipeline_experiment_stage_is_validated():
    result = run_h13_experiment(_CANDLES)
    assert result.experiment_result.stage == ExperimentStage.VALIDATED


def test_pipeline_experiment_result_has_regime():
    result = run_h13_experiment(_CANDLES)
    assert result.experiment_result.regime is not None


def test_pipeline_experiment_result_has_validation():
    result = run_h13_experiment(_CANDLES)
    assert result.experiment_result.validation is not None


def test_pipeline_experiment_result_regime_is_trend_up():
    result = run_h13_experiment(_CANDLES)
    assert result.experiment_result.regime.regime == RegimeType.TREND_UP


def test_pipeline_hypothesis_id_propagated():
    registry = HypothesisRegistry()
    hyp = registry.create("H-13 Test", "ADX continuation test")
    result = run_h13_experiment(_CANDLES, hypothesis=hyp)
    assert result.hypothesis_id == hyp.id


# ──────────────────────────────────────────────────────────────────────────────
# KnowledgeBase integration
# ──────────────────────────────────────────────────────────────────────────────

def test_knowledge_entry_created_after_pipeline():
    kb = KnowledgeBase()
    run_h13_experiment(_CANDLES, knowledge_base=kb)
    assert len(kb.list()) == 1


def test_knowledge_entry_type_is_experiment():
    kb = KnowledgeBase()
    run_h13_experiment(_CANDLES, knowledge_base=kb)
    entry = kb.list()[0]
    assert entry.knowledge_type == KnowledgeType.EXPERIMENT


def test_knowledge_entry_reference_id_matches_hypothesis():
    kb = KnowledgeBase()
    registry = HypothesisRegistry()
    hyp = registry.create("H-13 Reference Test", "ADX pullback entry")
    run_h13_experiment(_CANDLES, knowledge_base=kb, hypothesis=hyp)
    entry = kb.list()[0]
    assert entry.reference_id == hyp.id


def test_knowledge_entry_metadata_has_experiment_id():
    kb = KnowledgeBase()
    run_h13_experiment(_CANDLES, knowledge_base=kb)
    entry = kb.list()[0]
    assert "experiment_id" in entry.metadata
    assert entry.metadata["experiment_id"] == "h13_adx_continuation_synthetic_v1"


def test_knowledge_entry_metadata_has_validation_status():
    kb = KnowledgeBase()
    run_h13_experiment(_CANDLES, knowledge_base=kb)
    entry = kb.list()[0]
    assert "validation_status" in entry.metadata


def test_knowledge_entry_retrievable_by_experiment_type():
    kb = KnowledgeBase()
    run_h13_experiment(_CANDLES, knowledge_base=kb)
    results = kb.find_by_type(KnowledgeType.EXPERIMENT)
    assert len(results) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Determinism
# ──────────────────────────────────────────────────────────────────────────────

def test_pipeline_is_deterministic():
    """Two runs with identical synthetic data must produce identical outcomes."""
    result_a = run_h13_experiment(_CANDLES)
    result_b = run_h13_experiment(_CANDLES)

    assert result_a.experiment_result.stage == result_b.experiment_result.stage
    assert (
        result_a.experiment_result.regime.regime
        == result_b.experiment_result.regime.regime
    )
    assert (
        result_a.experiment_result.validation.status
        == result_b.experiment_result.validation.status
    )
    assert (
        result_a.experiment_result.validation.pass_rate
        == result_b.experiment_result.validation.pass_rate
    )


# ──────────────────────────────────────────────────────────────────────────────
# Walk-forward windows
# ──────────────────────────────────────────────────────────────────────────────

def test_walkforward_produces_at_least_one_window():
    """400 bars with train=252, test=63 must produce at least 1 WF window."""
    from core.costs.engine import ExecutionCostEngine
    from core.costs.models import ExecutionCostConfig
    from core.walkforward.engine import WalkForwardEngine
    from core.walkforward.models import WalkForwardConfig
    from core.walkforward.window_generator import WalkForwardWindowGenerator
    from experiments.h13_adx_continuation.providers import H13StrategyRunner

    wf_config = WalkForwardConfig(train_size=252, test_size=63, step_size=63)
    wf_engine = WalkForwardEngine(WalkForwardWindowGenerator(wf_config))
    cost_engine = ExecutionCostEngine(ExecutionCostConfig())
    runner = H13StrategyRunner(wf_engine, cost_engine)

    provider = H13FeatureProvider(_CANDLES)
    dataset = provider.build_features(_dummy_config())

    summary = runner.run(_dummy_config(), dataset)
    assert len(summary.runs) >= 1


def test_walkforward_window_results_have_expected_keys():
    from core.costs.engine import ExecutionCostEngine
    from core.costs.models import ExecutionCostConfig
    from core.walkforward.engine import WalkForwardEngine
    from core.walkforward.models import WalkForwardConfig
    from core.walkforward.window_generator import WalkForwardWindowGenerator
    from experiments.h13_adx_continuation.providers import H13StrategyRunner

    wf_config = WalkForwardConfig(train_size=252, test_size=63, step_size=63)
    wf_engine = WalkForwardEngine(WalkForwardWindowGenerator(wf_config))
    cost_engine = ExecutionCostEngine(ExecutionCostConfig())
    runner = H13StrategyRunner(wf_engine, cost_engine)

    provider = H13FeatureProvider(_CANDLES)
    dataset = provider.build_features(_dummy_config())

    summary = runner.run(_dummy_config(), dataset)
    for run in summary.runs:
        assert "trades_count" in run.result
        assert "total_pnl" in run.result
        assert "profitable" in run.result
