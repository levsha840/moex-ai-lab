"""Protocols for the Hypothesis Generator Module."""
from __future__ import annotations

from typing import Protocol

from core.hypothesis_generator.models import HypothesisCandidate, HypothesisTemplate, TemplateStats


class TemplateRepository(Protocol):
    """Read/write store for HypothesisTemplate objects."""

    def add(self, template: HypothesisTemplate) -> None: ...
    def get(self, template_id: str) -> HypothesisTemplate: ...  # raises KeyError if absent
    def list(self) -> list[HypothesisTemplate]: ...
    def list_by_category(self, category: str) -> list[HypothesisTemplate]: ...


class CandidateRanker(Protocol):
    """Ranks a list of candidates. Must not mutate the input list."""

    def rank(self, candidates: list[HypothesisCandidate]) -> list[HypothesisCandidate]: ...


class TemplateStatisticsProvider(Protocol):
    """Provides pre-computed TemplateStats indexed by template_id.

    Implementations are responsible for gathering and aggregating raw data
    (e.g. from KnowledgeBase + HypothesisRegistry). KnowledgeRanker only
    consumes the result — it has no knowledge of the data source.
    """

    def get_stats(self) -> dict[str, TemplateStats]: ...
