from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

from core.experiment.models import ExperimentConfig


class ResearchTaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class FailureAction(str, Enum):
    CONTINUE = "CONTINUE"
    ABORT = "ABORT"


class OrchestrationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class ResearchTaskSummary:
    """Lightweight reference to the outcome of a completed research task.

    Stores enough information for aggregate reporting without embedding the
    full ResearchPipelineResult. Full results are retrievable via KnowledgeBase
    using knowledge_entry_id.
    """

    knowledge_entry_id: str
    pass_rate: float | None  # None when experiment did not reach VALIDATED stage
    windows_total: int


@dataclass
class ResearchTask:
    """Unit of research work: one hypothesis paired with one ExperimentConfig.

    Lifecycle: PENDING → IN_PROGRESS → COMPLETED | FAILED | SKIPPED.
    Status transitions are enforced by the mark_* methods.
    """

    hypothesis_id: str
    experiment_config: ExperimentConfig
    task_id: str = field(default_factory=lambda: uuid4().hex)
    priority: int = 0
    status: ResearchTaskStatus = field(default=ResearchTaskStatus.PENDING)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: ResearchTaskSummary | None = None
    failure_reason: str | None = None

    def mark_in_progress(self, now: datetime) -> None:
        if self.status != ResearchTaskStatus.PENDING:
            raise ValueError(
                f"Cannot start task {self.task_id!r}: "
                f"expected PENDING, got {self.status.value!r}"
            )
        self.status = ResearchTaskStatus.IN_PROGRESS
        self.started_at = now

    def mark_completed(self, summary: ResearchTaskSummary, now: datetime) -> None:
        if self.status != ResearchTaskStatus.IN_PROGRESS:
            raise ValueError(
                f"Cannot complete task {self.task_id!r}: "
                f"expected IN_PROGRESS, got {self.status.value!r}"
            )
        self.status = ResearchTaskStatus.COMPLETED
        self.completed_at = now
        self.summary = summary

    def mark_failed(self, reason: str, now: datetime) -> None:
        if self.status != ResearchTaskStatus.IN_PROGRESS:
            raise ValueError(
                f"Cannot fail task {self.task_id!r}: "
                f"expected IN_PROGRESS, got {self.status.value!r}"
            )
        self.status = ResearchTaskStatus.FAILED
        self.completed_at = now
        self.failure_reason = reason

    def mark_skipped(self) -> None:
        if self.status != ResearchTaskStatus.PENDING:
            raise ValueError(
                f"Cannot skip task {self.task_id!r}: "
                f"expected PENDING, got {self.status.value!r}"
            )
        self.status = ResearchTaskStatus.SKIPPED


@dataclass(frozen=True)
class ResearchPlan:
    """Fixed, immutable scope of research work.

    Frozen at creation — tasks cannot be added or removed once the plan
    is passed to the orchestrator. New tasks require a new plan.
    """

    tasks: tuple[ResearchTask, ...]
    plan_id: str = field(default_factory=lambda: uuid4().hex)
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.tasks, tuple):
            raise ValueError(
                f"tasks must be a tuple, got {type(self.tasks).__name__!r}"
            )


@dataclass(frozen=True)
class OrchestrationResult:
    """Final immutable snapshot of a completed orchestration session."""

    session_id: str
    plan: ResearchPlan
    completed_tasks: tuple[ResearchTask, ...]
    failed_tasks: tuple[ResearchTask, ...]
    skipped_tasks: tuple[ResearchTask, ...]
    started_at: datetime
    finished_at: datetime
    final_status: OrchestrationStatus
