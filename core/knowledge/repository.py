from __future__ import annotations

import copy
from typing import Protocol

from core.knowledge.models import KnowledgeEntry, KnowledgeType


class KnowledgeRepository(Protocol):
    def add(self, entry: KnowledgeEntry) -> None: ...
    def get(self, id: str) -> KnowledgeEntry | None: ...
    def list(self) -> list[KnowledgeEntry]: ...
    def delete(self, id: str) -> None: ...
    def find_by_tag(self, tag: str) -> list[KnowledgeEntry]: ...
    def find_by_type(self, knowledge_type: KnowledgeType) -> list[KnowledgeEntry]: ...


class MemoryKnowledgeRepository:
    """In-memory KnowledgeRepository.

    Deep-copies on every store and retrieval so external mutation of returned
    objects cannot corrupt stored state.
    """

    def __init__(self) -> None:
        self._store: dict[str, KnowledgeEntry] = {}

    def add(self, entry: KnowledgeEntry) -> None:
        if entry.id in self._store:
            raise ValueError(f"KnowledgeEntry already exists: {entry.id!r}")
        self._store[entry.id] = copy.deepcopy(entry)

    def get(self, id: str) -> KnowledgeEntry | None:
        stored = self._store.get(id)
        return copy.deepcopy(stored) if stored is not None else None

    def list(self) -> list[KnowledgeEntry]:
        return [copy.deepcopy(e) for e in self._store.values()]

    def delete(self, id: str) -> None:
        if id not in self._store:
            raise KeyError(f"KnowledgeEntry not found: {id!r}")
        del self._store[id]

    def find_by_tag(self, tag: str) -> list[KnowledgeEntry]:
        return [
            copy.deepcopy(e)
            for e in self._store.values()
            if tag in e.tags
        ]

    def find_by_type(self, knowledge_type: KnowledgeType) -> list[KnowledgeEntry]:
        return [
            copy.deepcopy(e)
            for e in self._store.values()
            if e.knowledge_type == knowledge_type
        ]
