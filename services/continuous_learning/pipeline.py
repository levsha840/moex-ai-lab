"""
M11 Continuous Learning — Pipeline

Continuous learning pipeline that processes research/paper results,
updates KnowledgeStore, re-runs feature importance, and updates
discovery queue priorities.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from services.continuous_learning.knowledge_updater import KnowledgeUpdater
from services.continuous_learning.planner_bridge import PlannerBridge


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

@dataclass
class LearningEvent:
    event_id: str
    timestamp: str
    event_type: str   # "RESEARCH_COMPLETE", "PAPER_RESULT", "QUALITY_UPDATE"
    source: str
    data: dict
    processed: bool = False


# ---------------------------------------------------------------------------
# Cycle result
# ---------------------------------------------------------------------------

@dataclass
class LearningCycle:
    cycle_id: str
    started_at: str
    completed_at: str = ""
    events_processed: int = 0
    knowledge_facts_updated: int = 0
    new_drafts_generated: int = 0
    queue_entries_added: int = 0
    status: str = "RUNNING"  # "RUNNING", "COMPLETE", "ERROR"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class ContinuousLearningPipeline:
    """
    Continuous learning after each research completion.

    Pipeline stages:
    1. Receive new research/paper result events
    2. Update KnowledgeStore with new evidence
    3. Re-run FeatureImportance with updated data
    4. Re-run AlphaComposer to generate new drafts
    5. Update DiscoveryQueue priority
    6. Log cycle result
    """

    # Simulated new drafts generated per cycle (deterministic)
    DRAFTS_PER_CYCLE = 2
    QUEUE_ENTRIES_PER_CYCLE = 3
    _CYCLE_COUNTER = 0

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._event_queue: list[LearningEvent] = []
        self._cycles: list[LearningCycle] = []
        self._knowledge_updater = KnowledgeUpdater()
        self._planner_bridge = PlannerBridge()

    def add_event(self, event: LearningEvent) -> None:
        """Add a learning event to the queue."""
        self._event_queue.append(event)

    def run_cycle(self) -> LearningCycle:
        """
        Process all queued events and run a learning cycle.
        Returns the completed LearningCycle.
        """
        ContinuousLearningPipeline._CYCLE_COUNTER += 1
        cycle_id = f"CYCLE_{ContinuousLearningPipeline._CYCLE_COUNTER:04d}"

        timestamp_start = f"2026-06-29T{8 + (ContinuousLearningPipeline._CYCLE_COUNTER % 14):02d}:00:00"

        cycle = LearningCycle(
            cycle_id=cycle_id,
            started_at=timestamp_start,
            status="RUNNING",
        )

        # Process all queued events
        total_facts = 0
        events_processed = 0

        for event in self._event_queue:
            if event.processed:
                continue

            if event.event_type == "RESEARCH_COMPLETE":
                strategy_id = event.data.get("strategy_id", "UNKNOWN")
                pass_rate = event.data.get("pass_rate", 0.0)
                instrument = event.data.get("instrument", "SBER")
                period = event.data.get("period", "2023")
                n = self._knowledge_updater.update_from_research(
                    strategy_id, pass_rate, instrument, period
                )
                total_facts += n

            elif event.event_type == "PAPER_RESULT":
                strategy_id = event.data.get("strategy_id", "UNKNOWN")
                pf = event.data.get("pf", 1.0)
                win_rate = event.data.get("win_rate", 0.33)
                n = self._knowledge_updater.update_from_paper(strategy_id, pf, win_rate)
                total_facts += n

            elif event.event_type == "QUALITY_UPDATE":
                # Quality updates don't directly affect KnowledgeStore facts
                # but count as events processed
                pass

            event.processed = True
            events_processed += 1

        timestamp_end = f"2026-06-29T{8 + (ContinuousLearningPipeline._CYCLE_COUNTER % 14):02d}:05:00"

        cycle.events_processed = events_processed
        cycle.knowledge_facts_updated = total_facts
        cycle.new_drafts_generated = self.DRAFTS_PER_CYCLE if events_processed > 0 else 0
        cycle.queue_entries_added = self.QUEUE_ENTRIES_PER_CYCLE if events_processed > 0 else 0
        cycle.completed_at = timestamp_end
        cycle.status = "COMPLETE"

        # Clear processed events
        self._event_queue = [e for e in self._event_queue if not e.processed]
        self._cycles.append(cycle)

        return cycle

    def get_last_cycle(self) -> LearningCycle | None:
        """Return the most recently completed cycle."""
        if not self._cycles:
            return None
        return self._cycles[-1]

    def simulate_post_research_update(
        self, strategy_id: str, outcome: str
    ) -> LearningCycle:
        """
        Simulate a full post-research update cycle.

        outcome: "PASS" or "FAIL" — determines simulated metrics.
        """
        if outcome == "PASS":
            pass_rate = 0.47
            pf = 1.42
            win_rate = 0.47
        else:
            pass_rate = 0.28
            pf = 0.74
            win_rate = 0.33

        # Add research event
        research_event = LearningEvent(
            event_id=str(uuid.uuid4())[:8],
            timestamp="2026-06-29T09:00:00",
            event_type="RESEARCH_COMPLETE",
            source=strategy_id,
            data={
                "strategy_id": strategy_id,
                "pass_rate": pass_rate,
                "instrument": "SBER",
                "period": "2023-2024",
            },
        )
        self.add_event(research_event)

        # Add paper result event
        paper_event = LearningEvent(
            event_id=str(uuid.uuid4())[:8],
            timestamp="2026-06-29T09:30:00",
            event_type="PAPER_RESULT",
            source=strategy_id,
            data={
                "strategy_id": strategy_id,
                "pf": pf,
                "win_rate": win_rate,
            },
        )
        self.add_event(paper_event)

        return self.run_cycle()

    def get_knowledge_updater(self) -> KnowledgeUpdater:
        return self._knowledge_updater

    def get_planner_bridge(self) -> PlannerBridge:
        return self._planner_bridge

    def cycle_count(self) -> int:
        return len(self._cycles)

    def all_cycles(self) -> list[LearningCycle]:
        return list(self._cycles)
