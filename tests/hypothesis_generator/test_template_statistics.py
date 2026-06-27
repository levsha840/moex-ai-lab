"""Tests for KBTemplateStatisticsProvider."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from core.hypothesis.models import Hypothesis, HypothesisStatus
from core.hypothesis_generator.models import TemplateStats
from core.hypothesis_generator.statistics import KBTemplateStatisticsProvider
from core.knowledge.models import KnowledgeEntry, KnowledgeType


# ─────────────────────────────────────────────────────────────────────────────
# Stubs
# ─────────────────────────────────────────────────────────────────────────────

class _StubKB:
    def __init__(self, entries: list[KnowledgeEntry]) -> None:
        self._entries = entries

    def find_by_type(self, knowledge_type: KnowledgeType) -> list[KnowledgeEntry]:
        return [e for e in self._entries if e.knowledge_type == knowledge_type]


class _StubRegistry:
    def __init__(self, hypotheses: dict[str, Hypothesis]) -> None:
        self._h = hypotheses

    def get(self, hypothesis_id: str) -> Hypothesis:
        if hypothesis_id not in self._h:
            raise KeyError(hypothesis_id)
        return self._h[hypothesis_id]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_TS = datetime(2026, 1, 1)


def _entry(
    reference_id: str,
    validation_status: str,
    knowledge_type: KnowledgeType = KnowledgeType.EXPERIMENT,
) -> KnowledgeEntry:
    return KnowledgeEntry(
        id=uuid4().hex,
        knowledge_type=knowledge_type,
        reference_id=reference_id,
        summary="test",
        tags=[],
        created_at=_TS,
        metadata={"validation_status": validation_status},
    )


def _hypothesis(hypothesis_id: str, template_id: str | None = "tmpl_h13") -> Hypothesis:
    meta = {"template_id": template_id} if template_id is not None else {}
    return Hypothesis(
        id=hypothesis_id,
        title="Test",
        statement="Test statement.",
        status=HypothesisStatus.RESEARCH,
        created_at=_TS,
        updated_at=_TS,
        metadata=meta,
    )


def _provider(
    entries: list[KnowledgeEntry],
    hypotheses: dict[str, Hypothesis],
) -> KBTemplateStatisticsProvider:
    return KBTemplateStatisticsProvider(_StubKB(entries), _StubRegistry(hypotheses))


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_kb_returns_empty_dict():
    stats = _provider([], {}).get_stats()
    assert stats == {}


def test_single_pass_experiment():
    h_id = "hyp_1"
    stats = _provider(
        [_entry(h_id, "PASS")],
        {h_id: _hypothesis(h_id, "tmpl_h13")},
    ).get_stats()

    assert "tmpl_h13" in stats
    s = stats["tmpl_h13"]
    assert s.pass_count == 1
    assert s.fail_count == 0
    assert s.experiment_count == 1


def test_single_fail_experiment():
    h_id = "hyp_1"
    stats = _provider(
        [_entry(h_id, "FAIL")],
        {h_id: _hypothesis(h_id, "tmpl_h13")},
    ).get_stats()

    s = stats["tmpl_h13"]
    assert s.pass_count == 0
    assert s.fail_count == 1
    assert s.experiment_count == 1


def test_mixed_experiments_correct_counts():
    h_id = "hyp_1"
    entries = [
        _entry(h_id, "PASS"),
        _entry(h_id, "PASS"),
        _entry(h_id, "FAIL"),
    ]
    stats = _provider(entries, {h_id: _hypothesis(h_id)}).get_stats()

    s = stats["tmpl_h13"]
    assert s.pass_count == 2
    assert s.fail_count == 1
    assert s.experiment_count == 3


def test_two_different_templates():
    h1, h2 = "hyp_1", "hyp_2"
    stats = _provider(
        [_entry(h1, "PASS"), _entry(h2, "FAIL")],
        {
            h1: _hypothesis(h1, "tmpl_a"),
            h2: _hypothesis(h2, "tmpl_b"),
        },
    ).get_stats()

    assert stats["tmpl_a"].pass_count == 1
    assert stats["tmpl_a"].fail_count == 0
    assert stats["tmpl_b"].pass_count == 0
    assert stats["tmpl_b"].fail_count == 1


def test_hypothesis_not_in_registry_is_skipped():
    stats = _provider(
        [_entry("unknown_hyp", "PASS")],
        {},
    ).get_stats()
    assert stats == {}


def test_hypothesis_without_template_id_is_skipped():
    h_id = "hyp_no_template"
    stats = _provider(
        [_entry(h_id, "PASS")],
        {h_id: _hypothesis(h_id, template_id=None)},
    ).get_stats()
    assert stats == {}


def test_inconclusive_validation_status_not_counted():
    h_id = "hyp_1"
    stats = _provider(
        [_entry(h_id, "N/A")],
        {h_id: _hypothesis(h_id)},
    ).get_stats()
    assert stats == {}


def test_empty_validation_status_not_counted():
    h_id = "hyp_1"
    entry = KnowledgeEntry(
        id=uuid4().hex,
        knowledge_type=KnowledgeType.EXPERIMENT,
        reference_id=h_id,
        summary="test",
        tags=[],
        created_at=_TS,
        metadata={},  # no validation_status key
    )
    stats = _provider([entry], {h_id: _hypothesis(h_id)}).get_stats()
    assert stats == {}


def test_multiple_experiments_same_template_accumulated():
    h_ids = [f"hyp_{i}" for i in range(6)]
    entries = [
        _entry(h_ids[0], "PASS"),
        _entry(h_ids[1], "PASS"),
        _entry(h_ids[2], "PASS"),
        _entry(h_ids[3], "FAIL"),
        _entry(h_ids[4], "FAIL"),
        _entry(h_ids[5], "PASS"),
    ]
    hypotheses = {h: _hypothesis(h, "tmpl_x") for h in h_ids}

    stats = _provider(entries, hypotheses).get_stats()
    s = stats["tmpl_x"]
    assert s.pass_count == 4
    assert s.fail_count == 2
    assert s.experiment_count == 6


def test_experiment_count_equals_pass_plus_fail():
    h_id = "hyp_1"
    stats = _provider(
        [_entry(h_id, "PASS"), _entry(h_id, "FAIL")],
        {h_id: _hypothesis(h_id)},
    ).get_stats()

    s = stats["tmpl_h13"]
    assert s.experiment_count == s.pass_count + s.fail_count


def test_non_experiment_entry_type_ignored():
    h_id = "hyp_1"
    entry = _entry(h_id, "PASS", knowledge_type=KnowledgeType.OBSERVATION)
    stats = _provider([entry], {h_id: _hypothesis(h_id)}).get_stats()
    assert stats == {}
