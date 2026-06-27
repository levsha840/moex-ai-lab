"""Domain models for Research Report (Capability 4.4)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.research_session.models import ResearchSessionStatus


class ValidationOutcome(str, Enum):
    """Semantic classification of a single research task outcome.

    Wraps ResearchTaskStatus + pass_rate into a single, report-facing enum.
    Decouples report consumers from task lifecycle internals.
    """

    PASS         = "PASS"           # pass_rate >= pass_threshold
    FAIL         = "FAIL"           # pass_rate < pass_threshold (not None)
    INCONCLUSIVE = "INCONCLUSIVE"   # pass_rate is None — experiment ran, no validation
    ERROR        = "ERROR"          # ResearchTaskStatus.FAILED (pipeline exception)
    SKIPPED      = "SKIPPED"        # ResearchTaskStatus.SKIPPED


class RecommendationKind(str, Enum):
    """Type of action recommended after analysis of research findings."""

    REPEAT_EXPERIMENT    = "REPEAT_EXPERIMENT"     # marginal result, worth confirming
    ARCHIVE_HYPOTHESIS   = "ARCHIVE_HYPOTHESIS"    # strong FAIL, low recovery probability
    EXPLORE_VARIANT      = "EXPLORE_VARIANT"       # FAIL with signal, try variations
    REVIEW_PARAMETERS    = "REVIEW_PARAMETERS"     # INCONCLUSIVE — ExperimentConfig issue
    INVESTIGATE_PIPELINE = "INVESTIGATE_PIPELINE"  # pipeline ERROR, not a hypothesis problem
    RESCHEDULE_SKIPPED   = "RESCHEDULE_SKIPPED"    # SKIPPED due to abort, still valid


class RecommendationPriority(str, Enum):
    """Relative priority of a recommendation for consumer sorting."""

    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


class RecommendationScope(str, Enum):
    """Whether the recommendation applies to a specific hypothesis or the whole session."""

    SESSION    = "SESSION"     # session-level concern; hypothesis_id is None
    HYPOTHESIS = "HYPOTHESIS"  # specific hypothesis; hypothesis_id is set


@dataclass(frozen=True)
class HypothesisInfo:
    """Lightweight hypothesis metadata for report building.

    Obtained via HypothesisInfoProvider Protocol. Contains only what
    ResearchReportBuilder needs — not the full Hypothesis lifecycle object.
    """

    hypothesis_id: str
    title: str
    template_id: str | None  # from hypothesis.metadata["template_id"]; None if absent


@dataclass(frozen=True)
class ResearchFinding:
    """Analysis of a single research task outcome.

    One Finding is produced per task in ResearchPlan.tasks (completed, failed, or skipped).
    All fields are derived from observed data only — no inference or speculation.
    """

    hypothesis_id:      str
    hypothesis_title:   str            # "(unknown)" if HypothesisInfoProvider returned no data
    template_id:        str | None     # from HypothesisInfo; None if unavailable
    outcome:            ValidationOutcome
    pass_rate:          float | None   # None for INCONCLUSIVE, ERROR, SKIPPED
    windows_total:      int            # 0 when task did not reach validation
    knowledge_entry_id: str | None     # present only when outcome is PASS or FAIL
    strategy_name:      str            # from ResearchTask.experiment_config.strategy_name
    rationale:          str            # rule-derived explanation using only observed fields


@dataclass(frozen=True)
class ResearchRecommendation:
    """Action recommendation derived from research findings.

    Strictly data-driven: each recommendation references an observable condition.
    No domain speculation, no new hypothesis generation.
    """

    kind:          RecommendationKind
    scope:         RecommendationScope
    hypothesis_id: str | None     # set when scope == HYPOTHESIS; None when scope == SESSION
    rationale:     str
    priority:      RecommendationPriority


@dataclass(frozen=True)
class ReportSummary:
    """Aggregate view of a research session for dashboards and human consumers.

    Counts are re-derived from ResearchFindings — the canonical source of truth
    in the report. duration_seconds and kb_entries_created come from SessionStatistics.
    """

    session_id:           str
    description:          str
    status:               ResearchSessionStatus
    total_hypotheses:     int
    pass_count:           int
    fail_count:           int
    inconclusive_count:   int
    error_count:          int
    skipped_count:        int
    validation_pass_rate: float | None  # pass / (pass + fail); None if no conclusive results
    avg_pass_rate:        float | None  # mean of non-None pass_rates (PASS + FAIL tasks only)
    median_pass_rate:     float | None  # median of same; more robust to outliers
    kb_entries_created:   int
    duration_seconds:     float
    pass_threshold:       float         # threshold used for PASS/FAIL classification


@dataclass(frozen=True)
class ResearchReport:
    """Immutable, deterministic report produced from a completed ResearchSession.

    ResearchReport is a pure data model — it contains no rendering logic.
    Markdown, HTML, JSON, or PDF representations are produced by ReportRenderer
    implementations (see Extension Point EP-01 in Phase 4 Baseline).

    session_id references the originating ResearchSessionResult rather than
    embedding the full object graph (Change 1 from architecture review).
    """

    report_id:       str                                   # uuid4().hex, unique per build()
    generated_at:    datetime
    session_id:      str                                   # links back to ResearchSessionResult
    summary:         ReportSummary
    findings:        tuple[ResearchFinding, ...]           # ordered by ResearchPlan.tasks order
    recommendations: tuple[ResearchRecommendation, ...]   # ordered by priority (HIGH first)
