"""Domain models for the Hypothesis Generator Module."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class HypothesisPriority(str, Enum):
    A = "A"
    B = "B"
    C = "C"


_PRIORITY_BASE_SCORES: dict[HypothesisPriority, float] = {
    HypothesisPriority.A: 1.0,
    HypothesisPriority.B: 0.7,
    HypothesisPriority.C: 0.4,
}


@dataclass
class HypothesisTemplate:
    """Parameterised hypothesis pattern that can be rendered into a concrete candidate.

    Templates live next to their experiments (e.g. experiments/h13_adx_continuation/template.py).
    """

    template_id: str
    name: str
    category: str
    priority: HypothesisPriority
    title_template: str        # f-string pattern: "ADX Continuation on {ticker}"
    statement_template: str    # full statement with {param} slots
    required_features: list[str]
    default_parameters: dict[str, Any]

    @property
    def base_score(self) -> float:
        return _PRIORITY_BASE_SCORES[self.priority]

    def instantiate(self, parameters: dict[str, Any] | None = None) -> tuple[str, str]:
        """Render title and statement by substituting parameters.

        Merges default_parameters with the overrides, then formats both templates.
        Raises KeyError if a required slot is missing from the merged dict.
        """
        params = {**self.default_parameters, **(parameters or {})}
        return self.title_template.format(**params), self.statement_template.format(**params)


@dataclass(frozen=True)
class GenerationConfig:
    """Immutable configuration controlling a single generation run."""

    max_candidates: int = 10
    min_score: float = 0.0
    allowed_categories: tuple[str, ...] | None = None  # None = all categories

    def __post_init__(self) -> None:
        if self.max_candidates <= 0:
            raise ValueError(
                f"max_candidates must be positive, got {self.max_candidates}"
            )
        if not 0.0 <= self.min_score <= 1.0:
            raise ValueError(
                f"min_score must be in [0.0, 1.0], got {self.min_score}"
            )


@dataclass
class HypothesisCandidate:
    """A generated hypothesis proposal — not yet in HypothesisRegistry."""

    candidate_id: str
    template_id: str
    title: str
    statement: str
    parameters: dict[str, Any]
    score: float
    rationale: str
    created_at: datetime


@dataclass(frozen=True)
class GenerationSession:
    """Immutable snapshot of a single generation run.

    Reserved for future automation: scheduling, batch acceptance, audit trail.
    """

    session_id: str
    created_at: datetime
    config: GenerationConfig
    generated_candidates: tuple[HypothesisCandidate, ...]
