"""Integration tests for the first end-to-end research pipeline.

Uses real engine implementations throughout:
  - MarketRegimeEngine     (deterministic, rule-based)
  - WalkForwardEngine      (via WalkForwardStrategyAdapter stub)
  - ExecutionCostEngine    (via WalkForwardStrategyAdapter stub)
  - ValidationReportBuilder (via ValidationReportAdapter)
  - KnowledgeBase          (in-memory)
  - HypothesisRegistry     (in-memory)

Only the FeatureProvider and StrategyRunner are stubs (per spec).
"""
from __future__ import annotations

from typing import Any, Callable

import pytest

from core.costs.engine import ExecutionCostEngine
from core.costs.models import ExecutionCostConfig
from core.experiment.engine import ExperimentRunner
from core.experiment.models import ExperimentConfig, ExperimentStage
from core.hypothesis.models import Hypothesis, HypothesisStatus
from core.hypothesis.service import HypothesisRegistry
from core.knowledge.models import KnowledgeType
from core.knowledge.service import KnowledgeBase
from core.regime.engine import MarketRegimeEngine
from core.regime.models import RegimeFeatures
from core.research_pipeline import (
    RegimeEngineAdapter,
    ResearchPipeline,
    ResearchPipelineResult,
    StubFeatureProvider,
    ValidationReportAdapter,
    WalkForwardStrategyAdapter,
)
from core.validation.models import ValidationStatus
from core.validation.report import ValidationReportBuilder
from core.walkforward.engine import WalkForwardEngine
from core.walkforward.models import WalkForwardConfig
from core.walkforward.window_generator import WalkForwardWindowGenerator


# ──────────────────────────────────────────────────────────────────────────────
# Default test fixtures
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_FEATURES = RegimeFeatures(
    adx=30.0,               # > 25 → trend detected
    atr_pct=0.02,           # < 0.04 → not high volatility
    sma_fast=105.0,         # > sma_slow → TREND_UP
    sma_slow=100.0,
    realized_volatility=0.02,
)

# 100 data points, 2 walk-forward windows (0-50/50-70, 20-70/70-90)
_WF_CONFIG = WalkForwardConfig(train_size=50, test_size=20, step_size=20)
_DATA_LENGTH = 100


def _make_pipeline(
    *,
    features: RegimeFeatures = _DEFAULT_FEATURES,
    data_length: int = _DATA_LENGTH,
    wf_config: WalkForwardConfig = _WF_CONFIG,
    evaluator: Callable[[Any], bool] | None = None,
    strategy_runner_override=None,
    knowledge_base: KnowledgeBase | None = None,
) -> tuple[ResearchPipeline, KnowledgeBase]:
    kb = knowledge_base or KnowledgeBase()

    feature_provider = StubFeatureProvider(features)
    regime_provider = RegimeEngineAdapter(MarketRegimeEngine())

    if strategy_runner_override is not None:
        strategy_runner = strategy_runner_override
    else:
        wf_engine = WalkForwardEngine(WalkForwardWindowGenerator(wf_config))
        cost_engine = ExecutionCostEngine(ExecutionCostConfig())
        strategy_runner = WalkForwardStrategyAdapter(wf_engine, cost_engine, data_length)

    if evaluator is None:
        evaluator = lambda result: result["profitable"]

    validation_runner = ValidationReportAdapter(ValidationReportBuilder(), evaluator)

    experiment_runner = ExperimentRunner(
        feature_provider=feature_provider,
        regime_provider=regime_provider,
        strategy_runner=strategy_runner,
        validation_runner=validation_runner,
    )

    pipeline = ResearchPipeline(
        experiment_runner=experiment_runner,
        knowledge_base=kb,
    )
    return pipeline, kb


def _hypothesis() -> Hypothesis:
    registry = HypothesisRegistry()
    return registry.create(
        "RSI Oversold in Uptrend",
        "Buy when RSI < 30 and regime is TREND_UP.",
    )


def _config(hypothesis_id: str) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="exp_integration_001",
        hypothesis_id=hypothesis_id,
        dataset_id="MOEX_SBER_2023",
        strategy_name="rsi_oversold",
        feature_set=["rsi_14", "sma_50"],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Successful pipeline
# ──────────────────────────────────────────────────────────────────────────────

def test_successful_pipeline_returns_result():
    pipeline, _ = _make_pipeline()
    hyp = _hypothesis()
    result = pipeline.run(hyp, _config(hyp.id))
    assert isinstance(result, ResearchPipelineResult)


def test_successful_pipeline_experiment_stage_is_validated():
    pipeline, _ = _make_pipeline()
    hyp = _hypothesis()
    result = pipeline.run(hyp, _config(hyp.id))
    assert result.experiment_result.stage == ExperimentStage.VALIDATED


def test_successful_pipeline_validation_status_is_pass():
    pipeline, _ = _make_pipeline()
    hyp = _hypothesis()
    result = pipeline.run(hyp, _config(hyp.id))
    assert result.experiment_result.validation.status == ValidationStatus.PASS


def test_successful_pipeline_regime_is_trend_up():
    """MarketRegimeEngine classifies _DEFAULT_FEATURES as TREND_UP."""
    from core.regime.models import RegimeType

    pipeline, _ = _make_pipeline()
    hyp = _hypothesis()
    result = pipeline.run(hyp, _config(hyp.id))
    assert result.experiment_result.regime.regime == RegimeType.TREND_UP


def test_successful_pipeline_result_carries_hypothesis_id():
    pipeline, _ = _make_pipeline()
    hyp = _hypothesis()
    result = pipeline.run(hyp, _config(hyp.id))
    assert result.hypothesis_id == hyp.id


