"""Tests for MemoryTemplateRepository."""
from __future__ import annotations

import pytest

from core.hypothesis_generator.models import HypothesisPriority, HypothesisTemplate
from core.hypothesis_generator.repository import MemoryTemplateRepository


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _make_template(
    template_id: str = "tmpl_001",
    category: str = "Trend Following",
    priority: HypothesisPriority = HypothesisPriority.A,
) -> HypothesisTemplate:
    return HypothesisTemplate(
        template_id=template_id,
        name=f"Template {template_id}",
        category=category,
        priority=priority,
        title_template="Title {ticker}",
        statement_template="Statement for {ticker}.",
        required_features=["adx_14"],
        default_parameters={"ticker": "SBER"},
    )


# ──────────────────────────────────────────────────────────────────────────────
# add / get
# ──────────────────────────────────────────────────────────────────────────────

def test_add_and_get_returns_correct_template():
    repo = MemoryTemplateRepository()
    t = _make_template("tmpl_001")
    repo.add(t)
    result = repo.get("tmpl_001")
    assert result.template_id == "tmpl_001"
    assert result.name == t.name


def test_get_returns_deepcopy_not_same_object():
    repo = MemoryTemplateRepository()
    t = _make_template("tmpl_001")
    repo.add(t)
    a = repo.get("tmpl_001")
    b = repo.get("tmpl_001")
    assert a is not b


def test_get_unknown_template_raises_key_error():
    repo = MemoryTemplateRepository()
    with pytest.raises(KeyError, match="tmpl_missing"):
        repo.get("tmpl_missing")


def test_add_overwrites_existing_template_id():
    repo = MemoryTemplateRepository()
    repo.add(_make_template("tmpl_001", category="Trend Following"))
    repo.add(_make_template("tmpl_001", category="Mean Reversion"))
    assert repo.get("tmpl_001").category == "Mean Reversion"


# ──────────────────────────────────────────────────────────────────────────────
# list
# ──────────────────────────────────────────────────────────────────────────────

def test_list_returns_all_templates():
    repo = MemoryTemplateRepository()
    repo.add(_make_template("tmpl_001"))
    repo.add(_make_template("tmpl_002"))
    repo.add(_make_template("tmpl_003"))
    assert len(repo.list()) == 3


def test_list_empty_repo_returns_empty():
    assert MemoryTemplateRepository().list() == []


def test_list_preserves_insertion_order():
    repo = MemoryTemplateRepository()
    ids = ["tmpl_c", "tmpl_a", "tmpl_b"]
    for tid in ids:
        repo.add(_make_template(tid))
    assert [t.template_id for t in repo.list()] == ids


def test_list_returns_deepcopies_mutation_does_not_affect_store():
    repo = MemoryTemplateRepository()
    repo.add(_make_template("tmpl_001"))
    listing = repo.list()
    listing[0].name = "MUTATED"
    assert repo.get("tmpl_001").name != "MUTATED"


# ──────────────────────────────────────────────────────────────────────────────
# list_by_category
# ──────────────────────────────────────────────────────────────────────────────

def test_list_by_category_returns_only_matching():
    repo = MemoryTemplateRepository()
    repo.add(_make_template("tmpl_trend", category="Trend Following"))
    repo.add(_make_template("tmpl_mean", category="Mean Reversion"))
    repo.add(_make_template("tmpl_trend2", category="Trend Following"))
    result = repo.list_by_category("Trend Following")
    assert len(result) == 2
    assert all(t.category == "Trend Following" for t in result)


def test_list_by_category_missing_returns_empty():
    repo = MemoryTemplateRepository()
    repo.add(_make_template("tmpl_001", category="Trend Following"))
    assert repo.list_by_category("Volatility") == []


# ──────────────────────────────────────────────────────────────────────────────
# Constructor bulk-load
# ──────────────────────────────────────────────────────────────────────────────

def test_constructor_bulk_load():
    templates = [_make_template(f"tmpl_{i:03d}") for i in range(5)]
    repo = MemoryTemplateRepository(templates)
    assert len(repo.list()) == 5
