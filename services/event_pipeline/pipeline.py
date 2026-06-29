"""AutonomousPipeline — wires events and handlers into a single runnable chain.

Usage (programmatic):
    pipeline = AutonomousPipeline()
    results = pipeline.run(strategy_id="BB_SQUEEZE", outcome="FAIL", report_path="...")

Usage (CLI via scripts/run_event_pipeline.py).
"""
from __future__ import annotations

import logging
from pathlib import Path

from .bus import EventBus
from .events import ResearchFinished
from .handlers import (
    on_alpha_planner_updated,
    on_dashboard_updated,
    on_knowledge_updated,
    on_learning_updated,
    on_research_finished,
    on_validation_completed,
)

log = logging.getLogger(__name__)


class AutonomousPipeline:
    """
    Wires the complete research → dashboard event chain.

    ResearchFinished
      → KnowledgeUpdated
      → ValidationCompleted
      → AlphaPlannerUpdated
      → LearningUpdated
      → DashboardUpdated
    """

    def __init__(self, verbose: bool = False) -> None:
        self._bus = EventBus(verbose=verbose)
        self._register_handlers()

    def _register_handlers(self) -> None:
        bus = self._bus
        bus.subscribe("ResearchFinished",    on_research_finished)
        bus.subscribe("KnowledgeUpdated",    on_knowledge_updated)
        bus.subscribe("ValidationCompleted", on_validation_completed)
        bus.subscribe("AlphaPlannerUpdated", on_alpha_planner_updated)
        bus.subscribe("LearningUpdated",     on_learning_updated)
        bus.subscribe("DashboardUpdated",    on_dashboard_updated)

    def run(
        self,
        strategy_id: str = "UNKNOWN",
        outcome: str = "FAIL",
        report_path: str = "",
        session_id: str = "",
        findings_count: int = 0,
    ) -> dict:
        """Fire ResearchFinished and let the chain propagate automatically."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s  %(levelname)-7s  %(message)s",
            datefmt="%H:%M:%S",
        )
        log.info("=== AutonomousPipeline: starting cycle (strategy=%s outcome=%s) ===",
                 strategy_id, outcome)

        self._bus.emit(ResearchFinished(
            report_path=report_path,
            session_id=session_id,
            strategy_id=strategy_id,
            outcome=outcome,
            findings_count=findings_count,
        ))

        events = self._bus.history
        log.info("=== Pipeline complete: %d events emitted ===", len(events))

        return {
            "events_emitted": [e.event_type for e in events],
            "total_events": len(events),
            "success": any(e.event_type == "DashboardUpdated" for e in events),
            "stages": {
                "knowledge": any(e.event_type == "KnowledgeUpdated" for e in events),
                "validation": any(e.event_type == "ValidationCompleted" for e in events),
                "alpha_planner": any(e.event_type == "AlphaPlannerUpdated" for e in events),
                "learning": any(e.event_type == "LearningUpdated" for e in events),
                "dashboard": any(e.event_type == "DashboardUpdated" for e in events),
            },
        }

    @property
    def bus(self) -> EventBus:
        return self._bus
