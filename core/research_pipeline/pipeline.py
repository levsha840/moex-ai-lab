from __future__ import annotations

from dataclasses import dataclass

from core.experiment.engine import ExperimentRunner
from core.experiment.models import ExperimentConfig, ExperimentResult
from core.hypothesis.models import Hypothesis
from core.knowledge.models import KnowledgeEntry, KnowledgeType
from core.knowledge.service import KnowledgeBase
from core.validation.models import ValidationStatus


@dataclass
class ResearchPipelineResult:
    hypothesis_id: str
    experiment_result: ExperimentResult
    knowledge_entry: KnowledgeEntry


class ResearchPipeline:
    """Orchestrates a single end-to-end research cycle.

    Runs an experiment via ExperimentRunner, then persists the outcome to
    KnowledgeBase. Contains no business logic — only wires existing engines.

    If ExperimentRunner raises, the exception propagates unchanged and nothing
    is written to KnowledgeBase.
    """

    def __init__(
        self,
        experiment_runner: ExperimentRunner,
        knowledge_base: KnowledgeBase,
    ) -> None:
        self._runner = experiment_runner
        self._kb = knowledge_base

    def run(
        self,
        hypothesis: Hypothesis,
        experiment_config: ExperimentConfig,
    ) -> ResearchPipelineResult:
        experiment_result = self._runner.run(experiment_config)

        validation = experiment_result.validation
        validation_status = (
            validation.status.value if validation is not None else "N/A"
        )

        knowledge_entry = self._kb.record(
            knowledge_type=KnowledgeType.EXPERIMENT,
            reference_id=hypothesis.id,
            summary=(
                f"[{experiment_config.experiment_id}] "
                f"strategy={experiment_config.strategy_name} "
                f"validation={validation_status}"
            ),
            tags=[
                hypothesis.status.value,
                experiment_config.strategy_name,
                validation_status,
            ],
            metadata={
                "experiment_id": experiment_config.experiment_id,
                "hypothesis_id": hypothesis.id,
                "dataset_id": experiment_config.dataset_id,
                "stage": experiment_result.stage.value,
                "validation_status": validation_status,
            },
        )

        return ResearchPipelineResult(
            hypothesis_id=hypothesis.id,
            experiment_result=experiment_result,
            knowledge_entry=knowledge_entry,
        )
