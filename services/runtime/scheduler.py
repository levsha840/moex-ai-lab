"""M12 Sprint 2 — RuntimeScheduler.

Decoupled from FSM: Scheduler makes decisions (what to run next, when leases expire),
FSM only records those decisions as state transitions.

Responsibilities:
- Select highest-priority pending task from queue
- Claim task with a time-bounded lease (claimed_at + lease_until)
- Complete / fail tasks after pipeline finishes
- Recover stale in_progress entries whose lease_until has passed
- Refresh queue from AlphaDiscoveryEngine
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class RuntimeScheduler:
    """Handles all queue-interaction decisions for the orchestrator."""

    def __init__(
        self,
        queue,                       # PersistentAlphaQueue
        lease_minutes: int = 30,
    ) -> None:
        self._queue = queue
        self._lease_minutes = lease_minutes

    # ── Task selection ────────────────────────────────────────────────────────

    def next_task(self) -> dict | None:
        """Return highest-priority pending entry. None if queue is empty."""
        return self._queue.next_pending()

    # ── Lease / claim ─────────────────────────────────────────────────────────

    def claim_task(self, entry_id: str) -> bool:
        """Mark entry as in_progress with a time-bounded lease.

        The lease_until timestamp enables crash recovery: if the process dies,
        recover_expired_leases() can return the entry to pending.
        """
        lease_until = _iso(_utcnow() + timedelta(minutes=self._lease_minutes))
        return self._queue.mark_in_progress(entry_id, lease_until=lease_until)

    def complete_task(self, entry_id: str) -> bool:
        """Mark entry as done after successful pipeline run."""
        return self._queue.mark_done(entry_id)

    def fail_task(self, entry_id: str, reason: str = "") -> bool:
        """Mark entry as failed (with retry up to max_attempts)."""
        return self._queue.mark_failed(entry_id, reason)

    # ── Recovery ──────────────────────────────────────────────────────────────

    def recover_expired_leases(self) -> int:
        """Return all stale in_progress entries to pending.

        Called on orchestrator startup so crashed cycles don't leave entries
        permanently stuck in in_progress.
        Returns the number of entries recovered.
        """
        return self._queue.recover_expired_leases()

    # ── Queue refresh ─────────────────────────────────────────────────────────

    def refresh_queue(self) -> dict:
        """Re-populate queue from AlphaDiscoveryEngine and save.

        Idempotent: update_from_discovery() deduplicates by (name, source).
        """
        from services.alpha_discovery.engine import AlphaDiscoveryEngine
        engine = AlphaDiscoveryEngine(PROJECT_ROOT)
        report = engine.run()
        result = self._queue.update_from_discovery(report.queue)
        self._queue.save()
        return {
            "added": result["added"],
            "updated": result["updated"],
            "total_entries": result["total_entries"],
            "pending_entries": result["pending_entries"],
        }

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def queue_stats(self) -> dict:
        return self._queue.stats()
