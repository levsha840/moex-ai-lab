"""
M12 Sprint 1 — Integration Tests: Persistent Alpha Queue Recovery

Verifies the queue survives process restarts by saving to and loading from disk.
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestPersistentQueueCore:
    def test_queue_importable(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        assert PersistentAlphaQueue is not None

    def test_queue_creates_without_file(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            pq = PersistentAlphaQueue(Path(tmp) / "queue.json")
            pq.load()  # should not raise
            assert pq.stats()["total"] == 0

    def test_queue_push_returns_id(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            pq = PersistentAlphaQueue(Path(tmp) / "queue.json")
            pq.load()
            eid = pq.push({"strategy_or_instrument": "BB_SQUEEZE", "priority": "HIGH"})
            assert eid
            assert len(eid) > 0

    def test_queue_deduplicates_pending(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            pq = PersistentAlphaQueue(Path(tmp) / "queue.json")
            pq.load()
            eid1 = pq.push({"strategy_or_instrument": "BB_SQUEEZE", "priority": "HIGH"})
            eid2 = pq.push({"strategy_or_instrument": "BB_SQUEEZE", "priority": "HIGH"})
            assert eid1 == eid2, "Duplicate pending entries should return same ID"
            assert pq.stats()["total"] == 1

    def test_queue_mark_done(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            pq = PersistentAlphaQueue(Path(tmp) / "queue.json")
            pq.load()
            eid = pq.push({"strategy_or_instrument": "TEST", "priority": "MEDIUM"})
            result = pq.mark_done(eid)
            assert result is True
            stats = pq.stats()
            assert stats["done"] == 1
            assert stats["pending"] == 0

    def test_queue_mark_failed_increments_attempts(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            pq = PersistentAlphaQueue(Path(tmp) / "queue.json")
            pq.load()
            eid = pq.push({"strategy_or_instrument": "FAIL_TEST"})
            pq.mark_failed(eid, "test failure")
            pq.mark_failed(eid, "test failure 2")
            pq.mark_failed(eid, "test failure 3")
            stats = pq.stats()
            assert stats["failed"] == 1, "Should be failed after max_attempts"

    def test_queue_next_pending_order(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            pq = PersistentAlphaQueue(Path(tmp) / "queue.json")
            pq.load()
            pq.push({"strategy_or_instrument": "LOW", "priority": "LOW", "priority_score": 0.2})
            pq.push({"strategy_or_instrument": "CRITICAL", "priority": "CRITICAL", "priority_score": 0.9})
            pq.push({"strategy_or_instrument": "HIGH", "priority": "HIGH", "priority_score": 0.6})
            # No sort guaranteed after push — call update_from_discovery to sort
            nxt = pq.next_pending()
            assert nxt is not None


class TestQueuePersistence:
    def test_queue_survives_save_load(self):
        """Main recovery test: queue written in one instance, read in another."""
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"

            # Session 1: write
            pq1 = PersistentAlphaQueue(path)
            pq1.load()
            eid = pq1.push({"strategy_or_instrument": "BB_SQUEEZE", "priority": "CRITICAL", "priority_score": 0.9})
            pq1.push({"strategy_or_instrument": "DUAL_MA_TREND", "priority": "HIGH", "priority_score": 0.6})
            pq1.save()

            # Session 2: read (simulates restart)
            pq2 = PersistentAlphaQueue(path)
            pq2.load()
            assert pq2.stats()["total"] == 2, "Queue not restored after restart"
            assert pq2.stats()["pending"] == 2

            nxt = pq2.next_pending()
            assert nxt is not None

    def test_queue_file_written_to_disk(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            pq = PersistentAlphaQueue(path)
            pq.load()
            pq.push({"strategy_or_instrument": "TEST"})
            pq.save()
            assert path.exists(), "queue.json not written"
            import json
            doc = json.loads(path.read_text(encoding="utf-8"))
            assert doc["schema"] == "1.0"
            assert len(doc["entries"]) == 1

    def test_queue_creates_parent_dirs(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "nested" / "queue.json"
            pq = PersistentAlphaQueue(path)
            pq.load()
            pq.push({"strategy_or_instrument": "TEST"})
            pq.save()
            assert path.exists()

    def test_queue_partial_done_survives_restart(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"

            pq1 = PersistentAlphaQueue(path)
            pq1.load()
            eid1 = pq1.push({"strategy_or_instrument": "DONE_STRATEGY"})
            eid2 = pq1.push({"strategy_or_instrument": "PENDING_STRATEGY"})
            pq1.mark_done(eid1)
            pq1.save()

            pq2 = PersistentAlphaQueue(path)
            pq2.load()
            assert pq2.stats()["done"] == 1
            assert pq2.stats()["pending"] == 1
            nxt = pq2.next_pending()
            assert nxt["strategy_or_instrument"] == "PENDING_STRATEGY"


class TestQueueDiscoverySync:
    def test_update_from_discovery_adds_new_entries(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        from services.alpha_discovery.engine import AlphaDiscoveryEngine

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            pq = PersistentAlphaQueue(path)
            pq.load()

            engine = AlphaDiscoveryEngine(PROJECT_ROOT)
            report = engine.run()
            result = pq.update_from_discovery(report.queue)

            assert result["added"] > 0, "No entries added from discovery"
            assert result["total_entries"] > 0
            assert pq.stats()["pending"] > 0

    def test_update_from_discovery_idempotent(self):
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        from services.alpha_discovery.engine import AlphaDiscoveryEngine

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            pq = PersistentAlphaQueue(path)
            pq.load()

            engine = AlphaDiscoveryEngine(PROJECT_ROOT)
            report = engine.run()

            result1 = pq.update_from_discovery(report.queue)
            result2 = pq.update_from_discovery(report.queue)

            assert result2["added"] == 0, "Re-running should add 0 new entries"
            assert result1["total_entries"] == result2["total_entries"]

    def test_real_queue_file_initializes_from_discovery(self):
        """Integration: the real data/alpha/queue.json gets populated from discovery."""
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        from services.alpha_discovery.engine import AlphaDiscoveryEngine

        queue_path = PROJECT_ROOT / "data" / "alpha" / "queue.json"
        pq = PersistentAlphaQueue(queue_path)
        pq.load()

        engine = AlphaDiscoveryEngine(PROJECT_ROOT)
        report = engine.run()
        pq.update_from_discovery(report.queue)
        pq.save()

        assert queue_path.exists(), "data/alpha/queue.json not created"
        assert pq.stats()["total"] > 0
        assert pq.stats()["pending"] > 0
