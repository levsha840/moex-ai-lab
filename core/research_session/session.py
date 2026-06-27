"""Research Session — orchestration facade for a full research campaign."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from core.hypothesis.service import HypothesisRegistry
from core.hypothesis_generator.engine import HypothesisGenerator
from core.research_orchestrator.models import (
    OrchestrationStatus,
    ResearchPlan,
    ResearchTask,
)
from core.research_orchestrator.protocols import ResearchPolicy
from core.research_pipeline.pipeline import ResearchPipeline
from core.research_session.models import (
    ResearchSessionConfig,
    ResearchSessionResult,
    ResearchSessionStatus,
    SessionStatistics,
)
from core.research_session.protocols import PlanExecutor

# Local copy of the validation pass threshold.
# Must match ValidationReportBuilder._PASS_THRESHOLD = 0.80 (see OQ-007).
_VALIDATION_PASS_THRESHOLD: float = 0.80


class ResearchSession:
    """Orchestration facade for a full hypothesis research campaign.

    Coordinates HypothesisGenerator → accept_all → ResearchPlan → PlanExecutor
    and aggregates results into ResearchSessionResult.

    Makes no decisions about which hypotheses to run (GenerationConfig controls that),
    which order to run them (KnowledgeRanker + HypothesisGenerator control that),
    or what constitutes a passing experiment (Validation Core controls that).

    KnowledgeBase is NOT a direct dependency — it is written by ResearchPipeline
    internally and read via KBTemplateStatisticsProvider inside HypothesisGenerator.
    """

    def __init__(
        self,
        generator: HypothesisGenerator,
        executor: PlanExecutor,
        *,
        _clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._generator = generator
        self._executor = executor
        self._clock: Callable[[], datetime] = _clock or (
            lambda: datetime.now(timezone.utc)
        )

    def run(
        self,
        config: ResearchSessionConfig,
        registry: HypothesisRegistry,
        pipeline: ResearchPipeline,
        *,
        policy: ResearchPolicy | None = None,
    ) -> ResearchSessionResult:
        """Execute a full research campaign defined by config.

        Flow:
          1. Generate ranked candidates (HypothesisGenerator).
          2. Accept all candidates into HypothesisRegistry (accept_all).
          3. Build ResearchPlan from accepted hypotheses.
          4. Execute plan via PlanExecutor.
          5. Aggregate OrchestrationResult into ResearchSessionResult.

        Raises any unexpected exception from step 1–4 without wrapping it.
        A policy-driven ABORT is not an exception — it returns ABORTED status.
        """
        session_id = uuid4().hex
        started_at = self._clock()

        gen_session = self._generator.generate(config.generation_config)

        hypotheses = self._generator.accept_all(gen_session, registry)

        tasks = tuple(
            ResearchTask(
                hypothesis_id=h.id,
                experiment_config=config.experiment_config,
            )
            for h in hypotheses
        )
        plan = ResearchPlan(tasks=tasks, description=config.description)

        orch_result = self._executor.run(plan, registry, pipeline, policy=policy)

        finished_at = self._clock()
        stats = _build_statistics(gen_session, hypotheses, orch_result, started_at, finished_at)
        status = _map_status(orch_result.final_status)

        return ResearchSessionResult(
            session_id=session_id,
            config=config,
            orchestration_result=orch_result,
            statistics=stats,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _map_status(orch_status: OrchestrationStatus) -> ResearchSessionStatus:
    if orch_status == OrchestrationStatus.COMPLETED:
        return ResearchSessionStatus.COMPLETED
    return ResearchSessionStatus.ABORTED


def _build_statistics(gen_session, hypotheses, orch_result, started_at, finished_at):
    completed = orch_result.completed_tasks

    validation_pass = 0
    validation_fail = 0
    validation_inconclusive = 0
    pass_rates: list[float] = []
    kb_entries_created = 0

    for task in completed:
        if task.summary is not None and task.summary.knowledge_entry_id:
            kb_entries_created += 1

        if task.summary is None or task.summary.pass_rate is None:
            validation_inconclusive += 1
        elif task.summary.pass_rate >= _VALIDATION_PASS_THRESHOLD:
            validation_pass += 1
            pass_rates.append(task.summary.pass_rate)
        else:
            validation_fail += 1
            pass_rates.append(task.summary.pass_rate)

    avg_pass_rate = sum(pass_rates) / len(pass_rates) if pass_rates else None

    return SessionStatistics(
        candidates_generated=len(gen_session.generated_candidates),
        hypotheses_accepted=len(hypotheses),
        tasks_completed=len(completed),
        tasks_failed=len(orch_result.failed_tasks),
        tasks_skipped=len(orch_result.skipped_tasks),
        validation_pass=validation_pass,
        validation_fail=validation_fail,
        validation_inconclusive=validation_inconclusive,
        avg_pass_rate=avg_pass_rate,
        kb_entries_created=kb_entries_created,
        duration_seconds=(finished_at - started_at).total_seconds(),
    )
