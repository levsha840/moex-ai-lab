from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.hypothesis import (
    Hypothesis,
    HypothesisRegistry,
    HypothesisStatus,
    MemoryHypothesisRepository,
)
from core.hypothesis.service import _PIPELINE, _TERMINAL


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _tick_clock():
    """Returns a monotonically increasing clock (1 µs per call)."""
    counter = [0]

    def clock() -> datetime:
        counter[0] += 1
        return datetime(2026, 1, 1, 0, 0, 0, counter[0], tzinfo=timezone.utc)

    return clock


def _registry() -> HypothesisRegistry:
    return HypothesisRegistry(_clock=_tick_clock())


def _with_status(status: HypothesisStatus) -> HypothesisRegistry:
    """Return a registry with one hypothesis already at the given status."""
    reg = _registry()
    h = reg.create("title", "statement")
    _advance_to(reg, h.id, status)
    return reg, reg.list()[0].id


def _advance_to(
    reg: HypothesisRegistry,
    hypothesis_id: str,
    target: HypothesisStatus,
) -> None:
    """Walk forward through the pipeline until *target* is reached."""
    if target in _TERMINAL:
        raise ValueError("Use reject()/archive() for terminal states in tests.")
    current_idx = _PIPELINE.index(reg.get(hypothesis_id).status)
    target_idx = _PIPELINE.index(target)
    for i in range(current_idx, target_idx):
        reg.move_to(hypothesis_id, _PIPELINE[i + 1])


# ──────────────────────────────────────────────────────────────────────────────
# Create
# ──────────────────────────────────────────────────────────────────────────────

def test_create_hypothesis_returns_hypothesis():
    reg = _registry()
    h = reg.create("RSI Oversold Strategy", "Buy when RSI < 30 in non-downtrend")
    assert isinstance(h, Hypothesis)


def test_create_hypothesis_initial_status_is_idea():
    reg = _registry()
    h = reg.create("title", "statement")
    assert h.status == HypothesisStatus.IDEA


def test_create_hypothesis_fields_are_stored():
    reg = _registry()
    h = reg.create("My Title", "My statement about the market")
    assert h.title == "My Title"
    assert h.statement == "My statement about the market"


def test_create_hypothesis_id_is_non_empty_string():
    reg = _registry()
    h = reg.create("title", "statement")
    assert isinstance(h.id, str)
    assert len(h.id) > 0


def test_create_generates_unique_ids():
    reg = _registry()
    ids = {reg.create("title", f"statement {i}").id for i in range(10)}
    assert len(ids) == 10


def test_create_hypothesis_rejection_reason_is_none():
    reg = _registry()
    h = reg.create("title", "statement")
    assert h.rejection_reason is None


def test_create_hypothesis_metadata_is_empty_dict():
    reg = _registry()
    h = reg.create("title", "statement")
    assert h.metadata == {}


# ──────────────────────────────────────────────────────────────────────────────
# Get
# ──────────────────────────────────────────────────────────────────────────────

def test_get_returns_hypothesis_by_id():
    reg = _registry()
    created = reg.create("title", "statement")
    fetched = reg.get(created.id)
    assert fetched.id == created.id


def test_get_unknown_id_raises_key_error():
    reg = _registry()
    with pytest.raises(KeyError):
        reg.get("nonexistent_id")


# ──────────────────────────────────────────────────────────────────────────────
# List
# ──────────────────────────────────────────────────────────────────────────────

def test_list_returns_empty_for_new_registry():
    reg = _registry()
    assert reg.list() == []


def test_list_returns_all_hypotheses():
    reg = _registry()
    reg.create("first", "first statement")
    reg.create("second", "second statement")
    reg.create("third", "third statement")
    assert len(reg.list()) == 3


def test_list_returns_correct_titles():
    reg = _registry()
    reg.create("alpha", "statement")
    reg.create("beta", "statement")
    titles = {h.title for h in reg.list()}
    assert titles == {"alpha", "beta"}


# ──────────────────────────────────────────────────────────────────────────────
# Valid transitions
# ──────────────────────────────────────────────────────────────────────────────

def test_valid_transition_idea_to_draft():
    reg = _registry()
    h = reg.create("title", "statement")
    updated = reg.move_to(h.id, HypothesisStatus.DRAFT)
    assert updated.status == HypothesisStatus.DRAFT


def test_valid_forward_pipeline_full():
    """Walk every step in the pipeline sequentially."""
    reg = _registry()
    h = reg.create("title", "statement")
    for i in range(len(_PIPELINE) - 1):
        h = reg.move_to(h.id, _PIPELINE[i + 1])
        assert h.status == _PIPELINE[i + 1]
    assert h.status == HypothesisStatus.PRODUCTION


