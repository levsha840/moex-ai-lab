"""M12 Lab event definitions.

Each event carries the minimum payload needed by its subscribers.
All fields are plain Python types — no service imports here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LabEvent:
    """Base class for all lab events."""
    event_type: str
    timestamp: str = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"<{self.event_type} @ {self.timestamp[:19]}>"


@dataclass
class ResearchFinished(LabEvent):
    """Emitted when a research session writes its report to disk."""
    event_type: str = "ResearchFinished"
    report_path: str = ""
    session_id: str = ""
    strategy_id: str = ""
    outcome: str = "FAIL"
    findings_count: int = 0


@dataclass
class KnowledgeUpdated(LabEvent):
    """Emitted after knowledge store is updated from research output."""
    event_type: str = "KnowledgeUpdated"
    facts_added: int = 0
    store_version: int = 0
    ingestion_count: int = 0


@dataclass
class ValidationCompleted(LabEvent):
    """Emitted after validation passports are rebuilt."""
    event_type: str = "ValidationCompleted"
    passports_count: int = 0


@dataclass
class AlphaPlannerUpdated(LabEvent):
    """Emitted after alpha queue and planner are refreshed."""
    event_type: str = "AlphaPlannerUpdated"
    queue_size: int = 0
    persistent_entries: int = 0
    critical_entries: int = 0


@dataclass
class LearningUpdated(LabEvent):
    """Emitted after frontend export JSONs are regenerated."""
    event_type: str = "LearningUpdated"
    exports_refreshed: list[str] = field(default_factory=list)


@dataclass
class DashboardUpdated(LabEvent):
    """Emitted after reports cache is invalidated — dashboard will serve fresh data."""
    event_type: str = "DashboardUpdated"
    cache_invalidated: bool = True
