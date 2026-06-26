from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from core.knowledge.models import KnowledgeEntry, KnowledgeType
from core.knowledge.repository import KnowledgeRepository, MemoryKnowledgeRepository


class KnowledgeBase:
    """In-memory store for research knowledge.

    Records facts produced by experiments, regime classifications, feature
    analyses, and observations. Makes no decisions, draws no conclusions,
    performs no classification — it only stores and retrieves entries.

    Knows nothing about strategies, paper trading, brokers, databases, MOEX,
    or ExperimentRunner.
    """

    def __init__(
        self,
        repository: KnowledgeRepository | None = None,
        *,
        _clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo: KnowledgeRepository = repository or MemoryKnowledgeRepository()
        self._clock: Callable[[], datetime] = _clock or (
            lambda: datetime.now(timezone.utc)
        )

    def record(
        self,
        knowledge_type: KnowledgeType,
        reference_id: str,
        summary: str,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> KnowledgeEntry:
        entry = KnowledgeEntry(
            id=uuid4().hex,
            knowledge_type=knowledge_type,
            reference_id=reference_id,
            summary=summary,
            tags=list(tags) if tags is not None else [],
            created_at=self._clock(),
            metadata=dict(metadata) if metadata is not None else {},
        )
        self._repo.add(entry)
        return copy.deepcopy(entry)

    def get(self, entry_id: str) -> KnowledgeEntry:
        entry = self._repo.get(entry_id)
        if entry is None:
            raise KeyError(f"KnowledgeEntry not found: {entry_id!r}")
        return entry

    def list(self) -> list[KnowledgeEntry]:
        return self._repo.list()

    def find_by_tag(self, tag: str) -> list[KnowledgeEntry]:
        return self._repo.find_by_tag(tag)

    def find_by_type(self, knowledge_type: KnowledgeType) -> list[KnowledgeEntry]:
        return self._repo.find_by_type(knowledge_type)

    def delete(self, entry_id: str) -> None:
        self._repo.delete(entry_id)
