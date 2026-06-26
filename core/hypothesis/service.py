from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from core.hypothesis.models import Hypothesis, HypothesisStatus
from core.hypothesis.repository import HypothesisRepository, MemoryHypothesisRepository

# Forward pipeline — order is the contract.
_PIPELINE: list[HypothesisStatus] = [
    HypothesisStatus.IDEA,
    HypothesisStatus.DRAFT,
    HypothesisStatus.RESEARCH,
    HypothesisStatus.BACKTEST,
    HypothesisStatus.WALKFORWARD,
    HypothesisStatus.PAPER_TRADING,
    HypothesisStatus.PRODUCTION,
]

_TERMINAL: frozenset[HypothesisStatus] = frozenset(
    {HypothesisStatus.ARCHIVED, HypothesisStatus.REJECTED}
)


def _validate_move(current: HypothesisStatus, target: HypothesisStatus) -> None:
    """Raise ValueError if the requested transition is not permitted."""
    if current in _TERMINAL:
        raise ValueError(
            f"Cannot transition from terminal status {current.value!r}. "
            f"ARCHIVED and REJECTED are final states."
        )

    if target == HypothesisStatus.REJECTED:
        raise ValueError(
            "Use reject() to transition to REJECTED — a rejection reason is required."
        )

    if target == HypothesisStatus.ARCHIVED:
        return  # Allowed from any non-terminal status.

    # Forward-pipeline transition: only the immediate next step is permitted.
    current_idx = _PIPELINE.index(current)
    next_idx = current_idx + 1

    if next_idx >= len(_PIPELINE):
        raise ValueError(
            f"No forward pipeline transition from {current.value!r}."
        )

    expected = _PIPELINE[next_idx]
    if target != expected:
        raise ValueError(
            f"Invalid transition: {current.value!r} → {target.value!r}. "
            f"Stages cannot be skipped. Expected next: {expected.value!r}."
        )


class HypothesisRegistry:
    """Lifecycle manager for research hypotheses (in-memory).

    Knows nothing about strategies, experiments, validation, or databases.
    Enforces the pipeline transition rules and records timestamps.
    """

    def __init__(
        self,
        repository: HypothesisRepository | None = None,
        *,
        _clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo: HypothesisRepository = repository or MemoryHypothesisRepository()
        self._clock: Callable[[], datetime] = _clock or (
            lambda: datetime.now(timezone.utc)
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Mutations
    # ──────────────────────────────────────────────────────────────────────────

    def create(self, title: str, statement: str) -> Hypothesis:
        now = self._clock()
        hypothesis = Hypothesis(
            id=uuid4().hex,
            title=title,
            statement=statement,
            status=HypothesisStatus.IDEA,
            created_at=now,
            updated_at=now,
        )
        self._repo.add(hypothesis)
        return copy.deepcopy(hypothesis)

    def move_to(self, hypothesis_id: str, new_status: HypothesisStatus) -> Hypothesis:
        hypothesis = self._get_or_raise(hypothesis_id)
        _validate_move(hypothesis.status, new_status)
        hypothesis.status = new_status
        hypothesis.updated_at = self._clock()
        self._repo.update(hypothesis)
        return copy.deepcopy(hypothesis)

    def reject(self, hypothesis_id: str, reason: str) -> Hypothesis:
        hypothesis = self._get_or_raise(hypothesis_id)
        if hypothesis.status in _TERMINAL:
            raise ValueError(
                f"Cannot reject from terminal status {hypothesis.status.value!r}."
            )
        hypothesis.status = HypothesisStatus.REJECTED
        hypothesis.rejection_reason = reason
        hypothesis.updated_at = self._clock()
        self._repo.update(hypothesis)
        return copy.deepcopy(hypothesis)

    def archive(self, hypothesis_id: str) -> Hypothesis:
        return self.move_to(hypothesis_id, HypothesisStatus.ARCHIVED)

    def delete(self, hypothesis_id: str) -> None:
        self._repo.delete(hypothesis_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────────────────────────────────────

    def get(self, hypothesis_id: str) -> Hypothesis:
        h = self._repo.get(hypothesis_id)
        if h is None:
            raise KeyError(f"Hypothesis not found: {hypothesis_id!r}")
        return h

    def list(self) -> list[Hypothesis]:
        return self._repo.list()

    # ──────────────────────────────────────────────────────────────────────────

    def _get_or_raise(self, hypothesis_id: str) -> Hypothesis:
        h = self._repo.get(hypothesis_id)
        if h is None:
            raise KeyError(f"Hypothesis not found: {hypothesis_id!r}")
        return h
