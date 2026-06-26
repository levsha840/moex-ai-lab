"""Hypothesis Generator Module — core orchestration."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from core.hypothesis.models import Hypothesis
from core.hypothesis.service import HypothesisRegistry
from core.hypothesis_generator.models import (
    GenerationConfig,
    GenerationSession,
    HypothesisCandidate,
)
from core.hypothesis_generator.protocols import CandidateRanker, TemplateRepository


class HypothesisGenerator:
    """Generates ranked HypothesisCandidate objects from HypothesisTemplate definitions.

    Protocol-based: accepts any TemplateRepository and CandidateRanker.
    Fully deterministic given the same templates and config (candidate IDs use uuid4
    and will differ between runs; content — title, statement, score — is deterministic).

    Dependency: hypothesis_generator → hypothesis (via accept()).
    No dependency on knowledge, experiment, research_pipeline, or validation.
    """

    def __init__(
        self,
        template_repo: TemplateRepository,
        ranker: CandidateRanker,
        *,
        _clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = template_repo
        self._ranker = ranker
        self._clock: Callable[[], datetime] = _clock or (
            lambda: datetime.now(timezone.utc)
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def generate(self, config: GenerationConfig) -> GenerationSession:
        """Generate, rank, and filter candidates according to config.

        Steps:
          1. Load templates (filtered by allowed_categories when set).
          2. Instantiate one candidate per template using default_parameters.
          3. Rank via ranker.rank().
          4. Apply min_score filter.
          5. Cap at max_candidates.
          6. Wrap in an immutable GenerationSession.
        """
        templates = self._load_templates(config)
        now = self._clock()

        candidates: list[HypothesisCandidate] = []
        for template in templates:
            title, statement = template.instantiate()
            candidates.append(
                HypothesisCandidate(
                    candidate_id=uuid4().hex,
                    template_id=template.template_id,
                    title=title,
                    statement=statement,
                    parameters=copy.deepcopy(template.default_parameters),
                    score=template.base_score,
                    rationale=(
                        f"Template priority {template.priority.value} "
                        f"(base score {template.base_score:.2f})"
                    ),
                    created_at=now,
                )
            )

        ranked = self._ranker.rank(candidates)
        filtered = [c for c in ranked if c.score >= config.min_score]
        final = filtered[: config.max_candidates]

        return GenerationSession(
            session_id=uuid4().hex,
            created_at=now,
            config=config,
            generated_candidates=tuple(final),
        )

    def accept(
        self,
        candidate: HypothesisCandidate,
        registry: HypothesisRegistry,
    ) -> Hypothesis:
        """Register an accepted candidate in HypothesisRegistry as IDEA status.

        Stores template_id in Hypothesis.metadata for future deduplication.
        """
        return registry.create(
            candidate.title,
            candidate.statement,
            metadata={"template_id": candidate.template_id},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _load_templates(self, config: GenerationConfig) -> list:
        if config.allowed_categories is None:
            return self._repo.list()

        seen: set[str] = set()
        templates = []
        for category in config.allowed_categories:
            for t in self._repo.list_by_category(category):
                if t.template_id not in seen:
                    templates.append(t)
                    seen.add(t.template_id)
        return templates