def test_move_to_persists_status():
    reg = _registry()
    h = reg.create("title", "statement")
    reg.move_to(h.id, HypothesisStatus.DRAFT)
    assert reg.get(h.id).status == HypothesisStatus.DRAFT


# ──────────────────────────────────────────────────────────────────────────────
# Invalid transitions
# ──────────────────────────────────────────────────────────────────────────────

def test_invalid_skip_idea_to_research():
    reg = _registry()
    h = reg.create("title", "statement")
    with pytest.raises(ValueError, match="Expected next"):
        reg.move_to(h.id, HypothesisStatus.RESEARCH)


def test_invalid_skip_idea_to_production():
    reg = _registry()
    h = reg.create("title", "statement")
    with pytest.raises(ValueError, match="Expected next"):
        reg.move_to(h.id, HypothesisStatus.PRODUCTION)


def test_invalid_skip_backtest_to_production():
    reg = _registry()
    h = reg.create("title", "statement")
    _advance_to(reg, h.id, HypothesisStatus.BACKTEST)
    with pytest.raises(ValueError, match="Expected next"):
        reg.move_to(h.id, HypothesisStatus.PRODUCTION)


def test_invalid_backward_draft_to_idea():
    reg = _registry()
    h = reg.create("title", "statement")
    reg.move_to(h.id, HypothesisStatus.DRAFT)
    with pytest.raises(ValueError):
        reg.move_to(h.id, HypothesisStatus.IDEA)


def test_move_to_rejected_via_move_to_raises():
    """move_to() must refuse REJECTED — use reject() instead."""
    reg = _registry()
    h = reg.create("title", "statement")
    with pytest.raises(ValueError, match="reject()"):
        reg.move_to(h.id, HypothesisStatus.REJECTED)


# ──────────────────────────────────────────────────────────────────────────────
# Reject
# ──────────────────────────────────────────────────────────────────────────────

def test_reject_sets_rejected_status():
    reg = _registry()
    h = reg.create("title", "statement")
    rejected = reg.reject(h.id, "insufficient evidence")
    assert rejected.status == HypothesisStatus.REJECTED


def test_reject_stores_rejection_reason():
    reg = _registry()
    h = reg.create("title", "statement")
    rejected = reg.reject(h.id, "p-value > 0.05")
    assert rejected.rejection_reason == "p-value > 0.05"


def test_reject_persists_to_repository():
    reg = _registry()
    h = reg.create("title", "statement")
    reg.reject(h.id, "reason")
    stored = reg.get(h.id)
    assert stored.status == HypothesisStatus.REJECTED
    assert stored.rejection_reason == "reason"


def test_reject_from_any_non_terminal_pipeline_stage():
    for status in _PIPELINE:
        reg = _registry()
        h = reg.create("title", "statement")
        _advance_to(reg, h.id, status)
        result = reg.reject(h.id, "rejected")
        assert result.status == HypothesisStatus.REJECTED


def test_reject_from_already_rejected_raises():
    reg = _registry()
    h = reg.create("title", "statement")
    reg.reject(h.id, "first rejection")
    with pytest.raises(ValueError, match="terminal"):
        reg.reject(h.id, "second rejection")


def test_reject_from_archived_raises():
    reg = _registry()
    h = reg.create("title", "statement")
    reg.archive(h.id)
    with pytest.raises(ValueError, match="terminal"):
        reg.reject(h.id, "reason")


# ──────────────────────────────────────────────────────────────────────────────
# Archive
# ──────────────────────────────────────────────────────────────────────────────

def test_archive_sets_archived_status():
    reg = _registry()
    h = reg.create("title", "statement")
    archived = reg.archive(h.id)
    assert archived.status == HypothesisStatus.ARCHIVED


def test_archive_from_any_non_terminal_pipeline_stage():
    for status in _PIPELINE:
        reg = _registry()
        h = reg.create("title", "statement")
        _advance_to(reg, h.id, status)
        result = reg.archive(h.id)
        assert result.status == HypothesisStatus.ARCHIVED


def test_archive_from_archived_raises():
    reg = _registry()
    h = reg.create("title", "statement")
    reg.archive(h.id)
    with pytest.raises(ValueError, match="terminal"):
        reg.archive(h.id)


def test_archive_from_rejected_raises():
    reg = _registry()
    h = reg.create("title", "statement")
    reg.reject(h.id, "reason")
    with pytest.raises(ValueError, match="terminal"):
        reg.archive(h.id)


