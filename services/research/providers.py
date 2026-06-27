from __future__ import annotations

from typing import Protocol

from core.costs.engine import ExecutionCostEngine
from core.experiment.protocols import FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner
from core.hypothesis.service import HypothesisRegistry
from core.research_pipeline.adapters import ValidationReportAdapter
from core.research_session.report_models import HypothesisInfo
from core.validation.report import ValidationReportBuilder
from core.walkforward.engine import WalkForwardEngine
from core.walkforward.models import WalkForwardConfig
from core.walkforward.window_generator import WalkForwardWindowGenerator
from experiments.h13_adx_continuation.providers import (
    H13FeatureProvider,
    H13RegimeProvider,
    H13StrategyRunner,
)

from services.research.dataset import OhlcvDataset


class StrategyProviderFactory(Protocol):
    """Creates 4 providers for ExperimentRunner from a loaded dataset.

    Extension point EP-01: add a new strategy by implementing this Protocol.
    """

    def create_providers(
        self,
        dataset: OhlcvDataset,
        wf_config: WalkForwardConfig,
    ) -> tuple[FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner]: ...


class AdxContinuationProviderFactory:
    """Assembles H-13 ADX Continuation providers from an OhlcvDataset.

    Delegates to experiments/h13_adx_continuation/providers.py.
    strategy_name: "adx_continuation"
    """

    def create_providers(
        self,
        dataset: OhlcvDataset,
        wf_config: WalkForwardConfig,
    ) -> tuple[FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner]:
        candles = list(dataset.candles)

        feature_provider = H13FeatureProvider(candles)
        regime_provider = H13RegimeProvider()
        strategy_runner = H13StrategyRunner(
            wf_engine=WalkForwardEngine(WalkForwardWindowGenerator(wf_config)),
            cost_engine=ExecutionCostEngine(),
        )
        validation_runner = ValidationReportAdapter(
            builder=ValidationReportBuilder(),
            evaluator=lambda result: result.get("profitable", False),
        )

        return feature_provider, regime_provider, strategy_runner, validation_runner


class RegistryInfoProviderAdapter:
    """Adapts HypothesisRegistry to the HypothesisInfoProvider Protocol.

    HypothesisRegistry has no get_info() method. This adapter bridges the gap
    without modifying Core. Missing hypothesis_ids are silently omitted per the
    HypothesisInfoProvider contract.
    """

    def __init__(self, registry: HypothesisRegistry) -> None:
        self._registry = registry

    def get_info(self, hypothesis_ids: list[str]) -> dict[str, HypothesisInfo]:
        result: dict[str, HypothesisInfo] = {}
        for h_id in hypothesis_ids:
            try:
                h = self._registry.get(h_id)
                result[h_id] = HypothesisInfo(
                    hypothesis_id=h.id,
                    title=h.title,
                    template_id=h.metadata.get("template_id"),
                )
            except KeyError:
                pass
        return result
