"""Tests for HypothesisGenerator, PriorityRanker, and GenerationSession."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.hypothesis.service import HypothesisRegistry
from core.hypothesis_generator.engine import HypothesisGenerator
from core.hypothesis_generator.models import (
    GenerationConfig,
    GenerationSession,
    HypothesisCandidate,
    HypothesisPriority,
    HypothesisTemplate,
)
from core.hypothesis_generator.ranker import PriorityRanker
from core.hypothesis_generator.repository import MemoryTemplateRepository


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

_FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _fixed_clock() -> datetime:
    return _FIXED_NOW


def _make_template(
    template_id: str = "tmpl_001",
    category: str = "Trend Following",
    priority: HypothesisPriority = HypothesisPriority.A,
    ticker: str = "SBER",
) -> HypothesisTemplate:
    return HypothesisTemplate(
        template_id=template_id,
        name=f"Template {template_id}",
        category=category,
        priority=priority,
        title_template="Buy {ticker} on trend pullback",
        statement_template="Enter {ticker} when ADX > 25 and RSI retraces.",
        required_features=["adx_14", "rsi_14"],
        default_parameters={"ticker": ticker},
    )


def _make_generator(templates: list[HypothesisTemplate] | None = None) -> HypothesisGenerator:
    repo = MemoryTemplateRepository(templates or [])
    return HypothesisGenerator(repo, PriorityRanker(), _clock=_fixed_clock)


def _default_config(**kwargs) -> GenerationConfig:
    return GenerationConfig(**kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# generate() — empty repository
# ──────────────────────────────────────────────────────────────────────────────

def test_generate_empty_repo_returns_session_with_no_candidates():
    gen = _make_generator()
    session = gen.generate(_default_config())
    assert isinstance(session, GenerationSession)
    assert len(session.generated_candidates) == 0


# ──────────────────────────────────────────────────────────────────────────────
# generate() — single template
# ──────────────────────────────────────────────────────────────────────────────

def test_generate_one_template_produces_one_candidate():
    gen = _make_generator([_make_template()])
    session = gen.generate(_default_config())
    assert len(session.generated_candidates) == 1


def test_generate_candidate_has_correct_template_id():
    gen = _make_generator([_make_template("tmpl_x")])
    session = gen.generate(_default_config())
    assert session.generated_candidates[0].template_id == "tmpl_x"


def test_generate_candidate_title_is_rendered():
    gen = _make_generator([_make_template(ticker="GAZP")])
    session = gen.generate(_default_config())
    assert "GAZP" in session.generated_candidates[0].title


def test_generate_candidate_statement_is_rendered():
    gen = _make_generator([_make_template(ticker="LKOH")])
    session = gen.generate(_default_config())
    assert "LKOH" in session.generated_candidates[0].statement


def test_generate_candidate_score_equals_template_base_score():
    gen = _make_generator([_make_template(priority=HypothesisPriority.B)])
    session = gen.generate(_default_config())
    assert session.generated_candidates[0].score == pytest.approx(0.7)


def test_generate_candidate_parameters_match_template_defaults():
    gen = _make_generator([_make_template(ticker="YNDX")])
    session = gen.generate(_default_config())
    assert session.generated_candidates[0].parameters["ticker"] == "YNDX"


def test_generate_candidate_has_nonempty_rationale():
    gen = _make_generator([_make_template()])
    session = gen.generate(_default_config())
    assert len(session.generated_candidates[0].rationale) > 0


def test_generate_candidate_created_at_matches_clock():
    gen = _make_generator([_make_template()])
    session = gen.generate(_default_config())
    assert session.generated_candidates[0].created_at == _FIXED_NOW


# ──────────────────────────────────────────────────────────────────────────────
# generate() — max_candidates
# ──────────────────────────────────────────────────────────────────────────────

def test_generate_respects_max_candidates():
    templates = [_make_template(f"tmpl_{i:03d}") for i in range(5)]
    gen = _make_generator(templates)
    session = gen.generate(_default_config(max_candidates=3))
    assert len(session.generated_candidates) == 3


# ──────────────────────────────────────────────────────────────────────────────
# generate() — min_score
# ──────────────────────────────────────────────────────────────────────────────

def test_generate_min_score_filters_low_priority_templates():
    templates = [
        _make_template("tmpl_a", priority=HypothesisPriority.A),  # score 1.0
        _make_template("tmpl_b", priority=HypothesisPriority.B),  # score 0.7
        _make_template("tmpl_c", priority=HypothesisPriority.C),  # score 0.4
    ]
    gen = _make_generator(templates)
    session = gen.generate(_default_config(min_score=0.8))
    assert len(session.generated_candidates) == 1
    assert session.generated_candidates[0].template_id == "tmpl_a"


def test_generate_min_score_zero_keeps_all():
    templates = [
        _make_template("tmpl_a", priority=HypothesisPriority.A),
        _make_template("tmpl_c", priority=HypothesisPriority.C),
    ]
    gen = _make_generator(templates)
    session = gen.generate(_default_config(min_score=0.0))
    assert len(session.generated_candidates) == 2


# ──────────────────────────────────────────────────────────────────────────────
# generate() — allowed_categories
# ──────────────────────────────────────────────────────────────────────────────

def test_generate_allowed_categories_filters_to_matching_only():
    templates = [
        _make_template("tmpl_trend", category="Trend Following"),
        _make_template("tmpl_mean", category="Mean Reversion"),
    ]
    gen = _make_generator(templates)
    session = gen.generate(_default_config(allowed_categories=("Trend Following",)))
    assert len(session.generated_candidates) == 1
    assert session.generated_candidates[0].template_id == "tmpl_trend"


def test_generate_allowed_categories_multiple():
    templates = [
        _make_template("tmpl_trend", category="Trend Following"),
        _make_template("tmpl_mean", category="Mean Reversion"),
        _make_template("tmpl_vol", category="Volatility"),
    ]
    gen = _make_generator(templates)
    session = gen.generate(
        _default_config(allowed_categories=("Trend Following", "Volatility"))
    )
    ids = {c.template_id for c in session.generated_candidates}
    assert ids == {"tmpl_trend", "tmpl_vol"}


def test_generate_allowed_categories_duplicate_category_no_duplicate_candidates():
    templates = [_make_template("tmpl_trend", category="Trend Following")]
    gen = _make_generator(templates)
    # Same category listed twice — must produce exactly one candidate
    session = gen.generate(
        _default_config(allowed_categories=("Trend Following", "Trend Following"))
    )
    assert len(session.generated_candidates) == 1


# ──────────────────────────────────────────────────────────────────────────────
# generate() — ordering
# ──────────────────────────────────────────────────────────────────────────────

def test_generate_candidates_sorted_by_score_descending():
    templates = [
        _make_template("tmpl_c", priority=HypothesisPriority.C),  # 0.4
        _make_template("tmpl_a", priority=HypothesisPriority.A),  # 1.0
        _make_template("tmpl_b", priority=HypothesisPriority.B),  # 0.7
    ]
    gen = _make_generator(templates)
    session = gen.generate(_default_config())
    scores = [c.score for c in session.generated_candidates]
    assert scores == sorted(scores, reverse=True)


# ──────────────────────────────────────────────────────────────────────────────
# generate() — GenerationSession
# ──────────────────────────────────────────────────────────────────────────────

def test_generate_session_carries_config():
    config = _default_config(max_candidates=5)
    gen = _make_generator([_make_template()])
    session = gen.generate(config)
    assert session.config is config


def test_generate_session_created_at_matches_clock():
    gen = _make_generator([_make_template()])
    session = gen.generate(_default_config())
    assert session.created_at == _FIXED_NOW


def test_generate_session_generated_candidates_is_tuple():
    gen = _make_generator([_make_template()])
    session = gen.generate(_default_config())
    assert isinstance(session.generated_candidates, tuple)


def test_generate_two_sessions_have_distinct_session_ids():
    gen = _make_generator([_make_template()])
    config = _default_config()
    s1 = gen.generate(config)
    s2 = gen.generate(config)
    assert s1.session_id != s2.session_id


# ──────────────────────────────────────────────────────────────────────────────
# generate() — content determinism
# ──────────────────────────────────────────────────────────────────────────────

def test_generate_content_is_deterministic():
    """Same templates + same config → same titles, statements, scores (not same IDs)."""
    templates = [
        _make_template("tmpl_a", priority=HypothesisPriority.A),
        _make_template("tmpl_b", priority=HypothesisPriority.B),
    ]
    config = _default_config()

    gen_a = _make_generator(templates)
    gen_b = _make_generator(templates)

    s_a = gen_a.generate(config)
    s_b = gen_b.generate(config)

    for ca, cb in zip(s_a.generated_candidates, s_b.generated_candidates):
        assert ca.template_id == cb.template_id
        assert ca.title == cb.title
        assert ca.statement == cb.statement
        assert ca.score == pytest.approx(cb.score)


# ──────────────────────────────────────────────────────────────────────────────
# accept()
# ──────────────────────────────────────────────────────────────────────────────

def _accept_first_candidate(templates=None) -> tuple:
    gen = _make_generator(templates or [_make_template()])
    registry = HypothesisRegistry()
    session = gen.generate(_default_config())
    candidate = session.generated_candidates[0]
    hypothesis = gen.accept(candidate, registry)
    return hypothesis, candidate, registry


def test_accept_returns_hypothesis():
    from core.hypothesis.models import Hypothesis

    hypothesis, _, _ = _accept_first_candidate()
    assert isinstance(hypothesis, Hypothesis)


def test_accept_hypothesis_status_is_idea():
    from core.hypothesis.models import HypothesisStatus

    hypothesis, _, _ = _accept_first_candidate()
    assert hypothesis.status == HypothesisStatus.IDEA


def test_accept_hypothesis_title_matches_candidate():
    hypothesis, candidate, _ = _accept_first_candidate()
    assert hypothesis.title == candidate.title


def test_accept_hypothesis_statement_matches_candidate():
    hypothesis, candidate, _ = _accept_first_candidate()
    assert hypothesis.statement == candidate.statement


def test_accept_hypothesis_metadata_has_template_id():
    hypothesis, candidate, _ = _accept_first_candidate()
    assert hypothesis.metadata.get("template_id") == candidate.template_id


def test_accept_hypothesis_appears_in_registry():
    hypothesis, _, registry = _accept_first_candidate()
    ids = [h.id for h in registry.list()]
    assert hypothesis.id in ids


def test_accept_multiple_candidates_creates_separate_hypotheses():
    templates = [
        _make_template("tmpl_001"),
        _make_template("tmpl_002"),
    ]
    gen = _make_generator(templates)
    registry = HypothesisRegistry()
    session = gen.generate(_default_config())
    for candidate in session.generated_candidates:
        gen.accept(candidate, registry)
    assert len(registry.list()) == 2


# ──────────────────────────────────────────────────────────────────────────────
# GenerationConfig validation
# ──────────────────────────────────────────────────────────────────────────────

def test_generation_config_max_candidates_zero_raises():
    with pytest.raises(ValueError, match="max_candidates"):
        GenerationConfig(max_candidates=0)


def test_generation_config_min_score_negative_raises():
    with pytest.raises(ValueError, match="min_score"):
        GenerationConfig(min_score=-0.1)


def test_generation_config_min_score_above_one_raises():
    with pytest.raises(ValueError, match="min_score"):
        GenerationConfig(min_score=1.1)


# ──────────────────────────────────────────────────────────────────────────────
# PriorityRanker
# ──────────────────────────────────────────────────────────────────────────────

def _make_candidate(score: float, tid: str = "tmpl") -> HypothesisCandidate:
    return HypothesisCandidate(
        candidate_id="cid",
        template_id=tid,
        title="Title",
        statement="Statement.",
        parameters={},
        score=score,
        rationale="test",
        created_at=_FIXED_NOW,
    )


def test_priority_ranker_sorts_descending():
    ranker = PriorityRanker()
    candidates = [_make_candidate(0.4), _make_candidate(1.0), _make_candidate(0.7)]
    result = ranker.rank(candidates)
    assert [c.score for c in result] == [1.0, 0.7, 0.4]


def test_priority_ranker_empty_list():
    assert PriorityRanker().rank([]) == []


def test_priority_ranker_single_candidate():
    c = _make_candidate(0.5)
    assert PriorityRanker().rank([c]) == [c]


def test_priority_ranker_does_not_mutate_input():
    original = [_make_candidate(0.4), _make_candidate(1.0)]
    original_order = [c.score for c in original]
    PriorityRanker().rank(original)
    assert [c.score for c in original] == original_order


# ──────────────────────────────────────────────────────────────────────────────
# H-13 template integration
# ──────────────────────────────────────────────────────────────────────────────

def test_h13_template_instantiates_correctly():
    from experiments.h13_adx_continuation.template import H13_TEMPLATE

    title, statement = H13_TEMPLATE.instantiate()
    assert "SBER" in title
    assert "TREND_UP" in statement
    assert "25" in statement


def test_h13_template_accepted_into_registry():
    from experiments.h13_adx_continuation.template import H13_TEMPLATE

    repo = MemoryTemplateRepository([H13_TEMPLATE])
    gen = HypothesisGenerator(repo, PriorityRanker(), _clock=_fixed_clock)
    registry = HypothesisRegistry()

    session = gen.generate(_default_config())
    assert len(session.generated_candidates) == 1

    hypothesis = gen.accept(session.generated_candidates[0], registry)
    assert hypothesis.metadata["template_id"] == H13_TEMPLATE.template_id
    assert len(registry.list()) == 1
