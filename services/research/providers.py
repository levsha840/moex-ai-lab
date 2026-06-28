from __future__ import annotations

from typing import Protocol

from core.experiment.protocols import FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner
from core.hypothesis.service import HypothesisRegistry
from core.research_session.report_models import HypothesisInfo
from core.walkforward.models import WalkForwardConfig

from services.research.dataset import OhlcvDataset


class StrategyProviderFactory(Protocol):
    """Creates 4 providers for ExperimentRunner from a loaded dataset.

    Implement this Protocol in the experiment package, then register the
    dotted class path in hypotheses/<name>.yaml under `provider_factory`.
    """

    def create_providers(
        self,
        dataset: OhlcvDataset,
        wf_config: WalkForwardConfig,
    ) -> tuple[FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner]: ...


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
