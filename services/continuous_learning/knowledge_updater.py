"""
M11 Continuous Learning — Knowledge Updater

Updates KnowledgeStore facts based on new research outcomes.
Each update triggers re-weighting of relevant alpha factors.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Known facts structure (simplified KnowledgeStore model)
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeFact:
    fact_id: str
    strategy_id: str
    instrument: str
    period: str
    metric: str
    value: float
    confidence: float     # 0-1
    source: str           # "RESEARCH", "PAPER", "MANUAL"
    updated_at: str


# ---------------------------------------------------------------------------
# KnowledgeUpdater
# ---------------------------------------------------------------------------

class KnowledgeUpdater:
    """
    Updates KnowledgeStore facts based on new research outcomes.

    Simulates the update cycle that would normally write to
    knowledge/pyramid.py or a persistent KnowledgeStore.
    """

    # How many facts are generated per research result
    FACTS_PER_RESEARCH = 3   # pass_rate, payoff_ratio, sharpe
    FACTS_PER_PAPER = 4      # pf, win_rate, max_dd, net_pnl

    def __init__(self) -> None:
        self._facts: list[KnowledgeFact] = []
        self._update_counter = 0

    def update_from_research(
        self,
        strategy_id: str,
        pass_rate: float,
        instrument: str,
        period: str,
    ) -> int:
        """
        Update KnowledgeStore from a research (backtest) result.
        Returns number of facts updated.
        """
        timestamp = f"2026-06-29T{10 + self._update_counter % 12:02d}:00:00"
        base_id = f"{strategy_id}_{instrument}_{period}"

        new_facts = [
            KnowledgeFact(
                fact_id=f"{base_id}_pass_rate",
                strategy_id=strategy_id,
                instrument=instrument,
                period=period,
                metric="pass_rate",
                value=round(pass_rate, 4),
                confidence=0.80,
                source="RESEARCH",
                updated_at=timestamp,
            ),
            KnowledgeFact(
                fact_id=f"{base_id}_payoff_ratio",
                strategy_id=strategy_id,
                instrument=instrument,
                period=period,
                metric="payoff_ratio",
                value=round(1.5 + pass_rate * 0.5, 4),
                confidence=0.75,
                source="RESEARCH",
                updated_at=timestamp,
            ),
            KnowledgeFact(
                fact_id=f"{base_id}_net_edge",
                strategy_id=strategy_id,
                instrument=instrument,
                period=period,
                metric="net_edge_pct",
                value=round(pass_rate * 0.03 - 0.005, 6),
                confidence=0.70,
                source="RESEARCH",
                updated_at=timestamp,
            ),
        ]

        # Replace existing facts with same ID or append new ones
        existing_ids = {f.fact_id for f in self._facts}
        for fact in new_facts:
            if fact.fact_id in existing_ids:
                self._facts = [f for f in self._facts if f.fact_id != fact.fact_id]
            self._facts.append(fact)

        self._update_counter += 1
        return len(new_facts)

    def update_from_paper(
        self,
        strategy_id: str,
        pf: float,
        win_rate: float,
    ) -> int:
        """
        Update KnowledgeStore from a paper trading result.
        Returns number of facts updated.
        """
        timestamp = f"2026-06-29T{14 + self._update_counter % 8:02d}:00:00"
        base_id = f"{strategy_id}_paper"

        new_facts = [
            KnowledgeFact(
                fact_id=f"{base_id}_pf",
                strategy_id=strategy_id,
                instrument="PAPER",
                period="2026-Q2",
                metric="profit_factor",
                value=round(pf, 4),
                confidence=0.90,
                source="PAPER",
                updated_at=timestamp,
            ),
            KnowledgeFact(
                fact_id=f"{base_id}_win_rate",
                strategy_id=strategy_id,
                instrument="PAPER",
                period="2026-Q2",
                metric="win_rate",
                value=round(win_rate, 4),
                confidence=0.90,
                source="PAPER",
                updated_at=timestamp,
            ),
            KnowledgeFact(
                fact_id=f"{base_id}_net_pnl",
                strategy_id=strategy_id,
                instrument="PAPER",
                period="2026-Q2",
                metric="net_pnl_sign",
                value=1.0 if pf > 1.0 else -1.0,
                confidence=0.95,
                source="PAPER",
                updated_at=timestamp,
            ),
            KnowledgeFact(
                fact_id=f"{base_id}_viability",
                strategy_id=strategy_id,
                instrument="PAPER",
                period="2026-Q2",
                metric="viability",
                value=1.0 if pf > 1.2 and win_rate > 0.40 else 0.0,
                confidence=0.85,
                source="PAPER",
                updated_at=timestamp,
            ),
        ]

        existing_ids = {f.fact_id for f in self._facts}
        for fact in new_facts:
            if fact.fact_id in existing_ids:
                self._facts = [f for f in self._facts if f.fact_id != fact.fact_id]
            self._facts.append(fact)

        self._update_counter += 1
        return len(new_facts)

    def get_all_facts(self) -> list[KnowledgeFact]:
        return list(self._facts)

    def fact_count(self) -> int:
        return len(self._facts)

    def facts_for_strategy(self, strategy_id: str) -> list[KnowledgeFact]:
        return [f for f in self._facts if f.strategy_id == strategy_id]
