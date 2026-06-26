"""Entry point for the H-13 ADX Continuation synthetic research experiment.

Usage:
    from experiments.h13_adx_continuation.experiment import run_h13_experiment

    result = run_h13_experiment(candles=my_candles, knowledge_base=kb)
"""
from __future__ import annotations

from core.costs.engine import ExecutionCostEngine
from core.costs.models import ExecutionCostConfig
from core.experiment.engine import ExperimentRunner
from core.experiment.models import ExperimentConfig
from core.hypothesis.models import Hypothesis
from core.hypothesis.service import HypothesisRegistry
from core.knowledge.service import KnowledgeBase
from core.research_pipeline.pipeline import ResearchPipeline, ResearchPipelineResult
from core.validation.report import ValidationReportBuilder
from core.walkforward.engine import WalkForwardEngine
from core.walkforward.models import WalkForwardConfig
from core.walkforward.window_generator import WalkForwardWindowGenerator
from experiments.h13_adx_continuation.providers import (
    H13FeatureProvider,
    H13RegimeProvider,
    H13StrategyRunner,
)
from core.research_pipeline.adapters import ValidationReportAdapter

_WF_CONFIG = WalkForwardConfig(train_size=252, test_size=63, step_size=63)

_EXPERIMENT_ID = "h13_adx_continuation_synthetic_v1"
_DATASET_ID = "synthetic_uptrend_v1"
_STRATEGY_NAME = "adx_trend_continuation"
_FEATURE_SET = ["adx_14", "rsi_14", "sma_20", "sma_50", "atr_14"]

_H13_TITLE = "ADX Trend Continuation with RSI Pullback"
_H13_STATEMENT = (
    "When the market is in TREND_UP regime (ADX > 25, SMA_fast > SMA_slow) "
    "and RSI retraces to the neutral zone [40, 60], the price continues in "
    "the direction of the trend — generating a profitable long entry."
)


def run_h13_experiment(
    candles: list[dict],
    *,
    knowledge_base: KnowledgeBase | None = None,
    hypothesis: Hypothesis | None = None,
) -> ResearchPipelineResult:
    """Run the full H-13 synthetic research cycle and return the pipeline result.

    Args:
        candles:        OHLCV dicts with keys: ticker, ts, open, high, low, close, volume.
        knowledge_base: Existing KnowledgeBase; a fresh in-memory one is created if omitted.
        hypothesis:     Existing Hypothesis; a new IDEA-stage one is created if omitted.

    Returns:
        ResearchPipelineResult with experiment result and knowledge entry.
    """
    kb = knowledge_base or KnowledgeBase()

    if hypothesis is None:
        registry = HypothesisRegistry()
        hypothesis = registry.create(_H13_TITLE, _H13_STATEMENT)

    feature_provider = H13FeatureProvider(candles)
    regime_provider = H13RegimeProvider()

    wf_engine = WalkForwardEngine(WalkForwardWindowGenerator(_WF_CONFIG))
    cost_engine = ExecutionCostEngine(ExecutionCostConfig())
    strategy_runner = H13StrategyRunner(wf_engine, cost_engine)

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

    config = ExperimentConfig(
        experiment_id=_EXPERIMENT_ID,
        hypothesis_id=hypothesis.id,
        dataset_id=_DATASET_ID,
        strategy_name=_STRATEGY_NAME,
        feature_set=_FEATURE_SET,
    )

    return pipeline.run(hypothesis, config)
