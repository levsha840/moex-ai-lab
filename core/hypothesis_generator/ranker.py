"""Concrete CandidateRanker implementations."""
from __future__ import annotations

import copy

from core.hypothesis_generator.models import HypothesisCandidate, TemplateStats
from core.hypothesis_generator.protocols import TemplateStatisticsProvider


class PriorityRanker:
    """Ranks candidates by score descending. Returns a new list; input is unchanged."""

    def rank(self, candidates: list[HypothesisCandidate]) -> list[HypothesisCandidate]:
        return sorted(candidates, key=lambda c: c.score, reverse=True)


class KnowledgeRanker:
    """CandidateRanker that adjusts candidate scores using Knowledge Base history.

    Receives pre-built TemplateStats from a TemplateStatisticsProvider — has no
    direct dependency on KnowledgeBase or HypothesisRegistry.

    Scoring formula (per candidate):
        confidence_factor  = min(1.0, experiment_count / confidence_threshold)
        knowledge_multiplier = 1.0 + (pass_rate - 0.5) * max_adjustment * confidence_factor
        duplicate_penalty  = max(duplicate_penalty_floor, 1.0 - duplicate_step * experiment_count)
        final_score        = base_score * knowledge_multiplier * duplicate_penalty

    New templates (no KB history) always receive knowledge_multiplier = 1.0 and
    duplicate_penalty = 1.0, preserving their original base_score.

    Returns new HypothesisCandidate objects with updated score and rationale;
    input list and input objects are never mutated.

    Tie-breaking order: (-final_score, template_id, title) — stable across
    independent generation sessions because template_id and title are deterministic.
    """

    def __init__(
        self,
        stats_provider: TemplateStatisticsProvider,
        *,
        confidence_threshold: int = 5,
        max_adjustment: float = 1.0,
        duplicate_penalty_floor: float = 0.75,
        duplicate_step: float = 0.05,
    ) -> None:
        if confidence_threshold < 1:
            raise ValueError(
                f"confidence_threshold must be >= 1, got {confidence_threshold}"
            )
        if not 0.0 <= max_adjustment <= 2.0:
            raise ValueError(
                f"max_adjustment must be in [0.0, 2.0], got {max_adjustment}"
            )
        if not 0.0 <= duplicate_penalty_floor <= 1.0:
            raise ValueError(
                f"duplicate_penalty_floor must be in [0.0, 1.0], got {duplicate_penalty_floor}"
            )
        if duplicate_step < 0.0:
            raise ValueError(
                f"duplicate_step must be >= 0.0, got {duplicate_step}"
            )
        self._provider = stats_provider
        self._confidence_threshold = confidence_threshold
        self._max_adjustment = max_adjustment
        self._duplicate_penalty_floor = duplicate_penalty_floor
        self._duplicate_step = duplicate_step

    def rank(self, candidates: list[HypothesisCandidate]) -> list[HypothesisCandidate]:
        if not candidates:
            return []

        stats_map = self._provider.get_stats()

        scored: list[tuple[HypothesisCandidate, float, float]] = []
        for c in candidates:
            final_score, km = self._compute_score(c, stats_map)
            scored.append((c, final_score, km))

        scored.sort(key=lambda x: (-x[1], x[0].template_id, x[0].title))

        return [self._build_candidate(c, fs, km, stats_map) for c, fs, km in scored]

    # ──────────────────────────────────────────────────────────────────────────

    def _compute_score(
        self,
        candidate: HypothesisCandidate,
        stats_map: dict[str, TemplateStats],
    ) -> tuple[float, float]:
        """Returns (final_score, knowledge_multiplier)."""
        stats = stats_map.get(candidate.template_id)

        if stats is None or not stats.has_history:
            return candidate.score, 1.0

        confidence_factor = min(1.0, stats.experiment_count / self._confidence_threshold)
        km = 1.0 + (stats.pass_rate - 0.5) * self._max_adjustment * confidence_factor
        dp = max(
            self._duplicate_penalty_floor,
            1.0 - self._duplicate_step * stats.experiment_count,
        )
        return candidate.score * km * dp, km

    def _build_candidate(
        self,
        original: HypothesisCandidate,
        final_score: float,
        km: float,
        stats_map: dict[str, TemplateStats],
    ) -> HypothesisCandidate:
        stats = stats_map.get(original.template_id)

        if stats is not None and stats.has_history:
            rationale = (
                f"{original.rationale}; "
                f"KB: {stats.pass_count}P/{stats.fail_count}F "
                f"×{km:.2f}"
            )
        else:
            rationale = original.rationale

        return HypothesisCandidate(
            candidate_id=original.candidate_id,
            template_id=original.template_id,
            title=original.title,
            statement=original.statement,
            parameters=copy.deepcopy(original.parameters),
            score=final_score,
            rationale=rationale,
            created_at=original.created_at,
        )
