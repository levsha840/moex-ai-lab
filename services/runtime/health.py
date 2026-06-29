"""M12 Sprint 2 — LabHealthCheck.

Pre-flight health checks run in IDLE state before each cycle.
All checks are read-only and fast. A CRITICAL result blocks the cycle.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class HealthStatus(str, Enum):
    OK       = "OK"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class HealthReport:
    name: str
    status: HealthStatus
    message: str
    data: dict

    def is_ok(self) -> bool:
        return self.status == HealthStatus.OK

    def is_critical(self) -> bool:
        return self.status == HealthStatus.CRITICAL


class LabHealthCheck:
    """Aggregates health checks for all critical lab components."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root

    # ── Individual checks ─────────────────────────────────────────────────────

    def check_queue(self, queue) -> HealthReport:
        """Verify queue is loaded and has pending work."""
        stats = queue.stats()
        pending = stats.get("pending", 0)
        total = stats.get("total", 0)
        if pending > 0:
            return HealthReport(
                name="queue",
                status=HealthStatus.OK,
                message=f"{pending} pending tasks",
                data=stats,
            )
        if total > 0:
            return HealthReport(
                name="queue",
                status=HealthStatus.WARNING,
                message=f"No pending tasks ({total} entries, all done/failed)",
                data=stats,
            )
        return HealthReport(
            name="queue",
            status=HealthStatus.WARNING,
            message="Queue is empty — run refresh to populate",
            data=stats,
        )

    def check_knowledge_store(self) -> HealthReport:
        """Verify knowledge store exists and has facts."""
        store_path = self._root / "data" / "knowledge" / "evolution" / "store.json"
        if not store_path.exists():
            return HealthReport(
                name="knowledge_store",
                status=HealthStatus.CRITICAL,
                message="store.json not found",
                data={"path": str(store_path)},
            )
        try:
            doc = json.loads(store_path.read_text(encoding="utf-8"))
            facts = len(doc.get("facts", {}))
            version = doc.get("version", 0)
            if facts == 0:
                return HealthReport(
                    name="knowledge_store",
                    status=HealthStatus.WARNING,
                    message="Knowledge store has 0 facts",
                    data={"version": version, "facts": facts},
                )
            return HealthReport(
                name="knowledge_store",
                status=HealthStatus.OK,
                message=f"v{version}, {facts} facts",
                data={"version": version, "facts": facts},
            )
        except (json.JSONDecodeError, OSError) as exc:
            return HealthReport(
                name="knowledge_store",
                status=HealthStatus.CRITICAL,
                message=f"Cannot read store.json: {exc}",
                data={},
            )

    def check_orchestrator_state(self, state_path: Path) -> HealthReport:
        """Check that orchestrator state is readable (OK if file missing = fresh start)."""
        if not state_path.exists():
            return HealthReport(
                name="orchestrator_state",
                status=HealthStatus.OK,
                message="No state file — fresh start",
                data={},
            )
        try:
            doc = json.loads(state_path.read_text(encoding="utf-8"))
            return HealthReport(
                name="orchestrator_state",
                status=HealthStatus.OK,
                message=f"State: {doc.get('state', '?')}, cycles: {doc.get('cycle_count', 0)}",
                data={"state": doc.get("state"), "cycle_count": doc.get("cycle_count", 0)},
            )
        except (json.JSONDecodeError, OSError) as exc:
            return HealthReport(
                name="orchestrator_state",
                status=HealthStatus.WARNING,
                message=f"State file unreadable: {exc}",
                data={},
            )

    def check_reports_dir(self) -> HealthReport:
        """Verify reports directory exists and has research data."""
        reports_dir = self._root / "reports"
        if not reports_dir.exists():
            return HealthReport(
                name="reports_dir",
                status=HealthStatus.CRITICAL,
                message="reports/ directory not found",
                data={},
            )
        count = sum(1 for _ in reports_dir.glob("*/report.json")
                    if "visual_backtest" not in str(_))
        if count == 0:
            return HealthReport(
                name="reports_dir",
                status=HealthStatus.WARNING,
                message="reports/ is empty",
                data={"count": count},
            )
        return HealthReport(
            name="reports_dir",
            status=HealthStatus.OK,
            message=f"{count} session reports",
            data={"count": count},
        )

    # ── Aggregated check ──────────────────────────────────────────────────────

    def check_all(self, queue, state_path: Path) -> dict[str, HealthReport]:
        return {
            "queue":               self.check_queue(queue),
            "knowledge_store":     self.check_knowledge_store(),
            "orchestrator_state":  self.check_orchestrator_state(state_path),
            "reports_dir":         self.check_reports_dir(),
        }

    @staticmethod
    def is_healthy(reports: dict[str, HealthReport]) -> bool:
        """True if no CRITICAL checks. WARNINGs are allowed."""
        return not any(r.is_critical() for r in reports.values())
