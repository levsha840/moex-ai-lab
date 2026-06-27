"""Tests for KnowledgeRanker."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from core.hypothesis_generator.models import HypothesisCandidate, TemplateStats
from core.hypothesis_generator.ranker import KnowledgeRanker, PriorityRanker


# ─────────────────────────────────────────────────────────────────────────────
# Stubs
# ─────────────────────────────────────────────────────────────────────────────

class _StubProvider:
    """Returns a fixed stats snapshot."""

    def __init__(self, stats: dict[str, TemplateStats]) -> None:
        self._stats = stats

    def get_stats(self) -> dict[str, TemplateStats]:
        return dict(self._stats)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_TS = datetime(2026, 1, 1)


def _candidate(
    template_id: str,
    title: str = "Test Title",
    statement: str = "Test statement.",
    score: float = 1.0,
    rationale: str = "Priority A",
    candidate_id: str | None = None,
) -> HypothesisCandidate:
    return HypothesisCandidate(
        candidate_id=candidate_id or uuid4().hex,
        template_id=template_id,
        title=title,
        statement=statement,
        parameters={"p": 1},
        score=score,
        rationale=rationale,
        created_at=_TS,
    )


def _stats(template_id: str, pass_count: int, fail_count: int) -> TemplateStats:
    return TemplateStats(
        template_id=template_id,
        pass_count=pass_count,
        fail_count=fail_count,
        experiment_count=pass_count + fail_count,
    )


def _ranker(
    stats: dict[str, TemplateStats] | None = None,
    *,
    confidence_threshold: int = 5,
    max_adjustment: float = 1.0,
    duplicate_penalty_floor: float = 0.75,
    duplicate_step: float = 0.05,
) -> KnowledgeRanker:
    return KnowledgeRanker(
        _StubProvider(stats or {}),
        confidence_threshold=confidence_threshold,
        max_adjustment=max_adjustment,
        duplicate_penalty_floor=duplicate_penalty_floor,
        duplicate_step=duplicate_step,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Basic properties
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_candidates_returns_empty():
    assert _ranker().rank([]) == []


def test_single_candidate_no_history_score_unchanged():
    c = _candidate("tmpl_a", score=0.7)
    result = _ranker().rank([c])
    assert len(result) == 1
    assert result[0].score == pytest.approx(0.7)


def test_all_pass_full_confidence_boosts_score():
    stats = {"tmpl_a": _stats("tmpl_a", pass_count=5, fail_count=0)}
    c = _candidate("tmpl_a", score=1.0)
    result = _ranker(stats).rank([c])
    # multiplier = 1 + 0.5 * 1.0 * 1.0 = 1.5; penalty = max(0.75, 1 - 0.05*5) = 0.75
    # final = 1.0 * 1.5 * 0.75 = 1.125
    assert result[0].score == pytest.approx(1.125)
    assert result[0].score > 1.0


def test_all_fail_full_confidence_reduces_score():
    stats = {"tmpl_a": _stats("tmpl_a", pass_count=0, fail_count=5)}
    c = _candidate("tmpl_a", score=1.0)
    result = _ranker(stats).rank([c])
    # multiplier = 1 + (0 - 0.5) * 1.0 * 1.0 = 0.5; penalty = 0.75
    # final = 1.0 * 0.5 * 0.75 = 0.375
    assert result[0].score == pytest.approx(0.375)
    assert result[0].score < 1.0


def test_no_history_multiplier_exactly_one():
    c = _candidate("tmpl_a", score=0.4)
    result = _ranker({}).rank([c])
    assert result[0].score == pytest.approx(0.4)


def test_partial_confidence_less_effect_than_full():
    c_low = _candidate("tmpl_a", score=1.0)
    c_high = _candidate("tmpl_a", score=1.0)

    stats_1 = {"tmpl_a": _stats("tmpl_a", pass_count=1, fail_count=0)}
    stats_5 = {"tmpl_a": _stats("tmpl_a", pass_count=5, fail_count=0)}

    score_low = _ranker(stats_1).rank([c_low])[0].score
    score_high = _ranker(stats_5).rank([c_high])[0].score

    # 5 experiments → higher boost than 1
    assert score_high > score_low


def test_pass_rate_half_is_neutral():
    stats = {"tmpl_a": _stats("tmpl_a", pass_count=5, fail_count=5)}
    c = _candidate("tmpl_a", score=0.7)
    result = _ranker(stats).rank([c])
    # multiplier = 1 + 0.0 * ... = 1.0; penalty = max(0.75, 1 - 0.05*10) = 0.75
    # final = 0.7 * 1.0 * 0.75 = 0.525
    # score changes only due to duplicate_penalty (not knowledge boost/penalty)
    km = 1.0 + (0.5 - 0.5) * 1.0 * 1.0  # = 1.0
    assert km == pytest.approx(1.0)
    assert result[0].score == pytest.approx(0.7 * 1.0 * 0.75)


# ─────────────────────────────────────────────────────────────────────────────
# Non-mutation guarantees
# ─────────────────────────────────────────────────────────────────────────────

def test_does_not_mutate_input_list():
    c = _candidate("tmpl_a", score=1.0)
    original_score = c.score
    original_id = c.candidate_id
    original_list = [c]
    _ranker().rank(original_list)
    assert len(original_list) == 1
    assert original_list[0].score == original_score
    assert original_list[0].candidate_id == original_id


def test_returns_new_candidate_objects():
    c = _candidate("tmpl_a", score=1.0)
    result = _ranker().rank([c])
    assert result[0] is not c


def test_candidate_id_preserved():
    cid = uuid4().hex
    c = _candidate("tmpl_a", candidate_id=cid)
    result = _ranker().rank([c])
    assert result[0].candidate_id == cid


def test_parameters_deepcopied():
    params = {"key": [1, 2, 3]}
    c = _candidate("tmpl_a")
    c.parameters = params
    result = _ranker().rank([c])
    result[0].parameters["key"].append(99)
    assert params["key"] == [1, 2, 3]


# ─────────────────────────────────────────────────────────────────────────────
# Determinism
# ─────────────────────────────────────────────────────────────────────────────

def test_same_call_twice_returns_same_order():
    stats = {
        "tmpl_a": _stats("tmpl_a", pass_count=3, fail_count=1),
        "tmpl_b": _stats("tmpl_b", pass_count=1, fail_count=2),
    }
    candidates = [
        _candidate("tmpl_a", score=1.0),
        _candidate("tmpl_b", score=0.7),
    ]
    r = _ranker(stats)
    result1 = [c.template_id for c in r.rank(candidates)]
    result2 = [c.template_id for c in r.rank(candidates)]
    assert result1 == result2


def test_input_order_does_not_affect_output_order():
    stats = {
        "tmpl_a": _stats("tmpl_a", pass_count=5, fail_count=0),
        "tmpl_b": _stats("tmpl_b", pass_count=0, fail_count=5),
    }
    c_a = _candidate("tmpl_a", score=1.0)
    c_b = _candidate("tmpl_b", score=1.0)
    r = _ranker(stats)
    result_ab = [c.template_id for c in r.rank([c_a, c_b])]
    result_ba = [c.template_id for c in r.rank([c_b, c_a])]
    assert result_ab == result_ba


def test_tiebreak_by_template_id_not_candidate_id():
    # Two candidates with same base score and no KB history.
    # Tie-breaking must use template_id (stable), not candidate_id (uuid, changes per session).
    c_z = _candidate("tmpl_z", title="Same Title", score=1.0)
    c_a = _candidate("tmpl_a", title="Same Title", score=1.0)

    result = _ranker().rank([c_z, c_a])
    # template_id "tmpl_a" < "tmpl_z" → tmpl_a first
    assert result[0].template_id == "tmpl_a"
    assert result[1].template_id == "tmpl_z"


def test_tiebreak_by_title_when_same_template_id():
    c_z = _candidate("tmpl_a", title="Zebra Strategy", score=1.0)
    c_a = _candidate("tmpl_a", title="Apple Strategy", score=1.0)

    result = _ranker().rank([c_z, c_a])
    # title "Apple..." < "Zebra..." → Apple first
    assert result[0].title == "Apple Strategy"
    assert result[1].title == "Zebra Strategy"


def test_determinism_across_independent_candidate_ids():
    # Simulate two separate generation sessions: same template/title but different uuid candidate_ids
    stats = {"tmpl_a": _stats("tmpl_a", pass_count=2, fail_count=1)}
    c1_session1 = _candidate("tmpl_a", title="T1", candidate_id=uuid4().hex, score=1.0)
    c2_session1 = _candidate("tmpl_b", title="T2", candidate_id=uuid4().hex, score=0.7)
    c1_session2 = _candidate("tmpl_a", title="T1", candidate_id=uuid4().hex, score=1.0)
    c2_session2 = _candidate("tmpl_b", title="T2", candidate_id=uuid4().hex, score=0.7)

    r = _ranker(stats)
    order1 = [c.template_id for c in r.rank([c1_session1, c2_session1])]
    order2 = [c.template_id for c in r.rank([c1_session2, c2_session2])]
    assert order1 == order2


# ─────────────────────────────────────────────────────────────────────────────
# Rationale
# ─────────────────────────────────────────────────────────────────────────────

def test_rationale_updated_when_has_kb_history():
    stats = {"tmpl_a": _stats("tmpl_a", pass_count=3, fail_count=1)}
    c = _candidate("tmpl_a", rationale="Priority A")
    result = _ranker(stats).rank([c])
    assert "KB:" in result[0].rationale
    assert "3P/1F" in result[0].rationale


def test_rationale_unchanged_when_no_history():
    c = _candidate("tmpl_a", rationale="Priority A")
    result = _ranker({}).rank([c])
    assert result[0].rationale == "Priority A"


# ─────────────────────────────────────────────────────────────────────────────
# Duplicate penalty
# ─────────────────────────────────────────────────────────────────────────────

def test_duplicate_penalty_uses_experiment_count_not_pass_count():
    # 0 PASS, 5 FAIL → experiment_count=5 → penalty should still be applied
    stats = {"tmpl_a": _stats("tmpl_a", pass_count=0, fail_count=5)}
    c = _candidate("tmpl_a", score=1.0)
    result = _ranker(stats).rank([c])
    # penalty = max(0.75, 1 - 0.05 * 5) = 0.75
    # multiplier = 0.5 (all FAIL, full confidence)
    # final = 1.0 * 0.5 * 0.75 = 0.375
    assert result[0].score == pytest.approx(0.375)


def test_duplicate_penalty_no_experiments():
    stats = {"tmpl_a": _stats("tmpl_a", pass_count=0, fail_count=0)}
    c = _candidate("tmpl_a", score=0.7)
    result = _ranker(stats).rank([c])
    # no history → multiplier=1.0, penalty=1.0
    assert result[0].score == pytest.approx(0.7)


def test_duplicate_penalty_floor_enforced():
    # 20 experiments → penalty formula gives 1 - 0.05*20 = 0.0 → clipped to floor 0.75
    stats = {"tmpl_a": _stats("tmpl_a", pass_count=20, fail_count=0)}
    c = _candidate("tmpl_a", score=1.0)
    result = _ranker(stats).rank([c])
    # multiplier = 1.5 (all PASS, full confidence)
    # penalty = max(0.75, 1 - 0.05*20) = max(0.75, 0.0) = 0.75
    assert result[0].score == pytest.approx(1.0 * 1.5 * 0.75)


# ─────────────────────────────────────────────────────────────────────────────
# No-starvation: new candidates not suppressed
# ─────────────────────────────────────────────────────────────────────────────

def test_no_starvation_new_candidate_not_zeroed():
    c = _candidate("new_template", score=1.0)
    result = _ranker({}).rank([c])
    assert result[0].score == pytest.approx(1.0)


def test_new_priority_a_above_old_priority_c_max_pass():
    # New A: score=1.0, multiplier=1.0, penalty=1.0 → final=1.0
    # Old C, 5 PASS, full confidence: score=0.4, mult=1.5, penalty=0.75 → final=0.45
    stats = {"tmpl_c": _stats("tmpl_c", pass_count=5, fail_count=0)}
    c_new = _candidate("tmpl_a_new", title="A", score=1.0)
    c_old = _candidate("tmpl_c", title="C", score=0.4)

    result = _ranker(stats).rank([c_old, c_new])
    assert result[0].template_id == "tmpl_a_new"


def test_all_fail_score_still_positive():
    # Worst case: all FAIL, many experiments → score must remain > 0
    stats = {"tmpl_a": _stats("tmpl_a", pass_count=0, fail_count=100)}
    c = _candidate("tmpl_a", score=1.0)
    result = _ranker(stats).rank([c])
    assert result[0].score > 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Configurability
# ─────────────────────────────────────────────────────────────────────────────

def test_max_adjustment_zero_behaves_like_priority_ranker():
    # When max_adjustment=0, knowledge_multiplier=1.0 regardless of history
    stats = {
        "tmpl_a": _stats("tmpl_a", pass_count=5, fail_count=0),
        "tmpl_b": _stats("tmpl_b", pass_count=0, fail_count=5),
    }
    c_a = _candidate("tmpl_a", title="A", score=0.7)
    c_b = _candidate("tmpl_b", title="B", score=1.0)

    priority_order = PriorityRanker().rank([c_a, c_b])
    knowledge_order = _ranker(stats, max_adjustment=0.0).rank([c_a, c_b])

    # Both should rank c_b (score=1.0) first when adjustment=0 and no penalty matters
    # (penalty still applies — but ordering by base score is preserved)
    assert priority_order[0].template_id == knowledge_order[0].template_id


def test_invalid_confidence_threshold_raises():
    with pytest.raises(ValueError, match="confidence_threshold"):
        _ranker(confidence_threshold=0)


def test_invalid_max_adjustment_raises():
    with pytest.raises(ValueError, match="max_adjustment"):
        _ranker(max_adjustment=3.0)
