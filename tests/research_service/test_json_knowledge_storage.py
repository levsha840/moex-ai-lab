import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.knowledge.models import KnowledgeEntry, KnowledgeType
from services.research.persistence import JsonKnowledgeStorage


def _entry(
    id: str = "e1",
    knowledge_type: KnowledgeType = KnowledgeType.EXPERIMENT,
    reference_id: str = "hyp_001",
    summary: str = "test summary",
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> KnowledgeEntry:
    return KnowledgeEntry(
        id=id,
        knowledge_type=knowledge_type,
        reference_id=reference_id,
        summary=summary,
        tags=tags or ["tag1"],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata=metadata or {"key": "val"},
    )


class TestJsonKnowledgeStorageBasic:
    def test_starts_empty_when_no_file(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        assert storage.list() == []

    def test_add_and_get(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        e = _entry(id="e1")
        storage.add(e)
        result = storage.get("e1")
        assert result is not None
        assert result.id == "e1"
        assert result.summary == "test summary"

    def test_get_missing_returns_none(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        assert storage.get("nonexistent") is None

    def test_list_returns_all(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        storage.add(_entry(id="e1"))
        storage.add(_entry(id="e2"))
        ids = {e.id for e in storage.list()}
        assert ids == {"e1", "e2"}

    def test_duplicate_raises(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        storage.add(_entry(id="e1"))
        with pytest.raises(KeyError):
            storage.add(_entry(id="e1"))

    def test_delete_removes_entry(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        storage.add(_entry(id="e1"))
        storage.delete("e1")
        assert storage.get("e1") is None
        assert storage.list() == []

    def test_delete_missing_raises(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        with pytest.raises(KeyError):
            storage.delete("nonexistent")


class TestJsonKnowledgeStorageFilters:
    def test_find_by_tag(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        storage.add(_entry(id="e1", tags=["PASS", "adx"]))
        storage.add(_entry(id="e2", tags=["FAIL"]))
        results = storage.find_by_tag("PASS")
        assert len(results) == 1
        assert results[0].id == "e1"

    def test_find_by_type(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        storage.add(_entry(id="e1", knowledge_type=KnowledgeType.EXPERIMENT))
        storage.add(_entry(id="e2", knowledge_type=KnowledgeType.OBSERVATION))
        results = storage.find_by_type(KnowledgeType.EXPERIMENT)
        assert len(results) == 1
        assert results[0].id == "e1"

    def test_find_by_tag_returns_empty_when_no_match(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        storage.add(_entry(id="e1", tags=["FAIL"]))
        assert storage.find_by_tag("PASS") == []


class TestJsonKnowledgeStoragePersistence:
    def test_persists_to_disk_on_add(self, tmp_path):
        path = tmp_path / "kb.json"
        storage = JsonKnowledgeStorage(path)
        storage.add(_entry(id="e1"))
        assert path.exists()

    def test_json_has_version_field(self, tmp_path):
        path = tmp_path / "kb.json"
        storage = JsonKnowledgeStorage(path)
        storage.add(_entry(id="e1"))
        with open(path) as f:
            data = json.load(f)
        assert "version" in data
        assert "entries" in data

    def test_round_trip_preserves_fields(self, tmp_path):
        path = tmp_path / "kb.json"
        e = _entry(id="e1", tags=["A", "B"], metadata={"x": "1"})
        storage1 = JsonKnowledgeStorage(path)
        storage1.add(e)

        storage2 = JsonKnowledgeStorage(path)
        loaded = storage2.get("e1")
        assert loaded is not None
        assert loaded.id == "e1"
        assert loaded.knowledge_type == KnowledgeType.EXPERIMENT
        assert loaded.reference_id == "hyp_001"
        assert loaded.summary == "test summary"
        assert set(loaded.tags) == {"A", "B"}
        assert loaded.metadata == {"x": "1"}
        assert loaded.created_at == datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_load_existing_file(self, tmp_path):
        path = tmp_path / "kb.json"
        storage1 = JsonKnowledgeStorage(path)
        storage1.add(_entry(id="e1"))
        storage1.add(_entry(id="e2"))

        storage2 = JsonKnowledgeStorage(path)
        assert len(storage2.list()) == 2
        assert storage2.get("e1") is not None
        assert storage2.get("e2") is not None

    def test_add_persists_across_reload(self, tmp_path):
        path = tmp_path / "kb.json"
        JsonKnowledgeStorage(path).add(_entry(id="e1"))

        storage = JsonKnowledgeStorage(path)
        storage.add(_entry(id="e2"))

        reloaded = JsonKnowledgeStorage(path)
        ids = {e.id for e in reloaded.list()}
        assert ids == {"e1", "e2"}

    def test_get_returns_copy_not_reference(self, tmp_path):
        storage = JsonKnowledgeStorage(tmp_path / "kb.json")
        storage.add(_entry(id="e1"))
        copy1 = storage.get("e1")
        copy2 = storage.get("e1")
        assert copy1 is not copy2
