from __future__ import annotations

import copy
from typing import Protocol

from core.hypothesis.models import Hypothesis


class HypothesisRepository(Protocol):
    def add(self, hypothesis: Hypothesis) -> None: ...
    def update(self, hypothesis: Hypothesis) -> None: ...
    def get(self, id: str) -> Hypothesis | None: ...
    def list(self) -> list[Hypothesis]: ...
    def delete(self, id: str) -> None: ...


class MemoryHypothesisRepository:
    """In-memory implementation of HypothesisRepository.

    Stores deep copies of hypotheses so that external mutation of returned
    objects cannot corrupt stored state.
    """

    def __init__(self) -> None:
        self._store: dict[str, Hypothesis] = {}

    def add(self, hypothesis: Hypothesis) -> None:
        if hypothesis.id in self._store:
            raise ValueError(f"Hypothesis already exists: {hypothesis.id!r}")
        self._store[hypothesis.id] = copy.deepcopy(hypothesis)

    def update(self, hypothesis: Hypothesis) -> None:
        if hypothesis.id not in self._store:
            raise KeyError(f"Hypothesis not found: {hypothesis.id!r}")
        self._store[hypothesis.id] = copy.deepcopy(hypothesis)

    def get(self, id: str) -> Hypothesis | None:
        stored = self._store.get(id)
        return copy.deepcopy(stored) if stored is not None else None

    def list(self) -> list[Hypothesis]:
        return [copy.deepcopy(h) for h in self._store.values()]

    def delete(self, id: str) -> None:
        if id not in self._store:
            raise KeyError(f"Hypothesis not found: {id!r}")
        del self._store[id]
