"""Tests for report_models.py (Capability 4.4 data models)."""
from __future__ import annotations

from datetime import datetime

import pytest

from core.research_session.models import ResearchSessionConfig, ResearchSessionStatus
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

_TS = datetime(2026, 1, 1, 12, 0, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Enum values
# ─────────────────────────────────────────────────────────────────────────────

def test_validation_outcome_values():
    assert set(ValidationOutcome) == {
        ValidationOutcome.PASS,
        ValidationOutcome.FAIL,
        ValidationOutcome.INCONCLUSIVE,
        ValidationOutcome.ERROR,
        ValidationOutcome.SKIPPED,
    }


def test_recommendation_kind_values():
    assert set(RecommendationKind) == {
        RecommendationKind.REPEAT_EXPERIMENT,
        RecommendationKind.ARCHIVE_HYPOTHESIS,
        RecommendationKind.EXPLORE_VARIANT,
        RecommendationKind.REVIEW_PARAMETERS,
        RecommendationKind.INVESTIGATE_PIPELINE,
        RecommendationKind.RESCHEDULE_SKIPPED,
    }


def test_recommendation_priority_values():
    assert set(RecommendationPriority) == {
        RecommendationPriority.HIGH,
        RecommendationPriority.MEDIUM,
        RecommendationPriority.LOW,
    }


def test_recommendation_scope_values():
    assert set(RecommendationScope) == {
        RecommendationScope.SESSION,
        RecommendationScope.HYPOTHESIS,
    }


def test_validation_outcome_is_str_enum():
    assert ValidationOutcome.PASS == "PASS"
    assert ValidationOutcome.FAIL == "FAIL"
    assert RecommendationPriority.HIGH == "HIGH"
    assert RecommendationScope.SESSION == "SESSION"


# ─────────────────────────────────────────────────────────────────────────────
# HypothesisInfo
# ─────────────────────────────────────────────────────────────────────────────

def test_hypothesis_info_fields():
    info = HypothesisInfo(hypothesis_id="hyp_1", title="My Hypothesis", template_id="tmpl_h13")
    assert info.hypothesis_id == "hyp_1"
    assert info.title == "My Hypothesis"
    assert info.template_id == "tmpl_h13"


def test_hypothesis_info_template_id_optional():
    info = HypothesisInfo(hypothesis_id="hyp_1", title="Title", template_id=None)
    assert info.template_id is None


def test_hypothesis_info_is_frozen():
    info = HypothesisInfo(hypothesis_id="hyp_1", title="Title", template_id=None)
    with pytest.raises(Exception):
        info.title = "Modified"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# ResearchRecommendation — scope contract
# ─────────────────────────────────────────────────────────────────────────────

def test_session_scoped_recommendation_has_no_hypothesis_id():
    rec = ResearchRecommendation(
        kind=RecommendationKind.INVESTIGATE_PIPELINE,
        scope=RecommendationScope.SESSION,
        hypothesis_id=None,
        rationale="2 tasks failed.",
        priority=RecommendationPriority.HIGH,
    )
    assert rec.scope == RecommendationScope.SESSION
    assert rec.hypothesis_id is None


def test_hypothesis_scoped_recommendation_has_hypothesis_id():
    rec = ResearchRecommendation(
        kind=RecommendationKind.EXPLORE_VARIANT,
        scope=RecommendationScope.HYPOTHESIS,
        hypothesis_id="hyp_42",
        rationale="Explore variants.",
        priority=RecommendationPriority.LOW,
    )
    assert rec.scope == RecommendationScope.HYPOTHESIS
    assert rec.hypothesis_id == "hyp_42"


def test_research_recommendation_is_frozen():
    rec = ResearchRecommendation(
        kind=RecommendationKind.ARCHIVE_HYPOTHESIS,
        scope=RecommendationScope.HYPOTHESIS,
        hypothesis_id="hyp_1",
        rationale="Archive it.",
        priority=RecommendationPriority.LOW,
    )
    with pytest.raises(Exception):
        rec.priority = RecommendationPriority.HIGH  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# ResearchFinding — immutability
# ─────────────────────────────────────────────────────────────────────────────

def test_research_finding_is_frozen():
    finding = ResearchFinding(
        hypothesis_id="hyp_1",
        hypothesis_title="Title",
        template_id=None,
        outcome=ValidationOutcome.PASS,
        pass_rate=0.9,
        windows_total=10,
        knowledge_entry_id="kb_1",
        strategy_name="adx",
        rationale="Passed.",
    )
    with pytest.raises(Exception):
        finding.outcome = ValidationOutcome.FAIL  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# ResearchReport — immutability
# ─────────────────────────────────────────────────────────────────────────────

def test_research_report_is_frozen():
    summary = ReportSummary(
        session_id="sess_1",
        description="",
        status=ResearchSessionStatus.COMPLETED,
        total_hypotheses=0,
        pass_count=0,
        fail_count=0,
        inconclusive_count=0,
        error_count=0,
        skipped_count=0,
        validation_pass_rate=None,
        avg_pass_rate=None,
        median_pass_rate=None,
        kb_entries_created=0,
        duration_seconds=0.0,
        pass_threshold=0.80,
    )
    report = ResearchReport(
        report_id="rpt_1",
        generated_at=_TS,
        session_id="sess_1",
        summary=summary,
        findings=(),
        recommendations=(),
    )
    with pytest.raises(Exception):
        report.session_id = "mutated"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# ResearchSessionConfig.pass_threshold (ADR-0017)
# ─────────────────────────────────────────────────────────────────────────────

def _base_config(**kwargs):
    from core.experiment.models import ExperimentConfig
    from core.hypothesis_generator.models import GenerationConfig
    exp = ExperimentConfig(
        experiment_id="e1", hypothesis_id="h1", dataset_id="ds",
        strategy_name="adx", feature_set=[],
    )
    return ResearchSessionConfig(
        generation_config=GenerationConfig(max_candidates=1),
        experiment_config=exp,
        **kwargs,
    )


def test_pass_threshold_default_is_080():
    cfg = _base_config()
    assert cfg.pass_threshold == 0.80


def test_pass_threshold_custom_value():
    cfg = _base_config(pass_threshold=0.70)
    assert cfg.pass_threshold == 0.70


def test_pass_threshold_boundary_1_0_allowed():
    cfg = _base_config(pass_threshold=1.0)
    assert cfg.pass_threshold == 1.0


def test_pass_threshold_zero_raises():
    with pytest.raises(ValueError):
        _base_config(pass_threshold=0.0)


def test_pass_threshold_above_1_raises():
    with pytest.raises(ValueError):
        _base_config(pass_threshold=1.1)


def test_pass_threshold_negative_raises():
    with pytest.raises(ValueError):
        _base_config(pass_threshold=-0.1)