# ──────────────────────────────────────────────────────────────────────────────
# Failed validation
# ──────────────────────────────────────────────────────────────────────────────

def test_failed_validation_report_status_is_fail():
    """Evaluator that always returns False → pass_rate=0 → FAIL."""
    pipeline, _ = _make_pipeline(evaluator=lambda _: False)
    hyp = _hypothesis()
    result = pipeline.run(hyp, _config(hyp.id))
    assert result.experiment_result.validation.status == ValidationStatus.FAIL


def test_failed_validation_experiment_stage_still_validated():
    """A failing validation report does not affect ExperimentStage."""
    pipeline, _ = _make_pipeline(evaluator=lambda _: False)
    hyp = _hypothesis()
    result = pipeline.run(hyp, _config(hyp.id))
    assert result.experiment_result.stage == ExperimentStage.VALIDATED


def test_failed_validation_knowledge_is_still_saved():
    """KnowledgeBase records even when validation fails."""
    pipeline, kb = _make_pipeline(evaluator=lambda _: False)
    hyp = _hypothesis()
    pipeline.run(hyp, _config(hyp.id))
    assert len(kb.list()) == 1


def test_failed_validation_knowledge_entry_reflects_fail():
    pipeline, kb = _make_pipeline(evaluator=lambda _: False)
    hyp = _hypothesis()
    pipeline.run(hyp, _config(hyp.id))
    entry = kb.list()[0]
    assert ValidationStatus.FAIL.value in entry.metadata["validation_status"]


# ──────────────────────────────────────────────────────────────────────────────
# Failed experiment
# ──────────────────────────────────────────────────────────────────────────────

class _CrashingStrategyRunner:
    def run(self, config, features):
        raise RuntimeError("strategy runner crashed during walk-forward")


def test_failed_experiment_exception_propagates():
    pipeline, _ = _make_pipeline(strategy_runner_override=_CrashingStrategyRunner())
    hyp = _hypothesis()
    with pytest.raises(RuntimeError, match="strategy runner crashed"):
        pipeline.run(hyp, _config(hyp.id))


def test_failed_experiment_knowledge_not_saved():
    """When ExperimentRunner raises, KnowledgeBase must remain empty."""
    pipeline, kb = _make_pipeline(strategy_runner_override=_CrashingStrategyRunner())
    hyp = _hypothesis()
    with pytest.raises(RuntimeError):
        pipeline.run(hyp, _config(hyp.id))
    assert kb.list() == []


# ──────────────────────────────────────────────────────────────────────────────
# Knowledge saved
# ──────────────────────────────────────────────────────────────────────────────

def test_knowledge_saved_after_successful_run():
    pipeline, kb = _make_pipeline()
    hyp = _hypothesis()
    pipeline.run(hyp, _config(hyp.id))
    assert len(kb.list()) == 1


def test_knowledge_entry_type_is_experiment():
    pipeline, kb = _make_pipeline()
    hyp = _hypothesis()
    pipeline.run(hyp, _config(hyp.id))
    entry = kb.list()[0]
    assert entry.knowledge_type == KnowledgeType.EXPERIMENT


def test_knowledge_entry_reference_id_is_hypothesis_id():
    pipeline, kb = _make_pipeline()
    hyp = _hypothesis()
    pipeline.run(hyp, _config(hyp.id))
    entry = kb.list()[0]
    assert entry.reference_id == hyp.id


def test_knowledge_entry_metadata_contains_experiment_id():
    pipeline, kb = _make_pipeline()
    hyp = _hypothesis()
    config = _config(hyp.id)
    pipeline.run(hyp, config)
    entry = kb.list()[0]
    assert entry.metadata["experiment_id"] == config.experiment_id


def test_knowledge_entry_tags_contain_strategy_name():
    pipeline, kb = _make_pipeline()
    hyp = _hypothesis()
    config = _config(hyp.id)
    pipeline.run(hyp, config)
    entry = kb.list()[0]
    assert config.strategy_name in entry.tags


def test_knowledge_entry_tags_contain_hypothesis_status():
    pipeline, kb = _make_pipeline()
    hyp = _hypothesis()
    pipeline.run(hyp, _config(hyp.id))
    entry = kb.list()[0]
    assert hyp.status.value in entry.tags


def test_knowledge_entry_retrievable_by_type():
    pipeline, kb = _make_pipeline()
    hyp = _hypothesis()
    pipeline.run(hyp, _config(hyp.id))
    results = kb.find_by_type(KnowledgeType.EXPERIMENT)
    assert len(results) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Deterministic full run
# ──────────────────────────────────────────────────────────────────────────────

def test_deterministic_full_run_same_validation_status():
    hyp = _hypothesis()
    config = _config(hyp.id)

    pipeline_a, _ = _make_pipeline()
    pipeline_b, _ = _make_pipeline()

    result_a = pipeline_a.run(hyp, config)
    result_b = pipeline_b.run(hyp, config)

    assert result_a.experiment_result.stage == result_b.experiment_result.stage
    assert (
        result_a.experiment_result.validation.status
        == result_b.experiment_result.validation.status
    )
    assert (
        result_a.experiment_result.validation.pass_rate
        == result_b.experiment_result.validation.pass_rate
    )


def test_deterministic_full_run_same_regime():
    hyp = _hypothesis()
    config = _config(hyp.id)

    pipeline_a, _ = _make_pipeline()
    pipeline_b, _ = _make_pipeline()

    result_a = pipeline_a.run(hyp, config)
    result_b = pipeline_b.run(hyp, config)

    assert result_a.experiment_result.regime.regime == result_b.experiment_result.regime.regime
    assert result_a.experiment_result.regime.confidence == result_b.experiment_result.regime.confidence
