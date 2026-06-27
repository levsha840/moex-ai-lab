"""Research Report Builder (Capability 4.4)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from core.research_orchestrator.models import ResearchTaskStatus
from core.research_session.models import ResearchSessionResult, ResearchSessionStatus
from core.research_session.protocols import HypothesisInfoProvider
from core.research_session.report_models import (
    HypothesisInfo,
    RecommendationKind,
    RecommendationPriority,
    RecommendationScope,
    ReportSummary,
    ResearchFinding,
    ResearchRecommendation,
    ResearchReport,
    ValidationOutcome,
)


class ResearchReportBuilder:
    """Produces a ResearchReport from a ResearchSessionResult.

    Stateless across calls: build() has no side effects and does not modify
    any input object. Repeated calls with the same result produce structurally
    identical reports (report_id will differ; all other fields are deterministic).

    No dependency on KnowledgeBase, ResearchPipeline, or ExperimentRunner.
    Hypothesis titles are resolved via HypothesisInfoProvider Protocol (ADR-0016).
    """

    def __init__(
        self,
        *,
        info_provider: HypothesisInfoProvider | None = None,
        _clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._info_provider = info_provider
        self._clock: Callable[[], datetime] = _clock or (
            lambda: datetime.now(timezone.utc)
        )

    def build(self, result: ResearchSessionResult) -> ResearchReport:
        """Build a ResearchReport from a completed ResearchSessionResult.

        Findings are ordered by ResearchPlan.tasks order (plan order, not completion order).
        Recommendations are ordered by priority (HIGH → MEDIUM → LOW), then by kind.
        """
        generated_at = self._clock()
        pass_threshold = result.config.pass_threshold

        all_ids = [t.hypothesis_id for t in result.orchestration_result.plan.tasks]
        info_map = self._load_info(all_ids)

        findings = tuple(
            self._build_finding(task, pass_threshold, info_map)
            for task in result.orchestration_result.plan.tasks
        )

        summary = _build_summary(result, findings, pass_threshold)
        recommendations = _build_recommendations(findings, result.status, pass_threshold)

        return ResearchReport(
            report_id=uuid4().hex,
            generated_at=generated_at,
            session_id=result.session_id,
            summary=summary,
            findings=findings,
            recommendations=recommendations,
        )

    # ──────────────────────────────────────────────────────────────────────────

    def _load_info(self, hypothesis_ids: list[str]) -> dict[str, HypothesisInfo]:
        if self._info_provider is None or not hypothesis_ids:
            return {}
        return self._info_provider.get_info(hypothesis_ids)

    def _build_finding(
        self,
        task,
        pass_threshold: float,
        info_map: dict[str, HypothesisInfo],
    ) -> ResearchFinding:
        info = info_map.get(task.hypothesis_id)
        title = info.title if info else "(unknown)"
        template_id = info.template_id if info else None

        if task.status == ResearchTaskStatus.SKIPPED:
            return ResearchFinding(
                hypothesis_id=task.hypothesis_id,
                hypothesis_title=title,
                template_id=template_id,
                outcome=ValidationOutcome.SKIPPED,
                pass_rate=None,
                windows_total=0,
                knowledge_entry_id=None,
                strategy_name=task.experiment_config.strategy_name,
                rationale="Task was skipped: session was aborted before this task could start.",
            )

        if task.status == ResearchTaskStatus.FAILED:
            return ResearchFinding(
                hypothesis_id=task.hypothesis_id,
                hypothesis_title=title,
                template_id=template_id,
                outcome=ValidationOutcome.ERROR,
                pass_rate=None,
                windows_total=0,
                knowledge_entry_id=None,
                strategy_name=task.experiment_config.strategy_name,
                rationale=f"Pipeline exception: {task.failure_reason!r}.",
            )

        # COMPLETED
        s = task.summary
        pass_rate = s.pass_rate if s else None
        windows_total = s.windows_total if s else 0
        knowledge_entry_id = s.knowledge_entry_id if s else None

        if pass_rate is None:
            return ResearchFinding(
                hypothesis_id=task.hypothesis_id,
                hypothesis_title=title,
                template_id=template_id,
                outcome=ValidationOutcome.INCONCLUSIVE,
                pass_rate=None,
                windows_total=windows_total,
                knowledge_entry_id=knowledge_entry_id,
                strategy_name=task.experiment_config.strategy_name,
                rationale=(
                    f"Experiment completed but validation produced no pass_rate "
                    f"(windows_total={windows_total})."
                ),
            )

        if pass_rate >= pass_threshold:
            return ResearchFinding(
                hypothesis_id=task.hypothesis_id,
                hypothesis_title=title,
                template_id=template_id,
                outcome=ValidationOutcome.PASS,
                pass_rate=pass_rate,
                windows_total=windows_total,
                knowledge_entry_id=knowledge_entry_id,
                strategy_name=task.experiment_config.strategy_name,
                rationale=(
                    f"pass_rate={pass_rate:.2f} (>= {pass_threshold:.2f} threshold) "
                    f"over {windows_total} windows. "
                    f"KnowledgeBase entry: {knowledge_entry_id}."
                ),
            )

        return ResearchFinding(
            hypothesis_id=task.hypothesis_id,
            hypothesis_title=title,
            template_id=template_id,
            outcome=ValidationOutcome.FAIL,
            pass_rate=pass_rate,
            windows_total=windows_total,
            knowledge_entry_id=knowledge_entry_id,
            strategy_name=task.experiment_config.strategy_name,
            rationale=(
                f"pass_rate={pass_rate:.2f} (< {pass_threshold:.2f} threshold) "
                f"over {windows_total} windows."
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_summary(
    result: ResearchSessionResult,
    findings: tuple[ResearchFinding, ...],
    pass_threshold: float,
) -> ReportSummary:
    pass_count        = sum(1 for f in findings if f.outcome == ValidationOutcome.PASS)
    fail_count        = sum(1 for f in findings if f.outcome == ValidationOutcome.FAIL)
    inconclusive      = sum(1 for f in findings if f.outcome == ValidationOutcome.INCONCLUSIVE)
    error_count       = sum(1 for f in findings if f.outcome == ValidationOutcome.ERROR)
    skipped_count     = sum(1 for f in findings if f.outcome == ValidationOutcome.SKIPPED)
    kb_entries        = sum(1 for f in findings if f.knowledge_entry_id is not None)

    conclusive = pass_count + fail_count
    validation_pass_rate = pass_count / conclusive if conclusive > 0 else None

    rates = [f.pass_rate for f in findings if f.pass_rate is not None]
    avg_pass_rate = sum(rates) / len(rates) if rates else None
    median_pass_rate = _compute_median(rates)

    return ReportSummary(
        session_id=result.session_id,
        description=result.config.description,
        status=result.status,
        total_hypotheses=len(findings),
        pass_count=pass_count,
        fail_count=fail_count,
        inconclusive_count=inconclusive,
        error_count=error_count,
        skipped_count=skipped_count,
        validation_pass_rate=validation_pass_rate,
        avg_pass_rate=avg_pass_rate,
        median_pass_rate=median_pass_rate,
        kb_entries_created=kb_entries,
        duration_seconds=result.statistics.duration_seconds,
        pass_threshold=pass_threshold,
    )


def _build_recommendations(
    findings: tuple[ResearchFinding, ...],
    session_status: ResearchSessionStatus,
    pass_threshold: float,
) -> tuple[ResearchRecommendation, ...]:
    recs: list[ResearchRecommendation] = []

    # ── Session-level (scope = SESSION) ──────────────────────────────────────

    error_findings = [f for f in findings if f.outcome == ValidationOutcome.ERROR]
    if error_findings:
        recs.append(ResearchRecommendation(
            kind=RecommendationKind.INVESTIGATE_PIPELINE,
            scope=RecommendationScope.SESSION,
            hypothesis_id=None,
            rationale=(
                f"{len(error_findings)} task(s) failed with pipeline exceptions. "
                "Investigate pipeline configuration before re-running these hypotheses."
            ),
            priority=RecommendationPriority.HIGH,
        ))

    skipped_findings = [f for f in findings if f.outcome == ValidationOutcome.SKIPPED]
    if skipped_findings:
        recs.append(ResearchRecommendation(
            kind=RecommendationKind.RESCHEDULE_SKIPPED,
            scope=RecommendationScope.SESSION,
            hypothesis_id=None,
            rationale=(
                f"{len(skipped_findings)} task(s) were skipped due to session abort. "
                "Reschedule in a new ResearchSession."
            ),
            priority=RecommendationPriority.MEDIUM,
        ))

    # ── Per-hypothesis (scope = HYPOTHESIS) ──────────────────────────────────

    for finding in findings:
        rec = _recommend_for_finding(finding, pass_threshold)
        if rec is not None:
            recs.append(rec)

    # Stable order: HIGH before MEDIUM before LOW, then by kind
    _PRIORITY_ORDER = {
        RecommendationPriority.HIGH: 0,
        RecommendationPriority.MEDIUM: 1,
        RecommendationPriority.LOW: 2,
    }
    recs.sort(key=lambda r: (_PRIORITY_ORDER[r.priority], r.kind.value))

    return tuple(recs)


def _recommend_for_finding(
    finding: ResearchFinding,
    pass_threshold: float,
) -> ResearchRecommendation | None:
    """Return a per-hypothesis recommendation or None if no action is warranted."""

    if finding.outcome == ValidationOutcome.PASS:
        # Marginal PASS (within 10pp above threshold): recommend repeat to confirm.
        if finding.pass_rate is not None and finding.pass_rate < pass_threshold + 0.10:
            return ResearchRecommendation(
                kind=RecommendationKind.REPEAT_EXPERIMENT,
                scope=RecommendationScope.HYPOTHESIS,
                hypothesis_id=finding.hypothesis_id,
                rationale=(
                    f"pass_rate={finding.pass_rate:.2f} is within 10pp of threshold "
                    f"({pass_threshold:.2f}). Consider repeating to confirm the result."
                ),
                priority=RecommendationPriority.MEDIUM,
            )
        return None

    if finding.outcome == ValidationOutcome.FAIL:
        if finding.pass_rate is not None and finding.pass_rate < 0.50:
            return ResearchRecommendation(
                kind=RecommendationKind.ARCHIVE_HYPOTHESIS,
                scope=RecommendationScope.HYPOTHESIS,
                hypothesis_id=finding.hypothesis_id,
                rationale=(
                    f"pass_rate={finding.pass_rate:.2f} (< 0.50). "
                    "Low recovery probability — consider archiving this hypothesis."
                ),
                priority=RecommendationPriority.LOW,
            )
        return ResearchRecommendation(
            kind=RecommendationKind.EXPLORE_VARIANT,
            scope=RecommendationScope.HYPOTHESIS,
            hypothesis_id=finding.hypothesis_id,
            rationale=(
                f"pass_rate={finding.pass_rate:.2f} (failed threshold {pass_threshold:.2f}). "
                "Signal present but insufficient — consider exploring parameter variants."
            ),
            priority=RecommendationPriority.LOW,
        )

    if finding.outcome == ValidationOutcome.INCONCLUSIVE:
        return ResearchRecommendation(
            kind=RecommendationKind.REVIEW_PARAMETERS,
            scope=RecommendationScope.HYPOTHESIS,
            hypothesis_id=finding.hypothesis_id,
            rationale=(
                f"Experiment for hypothesis {finding.hypothesis_id!r} completed "
                "without producing a pass_rate. Review ExperimentConfig parameters."
            ),
            priority=RecommendationPriority.MEDIUM,
        )

    return None  # ERROR and SKIPPED are handled at session level


def _compute_median(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
