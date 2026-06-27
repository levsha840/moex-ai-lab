from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from core.hypothesis.models import HypothesisStatus
from core.hypothesis.service import HypothesisRegistry
from core.research_pipeline.pipeline import ResearchPipeline

from .models import (
    FailureAction,
    OrchestrationResult,
    OrchestrationStatus,
    ResearchPlan,
    ResearchTaskStatus,
    ResearchTaskSummary,
)
from .policy import DefaultResearchPolicy
from .protocols import ResearchPolicy

# Hypotheses in these statuses are eligible to start research.
# Any other status (RESEARCH, BACKTEST, …, ARCHIVED, REJECTED) causes a SKIPPED task.
_STARTABLE: frozenset[HypothesisStatus] = frozenset(
    {HypothesisStatus.IDEA, HypothesisStatus.DRAFT}
)


class ResearchOrchestrator:
    """Sequence executor for research tasks.

    Iterates through plan.tasks in order, advances each hypothesis to RESEARCH,
    delegates execution to ResearchPipeline, and applies ResearchPolicy on failure.

    Makes no decisions about *what* to run — that is the caller's responsibility.
    KnowledgeBase is not a dependency; it is written by ResearchPipeline internally.
    """

    def __init__(self, *, _clock: Callable[[], datetime] | None = None) -> None:
        self._clock: Callable[[], datetime] = _clock or (
            lambda: datetime.now(timezone.utc)
        )

    def run(
        self,
        plan: ResearchPlan,
        registry: HypothesisRegistry,
        pipeline: ResearchPipeline,
        *,
        policy: ResearchPolicy | None = None,
    ) -> OrchestrationResult:
        if policy is None:
            policy = DefaultResearchPolicy()

        session_id = uuid4().hex
        started_at = self._clock()
        consecutive_failures = 0
        final_status = OrchestrationStatus.COMPLETED

        for task in plan.tasks:
            if task.status != ResearchTaskStatus.PENDING:
                continue

            # Retrieve hypothesis — skip the task if not found
            try:
                hypothesis = registry.get(task.hypothesis_id)
            except KeyError:
                task.mark_skipped()
                continue

            # Skip if hypothesis is already in RESEARCH or beyond
            if hypothesis.status not in _STARTABLE:
                task.mark_skipped()
                continue

            # Policy gate: check whether we should proceed at all
            if not policy.should_continue(
                completed=sum(1 for t in plan.tasks if t.status == ResearchTaskStatus.COMPLETED),
                failed=sum(1 for t in plan.tasks if t.status == ResearchTaskStatus.FAILED),
                skipped=sum(1 for t in plan.tasks if t.status == ResearchTaskStatus.SKIPPED),
            ):
                task.mark_skipped()
                for remaining in plan.tasks:
                    if remaining.status == ResearchTaskStatus.PENDING:
                        remaining.mark_skipped()
                final_status = OrchestrationStatus.ABORTED
                break

            task.mark_in_progress(self._clock())
            try:
                # HypothesisRegistry enforces strictly-forward transitions one step at a time.
                # IDEA requires two moves; DRAFT requires one.
                if hypothesis.status == HypothesisStatus.IDEA:
                    registry.move_to(task.hypothesis_id, HypothesisStatus.DRAFT)
                registry.move_to(task.hypothesis_id, HypothesisStatus.RESEARCH)
                hypothesis = registry.get(task.hypothesis_id)

                result = pipeline.run(hypothesis, task.experiment_config)

                validation = result.experiment_result.validation
                summary = ResearchTaskSummary(
                    knowledge_entry_id=result.knowledge_entry.id,
                    pass_rate=validation.pass_rate if validation is not None else None,
                    windows_total=validation.windows_total if validation is not None else 0,
                )
                task.mark_completed(summary, self._clock())
                consecutive_failures = 0

            except Exception as exc:
                task.mark_failed(str(exc), self._clock())
                consecutive_failures += 1
                action = policy.on_task_failure(consecutive_failures)
                if action == FailureAction.ABORT:
                    for remaining in plan.tasks:
                        if remaining.status == ResearchTaskStatus.PENDING:
                            remaining.mark_skipped()
                    final_status = OrchestrationStatus.ABORTED
                    break

        finished_at = self._clock()
        return OrchestrationResult(
            session_id=session_id,
            plan=plan,
            completed_tasks=tuple(
                t for t in plan.tasks if t.status == ResearchTaskStatus.COMPLETED
            ),
            failed_tasks=tuple(
                t for t in plan.tasks if t.status == ResearchTaskStatus.FAILED
            ),
            skipped_tasks=tuple(
                t for t in plan.tasks if t.status == ResearchTaskStatus.SKIPPED
            ),
            started_at=started_at,
            finished_at=finished_at,
            final_status=final_status,
        )
