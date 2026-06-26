from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.knowledge import (
    KnowledgeBase,
    KnowledgeEntry,
    KnowledgeType,
    MemoryKnowledgeRepository,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _tick_clock():
    counter = [0]

    def clock() -> datetime:
        counter[0] += 1
        return datetime(2026, 1, 1, 0, 0, 0, counter[0], tzinfo=timezone.utc)

    return clock


def _kb() -> KnowledgeBase:
    return KnowledgeBase(_clock=_tick_clock())


def _record(kb: KnowledgeBase, **kwargs) -> KnowledgeEntry:
    defaults = dict(
        knowledge_type=KnowledgeType.OBSERVATION,
        reference_id="ref_001",
        summary="A basic observation.",
    )
    defaults.update(kwargs)
    return kb.record(**defaults)


# ──────────────────────────────────────────────────────────────────────────────
# Empty repository
# ──────────────────────────────────────────────────────────────────────────────

def test_empty_list():
    kb = _kb()
    assert kb.list() == []


def test_empty_find_by_tag():
    kb = _kb()
    assert kb.find_by_tag("rsi") == []


def test_empty_find_by_type():
    kb = _kb()
    assert kb.find_by_type(KnowledgeType.EXPERIMENT) == []


def test_get_unknown_raises_key_error():
    kb = _kb()
    with pytest.raises(KeyError):
        kb.get("nonexistent")


# ──────────────────────────────────────────────────────────────────────────────
# Record
# ──────────────────────────────────────────────────────────────────────────────

def test_record_returns_knowledge_entry():
    kb = _kb()
    entry = _record(kb)
    assert isinstance(entry, KnowledgeEntry)


def test_record_stores_knowledge_type():
    kb = _kb()
    entry = _record(kb, knowledge_type=KnowledgeType.EXPERIMENT)
    assert entry.knowledge_type == KnowledgeType.EXPERIMENT


def test_record_stores_reference_id():
    kb = _kb()
    entry = _record(kb, reference_id="exp_42")
    assert entry.reference_id == "exp_42"


def test_record_stores_summary():
    kb = _kb()
    entry = _record(kb, summary="RSI signal is strong in ranging markets.")
    assert entry.summary == "RSI signal is strong in ranging markets."


def test_record_stores_tags():
    kb = _kb()
    entry = _record(kb, tags=["rsi", "range", "signal"])
    assert entry.tags == ["rsi", "range", "signal"]


def test_record_default_tags_is_empty_list():
    kb = _kb()
    entry = _record(kb)
    assert entry.tags == []


def test_record_stores_metadata():
    kb = _kb()
    entry = _record(kb, metadata={"sharpe": 1.4, "window": 60})
    assert entry.metadata == {"sharpe": 1.4, "window": 60}


def test_record_default_metadata_is_empty_dict():
    kb = _kb()
    entry = _record(kb)
    assert entry.metadata == {}


def test_record_id_is_non_empty_string():
    kb = _kb()
    entry = _record(kb)
    assert isinstance(entry.id, str)
    assert len(entry.id) > 0


def test_record_created_at_is_datetime():
    kb = _kb()
    entry = _record(kb)
    assert isinstance(entry.created_at, datetime)


# ──────────────────────────────────────────────────────────────────────────────
# UUID generation
# ──────────────────────────────────────────────────────────────────────────────

def test_uuid_generation_unique_ids():
    kb = _kb()
    ids = {_record(kb, reference_id=str(i)).id for i in range(20)}
    assert len(ids) == 20


# ──────────────────────────────────────────────────────────────────────────────
# Get
# ──────────────────────────────────────────────────────────────────────────────

def test_get_entry_by_id():
    kb = _kb()
    entry = _record(kb, reference_id="target")
    fetched = kb.get(entry.id)
    assert fetched.id == entry.id
    assert fetched.reference_id == "target"


def test_get_after_multiple_records():
    kb = _kb()
    a = _record(kb, reference_id="a")
    _record(kb, reference_id="b")
    _record(kb, reference_id="c")
    assert kb.get(a.id).reference_id == "a"


# ──────────────────────────────────────────────────────────────────────────────
# List
# ──────────────────────────────────────────────────────────────────────────────

def test_list_returns_all_entries():
    kb = _kb()
    for i in range(5):
        _record(kb, reference_id=str(i))
    assert len(kb.list()) == 5


def test_list_entries_contain_correct_reference_ids():
    kb = _kb()
    _record(kb, reference_id="alpha")
    _record(kb, reference_id="beta")
    refs = {e.reference_id for e in kb.list()}
    assert refs == {"alpha", "beta"}


# ──────────────────────────────────────────────────────────────────────────────
# Filter by tag
# ──────────────────────────────────────────────────────────────────────────────

def test_find_by_tag_returns_matching_entries():
    kb = _kb()
    _record(kb, tags=["rsi", "momentum"])
    _record(kb, tags=["sma", "trend"])
    _record(kb, tags=["rsi", "range"])
    results = kb.find_by_tag("rsi")
    assert len(results) == 2


def test_find_by_tag_no_match_returns_empty():
    kb = _kb()
    _record(kb, tags=["sma"])
    assert kb.find_by_tag("nonexistent_tag") == []


def test_find_by_tag_partial_match_not_counted():
    kb = _kb()
    _record(kb, tags=["rsi_14"])
    assert kb.find_by_tag("rsi") == []


def test_find_by_tag_returns_only_matching():
    kb = _kb()
    _record(kb, reference_id="match", tags=["target"])
    _record(kb, reference_id="no_match", tags=["other"])
    results = kb.find_by_tag("target")
    assert len(results) == 1
    assert results[0].reference_id == "match"


def test_find_by_tag_entry_with_multiple_tags():
    kb = _kb()
    _record(kb, tags=["a", "b", "c"])
    assert len(kb.find_by_tag("b")) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Filter by type
# ──────────────────────────────────────────────────────────────────────────────

def test_find_by_type_returns_matching_entries():
    kb = _kb()
    _record(kb, knowledge_type=KnowledgeType.EXPERIMENT)
    _record(kb, knowledge_type=KnowledgeType.EXPERIMENT)
    _record(kb, knowledge_type=KnowledgeType.REGIME)
    results = kb.find_by_type(KnowledgeType.EXPERIMENT)
    assert len(results) == 2


def test_find_by_type_no_match_returns_empty():
    kb = _kb()
    _record(kb, knowledge_type=KnowledgeType.OBSERVATION)
    assert kb.find_by_type(KnowledgeType.VALIDATION) == []


def test_find_by_type_returns_only_matching():
    kb = _kb()
    _record(kb, knowledge_type=KnowledgeType.HYPOTHESIS, reference_id="hyp")
    _record(kb, knowledge_type=KnowledgeType.FEATURE, reference_id="feat")
    results = kb.find_by_type(KnowledgeType.HYPOTHESIS)
    assert len(results) == 1
    assert results[0].reference_id == "hyp"


def test_find_by_type_all_types_independent():
    kb = _kb()
    for kt in KnowledgeType:
        _record(kb, knowledge_type=kt)
    for kt in KnowledgeType:
        results = kb.find_by_type(kt)
        assert len(results) == 1
        assert results[0].knowledge_type == kt


# ──────────────────────────────────────────────────────────────────────────────
# Deterministic clock
# ──────────────────────────────────────────────────────────────────────────────

def test_deterministic_clock_timestamps_are_from_injected_clock():
    fixed_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    kb = KnowledgeBase(_clock=lambda: fixed_time)
    entry = _record(kb)
    assert entry.created_at == fixed_time


def test_deterministic_clock_monotonically_increasing():
    kb = KnowledgeBase(_clock=_tick_clock())
    a = _record(kb)
    b = _record(kb)
    assert b.created_at > a.created_at


# ──────────────────────────────────────────────────────────────────────────────
# Deepcopy isolation
# ──────────────────────────────────────────────────────────────────────────────

def test_mutating_recorded_entry_does_not_affect_stored():
    kb = _kb()
    entry = _record(kb, tags=["original"])
    entry.tags.append("injected")
    entry.metadata["key"] = "value"
    stored = kb.get(entry.id)
    assert stored.tags == ["original"]
    assert "key" not in stored.metadata


def test_mutating_listed_entry_does_not_affect_stored():
    kb = _kb()
    _record(kb, reference_id="target", tags=["keep"])
    listed = kb.list()
    listed[0].tags.clear()
    stored = kb.get(listed[0].id)
    assert stored.tags == ["keep"]


def test_mutating_found_by_tag_does_not_affect_stored():
    kb = _kb()
    _record(kb, tags=["search"])
    results = kb.find_by_tag("search")
    results[0].summary = "tampered"
    stored = kb.get(results[0].id)
    assert stored.summary != "tampered"


def test_mutating_found_by_type_does_not_affect_stored():
    kb = _kb()
    _record(kb, knowledge_type=KnowledgeType.FEATURE, reference_id="original")
    results = kb.find_by_type(KnowledgeType.FEATURE)
    results[0].reference_id = "tampered"
    stored = kb.get(results[0].id)
    assert stored.reference_id == "original"


def test_each_get_returns_independent_copy():
    kb = _kb()
    entry = _record(kb)
    copy_a = kb.get(entry.id)
    copy_b = kb.get(entry.id)
    copy_a.metadata["key"] = "value"
    assert "key" not in copy_b.metadata


# ──────────────────────────────────────────────────────────────────────────────
# Repository isolation
# ──────────────────────────────────────────────────────────────────────────────

def test_custom_repository_accepted_via_protocol():
    repo = MemoryKnowledgeRepository()
    kb = KnowledgeBase(repository=repo, _clock=_tick_clock())
    entry = _record(kb)
    assert repo.get(entry.id) is not None


def test_repository_delete_removes_entry():
    kb = _kb()
    entry = _record(kb)
    kb.delete(entry.id)
    assert kb.list() == []


def test_delete_unknown_raises_key_error():
    kb = _kb()
    with pytest.raises(KeyError):
        kb.delete("nonexistent")


# ──────────────────────────────────────────────────────────────────────────────
# Passing tags/metadata by reference does not cause aliasing
# ──────────────────────────────────────────────────────────────────────────────

def test_passed_tags_list_mutation_does_not_affect_stored():
    kb = _kb()
    tags = ["a", "b"]
    entry = kb.record(
        knowledge_type=KnowledgeType.OBSERVATION,
        reference_id="ref",
        summary="s",
        tags=tags,
    )
    tags.append("c")
    stored = kb.get(entry.id)
    assert "c" not in stored.tags


def test_passed_metadata_mutation_does_not_affect_stored():
    kb = _kb()
    meta = {"x": 1}
    entry = kb.record(
        knowledge_type=KnowledgeType.OBSERVATION,
        reference_id="ref",
        summary="s",
        metadata=meta,
    )
    meta["y"] = 2
    stored = kb.get(entry.id)
    assert "y" not in stored.metadata
