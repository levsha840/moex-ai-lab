"""Domain models for the Research Session Module."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.experiment.models import ExperimentConfig
from core.hypothesis_generator.models import GenerationConfig
from core.research_orchestrator.models import OrchestrationResult


class ResearchSessionStatus(str, Enum):
    CREATED   = "CREATED"    # instance created, run() not yet called
    RUNNING   = "RUNNING"    # run() is executing
    COMPLETED = "COMPLETED"  # orchestrator returned OrchestrationStatus.COMPLETED
    ABORTED   = "ABORTED"    # orchestrator returned OrchestrationStatus.ABORTED (policy)
    FAILED    = "FAILED"     # unexpected exception from generator or executor


@dataclass(frozen=True)
class ResearchSessionConfig:
    """Immutable configuration for a single research session run.

    One ExperimentConfig applies to all hypotheses generated in the session.
    For per-hypothesis configuration, see OQ-008.

    pass_threshold defines what constitutes a PASS in SessionStatistics and
    ResearchReport findings. Single source of truth (ADR-0017, resolves TD-001).
    """

    generation_config: GenerationConfig
    experiment_config: ExperimentConfig
    description: str = ""
    pass_threshold: float = 0.80

    def __post_init__(self) -> None:
        if not 0.0 < self.pass_threshold <= 1.0:
            raise ValueError(
                f"pass_threshold must be in (0.0, 1.0], got {self.pass_threshold}"
            )


@dataclass(frozen=True)
class SessionStatistics:
    """Aggregate metrics from a completed ResearchSession.

    Provides raw counts for direct use by dashboards and future reporting (4.4).
    Interpretation and ranking belong to ResearchReportBuilder, not here.
    """

    candidates_generated:    int           # len(GenerationSession.generated_candidates)
    hypotheses_accepted:     int           # candidates successfully accepted into Registry
    tasks_completed:         int           # ResearchTaskStatus.COMPLETED
    tasks_failed:            int           # ResearchTaskStatus.FAILED (pipeline exception)
    tasks_skipped:           int           # ResearchTaskStatus.SKIPPED
    validation_pass:         int           # completed tasks where pass_rate >= config.pass_threshold
    validation_fail:         int           # completed tasks where pass_rate < config.pass_threshold
    validation_inconclusive: int           # completed tasks where pass_rate is None
    avg_pass_rate:           float | None  # mean of non-None pass_rates; None if none exist
    kb_entries_created:      int           # completed tasks with a knowledge_entry_id
    duration_seconds:        float

    @property
    def validation_pass_rate(self) -> float | None:
        """Fraction of conclusive experiments that passed validation.

        Denominator: validation_pass + validation_fail (excludes inconclusive).
        Returns None when no conclusive experiments exist.
        """
        conclusive = self.validation_pass + self.validation_fail
        if conclusive == 0:
            return None
        return self.validation_pass / conclusive


@dataclass(frozen=True)
class ResearchSessionResult:
    """Immutable snapshot of a completed research session."""

    session_id:           str
    config:               ResearchSessionConfig
    orchestration_result: OrchestrationResult   # full raw result for downstream use
    statistics:           SessionStatistics
    started_at:           datetime
    finished_at:          datetime
    status:               ResearchSessionStatus