# ──────────────────────────────────────────────────────────────────────────────
# Timestamps
# ──────────────────────────────────────────────────────────────────────────────

def test_created_at_is_datetime():
    reg = _registry()
    h = reg.create("title", "statement")
    assert isinstance(h.created_at, datetime)


def test_updated_at_is_datetime():
    reg = _registry()
    h = reg.create("title", "statement")
    assert isinstance(h.updated_at, datetime)


def test_updated_at_advances_on_transition():
    reg = HypothesisRegistry(_clock=_tick_clock())
    h = reg.create("title", "statement")
    created_updated = h.updated_at
    moved = reg.move_to(h.id, HypothesisStatus.DRAFT)
    assert moved.updated_at > created_updated


def test_created_at_does_not_change_on_transition():
    reg = HypothesisRegistry(_clock=_tick_clock())
    h = reg.create("title", "statement")
    original_created_at = h.created_at
    reg.move_to(h.id, HypothesisStatus.DRAFT)
    assert reg.get(h.id).created_at == original_created_at


def test_reject_advances_updated_at():
    reg = HypothesisRegistry(_clock=_tick_clock())
    h = reg.create("title", "statement")
    original_updated_at = h.updated_at
    rejected = reg.reject(h.id, "reason")
    assert rejected.updated_at > original_updated_at


# ──────────────────────────────────────────────────────────────────────────────
# Repository isolation
# ──────────────────────────────────────────────────────────────────────────────

def test_mutating_returned_hypothesis_does_not_affect_stored():
    reg = _registry()
    h = reg.create("title", "statement")
    # Mutate the returned object.
    h.title = "tampered"
    h.metadata["injected"] = True
    stored = reg.get(h.id)
    assert stored.title == "title"
    assert "injected" not in stored.metadata


def test_mutating_listed_hypothesis_does_not_affect_stored():
    reg = _registry()
    reg.create("title", "statement")
    listed = reg.list()
    listed[0].title = "tampered"
    stored = reg.get(listed[0].id)
    assert stored.title == "title"


def test_each_get_returns_independent_copy():
    reg = _registry()
    h = reg.create("title", "statement")
    copy_a = reg.get(h.id)
    copy_b = reg.get(h.id)
    copy_a.metadata["key"] = "value"
    assert "key" not in copy_b.metadata


def test_custom_repository_injected_via_protocol():
    """Registry accepts any HypothesisRepository implementation."""
    repo = MemoryHypothesisRepository()
    reg = HypothesisRegistry(repository=repo, _clock=_tick_clock())
    h = reg.create("title", "statement")
    assert repo.get(h.id) is not None


# ──────────────────────────────────────────────────────────────────────────────
# Determinism
# ──────────────────────────────────────────────────────────────────────────────

def test_deterministic_same_transitions_same_final_status():
    def run() -> HypothesisStatus:
        reg = _registry()
        h = reg.create("title", "statement")
        reg.move_to(h.id, HypothesisStatus.DRAFT)
        reg.move_to(h.id, HypothesisStatus.RESEARCH)
        return reg.get(h.id).status

    assert run() == run()


def test_deterministic_reject_reason_preserved():
    def run() -> str | None:
        reg = _registry()
        h = reg.create("title", "statement")
        reg.reject(h.id, "repeatable reason")
        return reg.get(h.id).rejection_reason

    assert run() == run()


# ──────────────────────────────────────────────────────────────────────────────
# create() with metadata kwarg (added in v3.3 for HypothesisGenerator)
# ──────────────────────────────────────────────────────────────────────────────

def test_create_with_metadata_stores_values():
    reg = _registry()
    h = reg.create("title", "statement", metadata={"template_id": "tmpl_x"})
    assert h.metadata["template_id"] == "tmpl_x"


def test_create_with_metadata_does_not_alias_caller_dict():
    reg = _registry()
    caller_dict = {"template_id": "tmpl_x"}
    h = reg.create("title", "statement", metadata=caller_dict)
    caller_dict["template_id"] = "MUTATED"
    assert reg.get(h.id).metadata["template_id"] == "tmpl_x"


def test_create_without_metadata_defaults_to_empty_dict():
    reg = _registry()
    h = reg.create("title", "statement")
    assert h.metadata == {}


def test_create_metadata_kwarg_is_keyword_only():
    reg = _registry()
    with pytest.raises(TypeError):
        reg.create("title", "statement", {"positional": "not allowed"})  # type: ignore[call-arg]
