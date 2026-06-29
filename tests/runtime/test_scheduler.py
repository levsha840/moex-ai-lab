"""M12 Sprint 2 — RuntimeScheduler tests (12 tests)."""
import sys
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
from services.runtime.scheduler import RuntimeScheduler


def _make_queue(tmp: Path, n_tasks: int = 2) -> PersistentAlphaQueue:
    q = PersistentAlphaQueue(tmp / "queue.json")
    for i in range(n_tasks):
        q.push({
            "strategy_or_instrument": f"STRAT_{i}",
            "priority": "HIGH",
            "priority_score": 0.7 - i * 0.05,
            "estimated_cost": "LOW",
            "source": "TEST",
        })
    return q


class TestSchedulerImport:
    def test_importable(self):
        from services.runtime.scheduler import RuntimeScheduler
        assert RuntimeScheduler is not None


class TestNextTask:
    def test_returns_highest_priority(self):
        with tempfile.TemporaryDirectory() as td:
            q = _make_queue(Path(td), 2)
            sched = RuntimeScheduler(q)
            task = sched.next_task()
            assert task is not None
            assert task["strategy_or_instrument"] == "STRAT_0"  # higher score

    def test_returns_none_on_empty_queue(self):
        with tempfile.TemporaryDirectory() as td:
            q = PersistentAlphaQueue(Path(td) / "queue.json")
            sched = RuntimeScheduler(q)
            assert sched.next_task() is None

    def test_returns_none_when_all_done(self):
        with tempfile.TemporaryDirectory() as td:
            q = _make_queue(Path(td), 1)
            task = q.next_pending()
            q.mark_in_progress(task["entry_id"])
            q.mark_done(task["entry_id"])
            sched = RuntimeScheduler(q)
            assert sched.next_task() is None


class TestClaimTask:
    def test_claim_sets_in_progress(self):
        with tempfile.TemporaryDirectory() as td:
            q = _make_queue(Path(td), 1)
            sched = RuntimeScheduler(q, lease_minutes=30)
            task = sched.next_task()
            success = sched.claim_task(task["entry_id"])
            assert success is True
            # Queue entry should now be in_progress
            entry = next(e for e in q._entries if e["entry_id"] == task["entry_id"])
            assert entry["status"] == "in_progress"

    def test_claim_sets_lease_until(self):
        with tempfile.TemporaryDirectory() as td:
            q = _make_queue(Path(td), 1)
            sched = RuntimeScheduler(q, lease_minutes=30)
            task = sched.next_task()
            sched.claim_task(task["entry_id"])
            entry = next(e for e in q._entries if e["entry_id"] == task["entry_id"])
            assert entry.get("lease_until"), "lease_until must be set"

    def test_claim_returns_false_on_missing(self):
        with tempfile.TemporaryDirectory() as td:
            q = PersistentAlphaQueue(Path(td) / "q.json")
            sched = RuntimeScheduler(q)
            assert sched.claim_task("nonexistent") is False


class TestRecoverExpiredLeases:
    def test_recover_returns_stale_to_pending(self):
        with tempfile.TemporaryDirectory() as td:
            q = _make_queue(Path(td), 1)
            sched = RuntimeScheduler(q, lease_minutes=30)
            task = sched.next_task()
            entry_id = task["entry_id"]

            # Claim with already-expired lease
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            q.mark_in_progress(entry_id, lease_until=past)

            recovered = sched.recover_expired_leases()
            assert recovered == 1
            entry = next(e for e in q._entries if e["entry_id"] == entry_id)
            assert entry["status"] == "pending"

    def test_no_recovery_if_lease_still_valid(self):
        with tempfile.TemporaryDirectory() as td:
            q = _make_queue(Path(td), 1)
            sched = RuntimeScheduler(q, lease_minutes=30)
            task = sched.next_task()
            entry_id = task["entry_id"]

            # Claim with future lease
            future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            q.mark_in_progress(entry_id, lease_until=future)

            recovered = sched.recover_expired_leases()
            assert recovered == 0

    def test_empty_lease_not_recovered(self):
        """Entries with empty lease_until are skipped (no lease set)."""
        with tempfile.TemporaryDirectory() as td:
            q = _make_queue(Path(td), 1)
            task = q.next_pending()
            q.mark_in_progress(task["entry_id"])  # no lease_until
            sched = RuntimeScheduler(q)
            assert sched.recover_expired_leases() == 0


class TestCompleteAndFail:
    def test_complete_task(self):
        with tempfile.TemporaryDirectory() as td:
            q = _make_queue(Path(td), 1)
            sched = RuntimeScheduler(q)
            task = sched.next_task()
            sched.claim_task(task["entry_id"])
            result = sched.complete_task(task["entry_id"])
            assert result is True

    def test_fail_task(self):
        with tempfile.TemporaryDirectory() as td:
            q = _make_queue(Path(td), 1)
            sched = RuntimeScheduler(q)
            task = sched.next_task()
            sched.claim_task(task["entry_id"])
            result = sched.fail_task(task["entry_id"], "test error")
            assert result is True
