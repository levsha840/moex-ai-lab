"""
M10 Alpha Discovery — Discovery Queue

Priority queue for new strategy drafts. Provides ranked ordering for
Adaptive Planner integration.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.alpha_discovery.alpha_composer import StrategyDraft
from services.alpha_discovery.net_edge_predictor import CURRENT_MOEX_REGIME

# ---------------------------------------------------------------------------
# Research cost estimation
# ---------------------------------------------------------------------------

def _estimate_research_cost(features: list[str]) -> str:
    """
    Estimate research cost based on feature complexity.

    LOW:    <= 3 features, all in M8 data
    MEDIUM: 4-5 features or includes VWAP
    HIGH:   6+ features or includes TIME_FILTER + VWAP
    """
    n = len(features)
    untested = {"VWAP", "TIME_FILTER"}
    has_untested = any(f in untested for f in features)

    if n <= 3 and not has_untested:
        return "LOW"
    elif n <= 5 and not has_untested:
        return "MEDIUM"
    elif n <= 5 and has_untested:
        return "MEDIUM"
    else:
        return "HIGH"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class QueueEntry:
    rank: int
    draft_id: str
    name: str
    priority_score: float
    expected_net_edge_pct: float
    target_regimes: list[str]
    target_timeframes: list[str]
    features: list[str]
    status: str                    # "QUEUED"
    estimated_research_cost: str   # "LOW", "MEDIUM", "HIGH"


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

class DiscoveryQueue:
    """Priority queue for strategy drafts, ranked by composite priority score."""

    def __init__(self) -> None:
        self._entries: list[QueueEntry] = []

    def enqueue(self, draft: StrategyDraft) -> None:
        """Add a strategy draft to the queue (rank assigned on prioritize())."""
        entry = QueueEntry(
            rank=0,  # set by prioritize()
            draft_id=draft.draft_id,
            name=draft.name,
            priority_score=draft.priority_score,
            expected_net_edge_pct=draft.expected_net_edge_pct,
            target_regimes=list(draft.target_regimes),
            target_timeframes=list(draft.target_timeframes),
            features=list(draft.features),
            status="QUEUED",
            estimated_research_cost=_estimate_research_cost(draft.features),
        )
        self._entries.append(entry)

    def prioritize(self) -> list[QueueEntry]:
        """Sort queue by priority_score and assign ranks. Returns sorted list."""
        self._entries.sort(key=lambda e: e.priority_score, reverse=True)
        for i, entry in enumerate(self._entries, start=1):
            entry.rank = i
        return list(self._entries)

    def get_top_n(self, n: int) -> list[QueueEntry]:
        """Return top N entries by priority. Triggers re-prioritization."""
        ranked = self.prioritize()
        return ranked[:n]

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self.prioritize())
