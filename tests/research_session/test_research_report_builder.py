"""Tests for ResearchReportBuilder (Capability 4.4)."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from core.experiment.models import ExperimentConfig
from core.hypothesis_generator.models import GenerationConfig
from core.research_orchestrator.models import (
    OrchestrationResult,
    OrchestrationStatus,
    ResearchPlan,
    ResearchTask,
    ResearchTaskSummary,
)
from core.research_session.models import (
    ResearchSessionConfig,
    ResearchSessionResult,
    ResearchSessionStatus,
    SessionStatistics,
)
from core.research_session.report import ResearchReportBuilder
from core.research_session.report_models import (
    HypothesisInfo,
    RecommendationKind,
    RecommendationPriority,
    RecommendationScope,
    ValidationOutcome,
)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_TS  = datetime(2026, 1, 1, 12, 0, 0)
_TS2 = datetime(2026, 1, 1, 12, 0, 5)

_EXP_CONFIG = ExperimentConfig(
    experiment_id="exp_test",
    hypothesis_id="hyp_test",
    dataset_id="dataset_h13",
    strategy_name="adx_continuation",
    feature_set=["adx", "rsi"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Stubs
# ─────────────────────────────────────────────────────────────────────────────

class _StubInfoProvider:
    def __init__(self, info_map: dict[str, HypothesisInfo] | None = None) -> None:
        self._map: dict[str, HypothesisInfo] = info_map or {}
        self.calls: list[list[str]] = []

    def get_info(self, hypothesis_ids: list[str]) -> dict[str, HypothesisInfo]:
        self.calls.append(hypothesis_ids)
        return {h: self._map[h] for h in hypothesis_ids if h in self._map}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _completed_task(
    hypothesis_id: str | None = None,
    pass_rate: float | None = 0.9,
    windows_total: int = 10,
    knowledge_entry_id: str | None = None,
) -> ResearchTask:
    task = ResearchTask(
        hypothesis_id=hypothesis_id or uuid4().hex,
        experiment_config=_EXP_CONFIG,
    )
    task.mark_in_progress(_TS)
    task.mark_completed(
        ResearchTaskSummary(
            knowledge_entry_id=knowledge_entry_id or uuid4().hex,
            pass_rate=pass_rate,
            windows_total=windows_total,
        ),
        _TS,
    )
    return task


def _failed_task(hypothesis_id: str | None = None, reason: str = "Pipeline error") -> ResearchTask:
    task = ResearchTask(
        hypothesis_id=hypothesis_id or uuid4().hex,
        experiment_config=_EXP_CONFIG,
    )
    task.mark_in_progress(_TS)
    task.mark_failed(reason, _TS)
    return task


def _skipped_task(hypothesis_id: str | None = None) -> ResearchTask:
    task = ResearchTask(
        hypothesis_id=hypothesis_id or uuid4().hex,
        experiment_config=_EXP_CONFIG,
    )
    task.mark_skipped()
    return task


def _make_result(
    tasks: list[ResearchTask],
    final_status: OrchestrationStatus = OrchestrationStatus.COMPLETED,
    pass_threshold: float = 0.80,
    session_id: str | None = None,
    description: str = "Test campaign",
) -> ResearchSessionResult:
    from core.research_orchestrator.models import ResearchTaskStatus

    completed = tuple(t for t in tasks if t.status == ResearchTaskStatus.COMPLETED)
    failed    = tuple(t for t in tasks if t.status == ResearchTaskStatus.FAILED)
    skipped   = tuple(t for t in tasks if t.status == ResearchTaskStatus.SKIPPED)

    plan = ResearchPlan(tasks=tuple(tasks))
    orch_result = OrchestrationResult(
        session_id=uuid4().hex,
        plan=plan,
        completed_tasks=completed,
        failed_tasks=failed,
        skipped_tasks=skipped,
        started_at=_TS,
        finished_at=_TS2,
        final_status=final_status,
    )

    stats = SessionStatistics(
        candidates_generated=len(tasks),
        hypotheses_accepted=len(tasks),
        tasks_completed=len(completed),
        tasks_failed=len(failed),
        tasks_skipped=len(skipped),
        validation_pass=0,
        validation_fail=0,
        validation_inconclusive=0,
        avg_pass_rate=None,
        kb_entries_created=len(completed),
        duration_seconds=5.0,
    )

    config = ResearchSessionConfig(
        generation_config=GenerationConfig(max_candidates=max(1, len(tasks))),
        experiment_config=_EXP_CONFIG,
        description=description,
        pass_threshold=pass_threshold,
    )

    sess_status = (
        ResearchSessionStatus.COMPLETED
        if final_status == OrchestrationStatus.COMPLETED
        else ResearchSessionStatus.ABORTED
    )

    return ResearchSessionResult(
        session_id=session_id or uuid4().hex,
        config=config,
        orchestration_result=orch_result,
        statistics=stats,
        started_at=_TS,
        finished_at=_TS2,
        status=sess_status,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Empty session
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_session_produces_empty_report():
    result = _make_result([])
    report = ResearchReportBuilder().build(result)
    assert report.findings == ()
    assert report.recommendations == ()
    assert report.summary.total_hypotheses == 0


def test_empty_session_summary_rates_are_none():
    result = _make_result([])
    summary = ResearchReportBuilder().build(result).summary
    assert summary.validation_pass_rate is None
    assert summary.avg_pass_rate is None
    assert summary.median_pass_rate is None


# ─────────────────────────────────────────────────────────────────────────────
# Finding classification
# ─────────────────────────────────────────────────────────────────────────────

def test_pass_task_produces_pass_finding():
    task = _completed_task(pass_rate=0.90)
    result = _make_result([task])
    report = ResearchReportBuilder().build(result)
    assert len(report.findings) == 1
    assert report.findings[0].outcome == ValidationOutcome.PASS
    assert report.findings[0].pass_rate == pytest.approx(0.90)


def test_fail_task_produces_fail_finding():
    task = _completed_task(pass_rate=0.70)
    result = _make_result([task])
    report = ResearchReportBuilder().build(result)
    assert report.findings[0].outcome == ValidationOutcome.FAIL


def test_exact_threshold_is_pass():
    task = _completed_task(pass_rate=0.80)
    result = _make_result([task], pass_threshold=0.80)
    report = ResearchReportBuilder().build(result)
    assert report.findings[0].outcome == ValidationOutcome.PASS


def test_inconclusive_task_produces_inconclusive_finding():
    task = _completed_task(pass_rate=None)
    result = _make_result([task])
    report = ResearchReportBuilder().build(result)
    assert report.findings[0].outcome == ValidationOutcome.INCONCLUSIVE
    assert report.findings[0].pass_rate is None


def test_failed_pipeline_task_produces_error_finding():
    task = _failed_task()
    result = _make_result([task])
    report = ResearchReportBuilder().build(result)
    assert report.findings[0].outcome == ValidationOutcome.ERROR
    assert report.findings[0].pass_rate is None


def test_skipped_task_produces_skipped_finding():
    task = _skipped_task()
    result = _make_result([task])
    report = ResearchReportBuilder().build(result)
    assert report.findings[0].outcome == ValidationOutcome.SKIPPED
    assert report.findings[0].pass_rate is None


def test_findings_preserve_plan_order():
    h1 = uuid4().hex
    h2 = uuid4().hex
    h3 = uuid4().hex
    tasks = [
        _completed_task(hypothesis_id=h1, pass_rate=0.90),
        _completed_task(hypothesis_id=h2, pass_rate=0.60),
        _skipped_task(hypothesis_id=h3),
    ]
    result = _make_result(tasks)
    report = ResearchReportBuilder().build(result)
    ids = [f.hypothesis_id for f in report.findings]
    assert ids == [h1, h2, h3]


# ─────────────────────────────────────────────────────────────────────────────
# Rationale content
# ─────────────────────────────────────────────────────────────────────────────

def test_pass_finding_rationale_contains_pass_rate_and_threshold():
    task = _completed_task(pass_rate=0.90)
    report = ResearchReportBuilder().build(_make_result([task]))
    rationale = report.findings[0].rationale
    assert "0.90" in rationale
    assert "0.80" in rationale


def test_fail_finding_rationale_contains_pass_rate_and_threshold():
    task = _completed_task(pass_rate=0.70)
    report = ResearchReportBuilder().build(_make_result([task]))
    rationale = report.findings[0].rationale
    assert "0.70" in rationale
    assert "0.80" in rationale


def test_error_finding_rationale_contains_failure_reason():
    task = _failed_task(reason="NaN in features")
    report = ResearchReportBuilder().build(_make_result([task]))
    assert "NaN in features" in report.findings[0].rationale


# ─────────────────────────────────────────────────────────────────────────────
# HypothesisInfoProvider
# ─────────────────────────────────────────────────────────────────────────────

def test_without_info_provider_title_is_unknown():
    task = _completed_task()
    report = ResearchReportBuilder().build(_make_result([task]))
    assert report.findings[0].hypothesis_title == "(unknown)"
    assert report.findings[0].template_id is None


def test_with_info_provider_title_and_template_resolved():
    h_id = "hyp_42"
    info = HypothesisInfo(hypothesis_id=h_id, title="ADX Continuation", template_id="tmpl_h13")
    provider = _StubInfoProvider({h_id: info})
    task = _completed_task(hypothesis_id=h_id)
    report = ResearchReportBuilder(info_provider=provider).build(_make_result([task]))
    assert report.findings[0].hypothesis_title == "ADX Continuation"
    assert report.findings[0].template_id == "tmpl_h13"


def test_info_provider_called_with_all_hypothesis_ids():
    ids = [uuid4().hex for _ in range(3)]
    tasks = [_completed_task(hypothesis_id=h) for h in ids]
    provider = _StubInfoProvider()
    ResearchReportBuilder(info_provider=provider).build(_make_result(tasks))
    assert len(provider.calls) == 1
    assert set(provider.calls[0]) == set(ids)


def test_missing_hypothesis_in_provider_falls_back_to_unknown():
    h_known = "hyp_known"
    h_unknown = "hyp_unknown"
    info = HypothesisInfo(hypothesis_id=h_known, title="Known", template_id=None)
    provider = _StubInfoProvider({h_known: info})
    tasks = [
        _completed_task(hypothesis_id=h_known),
        _completed_task(hypothesis_id=h_unknown),
    ]
    report = ResearchReportBuilder(info_provider=provider).build(_make_result(tasks))
    titles = {f.hypothesis_id: f.hypothesis_title for f in report.findings}
    assert titles[h_known] == "Known"
    assert titles[h_unknown] == "(unknown)"


# ─────────────────────────────────────────────────────────────────────────────
# Summary aggregation
# ─────────────────────────────────────────────────────────────────────────────

def test_summary_counts_match_findings():
    tasks = [
        _completed_task(pass_rate=0.90),   # PASS
        _completed_task(pass_rate=0.90),   # PASS
        _completed_task(pass_rate=0.70),   # FAIL
        _completed_task(pass_rate=None),   # INCONCLUSIVE
        _failed_task(),                    # ERROR
        _skipped_task(),                   # SKIPPED
    ]
    summary = ResearchReportBuilder().build(_make_result(tasks)).summary
    assert summary.pass_count == 2
    assert summary.fail_count == 1
    assert summary.inconclusive_count == 1
    assert summary.error_count == 1
    assert summary.skipped_count == 1
    assert summary.total_hypotheses == 6


def test_summary_validation_pass_rate():
    tasks = [
        _completed_task(pass_rate=0.90),  # PASS
        _completed_task(pass_rate=0.90),  # PASS
        _completed_task(pass_rate=0.70),  # FAIL
    ]
    summary = ResearchReportBuilder().build(_make_result(tasks)).summary
    assert summary.validation_pass_rate == pytest.approx(2 / 3)


def test_summary_validation_pass_rate_none_when_all_inconclusive():
    tasks = [_completed_task(pass_rate=None), _completed_task(pass_rate=None)]
    summary = ResearchReportBuilder().build(_make_result(tasks)).summary
    assert summary.validation_pass_rate is None


def test_summary_avg_pass_rate():
    tasks = [
        _completed_task(pass_rate=0.90),
        _completed_task(pass_rate=0.70),
    ]
    summary = ResearchReportBuilder().build(_make_result(tasks)).summary
    assert summary.avg_pass_rate == pytest.approx(0.80)


def test_summary_median_pass_rate_odd():
    tasks = [
        _completed_task(pass_rate=0.70),
        _completed_task(pass_rate=0.90),
        _completed_task(pass_rate=0.80),
    ]
    summary = ResearchReportBuilder().build(_make_result(tasks)).summary
    assert summary.median_pass_rate == pytest.approx(0.80)


def test_summary_median_pass_rate_even():
    tasks = [
        _completed_task(pass_rate=0.70),
        _completed_task(pass_rate=0.90),
    ]
    summary = ResearchReportBuilder().build(_make_result(tasks)).summary
    assert summary.median_pass_rate == pytest.approx(0.80)


def test_summary_median_pass_rate_single_value():
    task = _completed_task(pass_rate=0.85)
    summary = ResearchReportBuilder().build(_make_result([task])).summary
    assert summary.median_pass_rate == pytest.approx(0.85)


def test_summary_session_id_matches_result():
    sess_id = uuid4().hex
    result = _make_result([], session_id=sess_id)
    report = ResearchReportBuilder().build(result)
    assert report.summary.session_id == sess_id
    assert report.session_id == sess_id


def test_summary_pass_threshold_from_config():
    result = _make_result([], pass_threshold=0.75)
    summary = ResearchReportBuilder().build(result).summary
    assert summary.pass_threshold == pytest.approx(0.75)


def test_custom_pass_threshold_affects_classification():
    task = _completed_task(pass_rate=0.72)
    result_strict = _make_result([task], pass_threshold=0.80)
    result_lenient = _make_result([task], pass_threshold=0.70)

    assert ResearchReportBuilder().build(result_strict).findings[0].outcome == ValidationOutcome.FAIL
    # Task's pass_rate=0.72 >= threshold 0.70 → PASS in lenient config
    assert ResearchReportBuilder().build(result_lenient).findings[0].outcome == ValidationOutcome.PASS


# ─────────────────────────────────────────────────────────────────────────────
# Recommendations
# ─────────────────────────────────────────────────────────────────────────────

def test_no_recommendations_for_clean_pass_session():
    tasks = [_completed_task(pass_rate=0.95)]  # Strong PASS (above threshold + 10pp)
    report = ResearchReportBuilder().build(_make_result(tasks))
    assert report.recommendations == ()


def test_marginal_pass_generates_repeat_experiment():
    task = _completed_task(pass_rate=0.83)   # Within 10pp of 0.80 threshold
    report = ResearchReportBuilder().build(_make_result([task], pass_threshold=0.80))
    kinds = [r.kind for r in report.recommendations]
    assert RecommendationKind.REPEAT_EXPERIMENT in kinds
    repeat = next(r for r in report.recommendations if r.kind == RecommendationKind.REPEAT_EXPERIMENT)
    assert repeat.scope == RecommendationScope.HYPOTHESIS
    assert repeat.priority == RecommendationPriority.MEDIUM
    assert repeat.hypothesis_id == task.hypothesis_id


def test_fail_above_050_generates_explore_variant():
    task = _completed_task(pass_rate=0.65)
    report = ResearchReportBuilder().build(_make_result([task]))
    kinds = [r.kind for r in report.recommendations]
    assert RecommendationKind.EXPLORE_VARIANT in kinds


def test_fail_below_050_generates_archive_hypothesis():
    task = _completed_task(pass_rate=0.30)
    report = ResearchReportBuilder().build(_make_result([task]))
    kinds = [r.kind for r in report.recommendations]
    assert RecommendationKind.ARCHIVE_HYPOTHESIS in kinds
    archive = next(r for r in report.recommendations if r.kind == RecommendationKind.ARCHIVE_HYPOTHESIS)
    assert archive.scope == RecommendationScope.HYPOTHESIS
    assert archive.priority == RecommendationPriority.LOW


def test_inconclusive_generates_review_parameters():
    task = _completed_task(pass_rate=None)
    report = ResearchReportBuilder().build(_make_result([task]))
    kinds = [r.kind for r in report.recommendations]
    assert RecommendationKind.REVIEW_PARAMETERS in kinds
    rec = next(r for r in report.recommendations if r.kind == RecommendationKind.REVIEW_PARAMETERS)
    assert rec.scope == RecommendationScope.HYPOTHESIS


def test_error_tasks_generate_session_level_investigate_pipeline():
    tasks = [_failed_task(), _failed_task()]
    report = ResearchReportBuilder().build(_make_result(tasks))
    pipeline_recs = [r for r in report.recommendations if r.kind == RecommendationKind.INVESTIGATE_PIPELINE]
    assert len(pipeline_recs) == 1
    assert pipeline_recs[0].scope == RecommendationScope.SESSION
    assert pipeline_recs[0].hypothesis_id is None
    assert pipeline_recs[0].priority == RecommendationPriority.HIGH


def test_skipped_tasks_generate_session_level_reschedule():
    tasks = [_skipped_task(), _skipped_task()]
    report = ResearchReportBuilder().build(_make_result(tasks))
    reschedule_recs = [r for r in report.recommendations if r.kind == RecommendationKind.RESCHEDULE_SKIPPED]
    assert len(reschedule_recs) == 1
    assert reschedule_recs[0].scope == RecommendationScope.SESSION
    assert reschedule_recs[0].hypothesis_id is None


def test_recommendations_ordered_high_before_low():
    tasks = [
        _completed_task(pass_rate=0.30),  # ARCHIVE → LOW
        _failed_task(),                   # ERROR → INVESTIGATE_PIPELINE → HIGH
    ]
    report = ResearchReportBuilder().build(_make_result(tasks))
    priorities = [r.priority for r in report.recommendations]
    high_idx = priorities.index(RecommendationPriority.HIGH)
    low_idx  = priorities.index(RecommendationPriority.LOW)
    assert high_idx < low_idx


# ─────────────────────────────────────────────────────────────────────────────
# Report identity and determinism
# ─────────────────────────────────────────────────────────────────────────────

def test_report_id_is_unique_per_call():
    result = _make_result([_completed_task()])
    builder = ResearchReportBuilder()
    r1 = builder.build(result)
    r2 = builder.build(result)
    assert r1.report_id != r2.report_id


def test_report_structure_is_deterministic_across_calls():
    result = _make_result([
        _completed_task(hypothesis_id="h1", pass_rate=0.90),
        _completed_task(hypothesis_id="h2", pass_rate=0.70),
    ])
    builder = ResearchReportBuilder(_clock=lambda: _TS)
    r1 = builder.build(result)
    r2 = builder.build(result)
    assert len(r1.findings) == len(r2.findings)
    assert r1.findings[0].outcome == r2.findings[0].outcome
    assert r1.summary.avg_pass_rate == pytest.approx(r2.summary.avg_pass_rate)
    assert r1.summary.median_pass_rate == pytest.approx(r2.summary.median_pass_rate)


def test_report_is_frozen():
    result = _make_result([])
    report = ResearchReportBuilder().build(result)
    with pytest.raises(Exception):
        report.session_id = "modified"  # type: ignore[misc]
