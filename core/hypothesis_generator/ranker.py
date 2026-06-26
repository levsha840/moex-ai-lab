"""Concrete CandidateRanker implementations."""
from __future__ import annotations

from core.hypothesis_generator.models import HypothesisCandidate


class PriorityRanker:
    """Ranks candidates by score descending. Returns a new list; input is unchanged."""

    def rank(self, candidates: list[HypothesisCandidate]) -> list[HypothesisCandidate]:
        return sorted(candidates, key=lambda c: c.score, reverse=True)
