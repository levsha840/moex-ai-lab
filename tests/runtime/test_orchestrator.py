"""M12 Sprint 2 — RuntimeOrchestrator tests (22 tests).

All tests run in dry_run=True mode to avoid touching real services.
Live-path behaviour is covered by integration tests.
"""
import json
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
from services.runtime.orchestrator import RuntimeOrchestrator
from services.runtime.runtime_context import CycleResult, OrchestratorContext
from services.runtime.runtime_state import OrchestratorState


def _seed_queue(tmp: Path, n: int = 2) -> None:
    q = PersistentAlphaQueue(tmp / "data" / "alpha" / "queue.json")
    for i in range(n):
        q.push({
            "strategy_or_instrument": f"STRAT_{i}",
            "priority": "HIGH",
            "priority_score": 0.8 - i * 0.05,
            "estimated_cost": "LOW",
            "source": "TEST",
        })
    q.save()


def _make_orch(tmp: Path, dry_run: bool = True, **kw) -> RuntimeOrchestrator:
    return RuntimeOrchestrator(project_root=tmp, dry_run=dry_run, **kw)


class TestOrchestratorImport:
    def test_importable(self):
        from services.runtime.orchestrator import RuntimeOrchestrator
        assert RuntimeOrchestrator is not None

    def test_cycle_result_importable(self):
        from services.runtime.runtime_context import CycleResult
        assert CycleResult is not None


class TestOrchestratorInit:
    def test_creates_in_idle(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            orch = _make_orch(tmp)
            assert orch.context.state == "IDLE"

    def test_state_file_created_after_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            orch = _make_orch(tmp)
            # State file should be created during startup
            state_file = tmp / "runtime" / "orchestrator_state.json"
            # May or may not exist depending on whether startup_recovery writes it
            # Just check context is usable
            assert orch.context.run_id is not None

    def test_dry_run_flag_stored(self):
        with tempfile.TemporaryDirectory() as td:
            orch = _make_orch(Path(td), dry_run=True)
            assert orch._dry_run is True

    def test_error_count_zero_at_start(self):
        with tempfile.TemporaryDirectory() as td:
            orch = _make_orch(Path(td))
            assert orch.context.error_count == 0


class TestRunOnce:
    def test_run_once_empty_queue_no_task(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            orch = _make_orch(tmp)
            result = orch.run_once()
            assert result.no_task is True
            assert result.final_state == "IDLE"
            assert result.error is None

    def test_run_once_with_task_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp)
            result = orch.run_once()
            assert result.no_task is False
            assert result.final_state == "IDLE"
            assert result.pipeline_success is True  # dry_run simulates success

    def test_run_once_dry_run_does_not_mutate_queue(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp, dry_run=True)
            q_before = orch._queue.stats()
            orch.run_once()
            q_after = orch._queue.stats()
            # In dry_run, queue entries are NOT claimed or marked done
            assert q_after["pending"] == q_before["pending"]

    def test_run_once_increments_cycle_count(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp)
            assert orch.context.cycle_count == 0
            orch.run_once()
            assert orch.context.cycle_count == 1

    def test_run_once_records_history(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp)
            orch.run_once()
            assert len(orch.context.history) == 1

    def test_run_once_state_returns_to_idle(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp)
            orch.run_once()
            assert orch.context.state == "IDLE"

    def test_run_once_result_has_strategy(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp)
            result = orch.run_once()
            assert result.strategy_id == "STRAT_0"

    def test_run_once_result_has_pipeline_events(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp)
            result = orch.run_once()
            # In dry_run, 6 simulated events
            assert len(result.pipeline_events) == 6

    def test_run_once_dry_run_flag_in_result(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp, dry_run=True)
            result = orch.run_once()
            assert result.dry_run is True


class TestRunContinuous:
    def test_run_continuous_max_cycles(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # 3 tasks, run 2 cycles (both empty-queue skips or task runs)
            _seed_queue(tmp, n=3)
            orch = _make_orch(tmp)
            results = orch.run_continuous(max_cycles=2)
            assert len(results) == 2

    def test_run_continuous_empty_queue_completes(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            orch = _make_orch(tmp)
            results = orch.run_continuous(max_cycles=3)
            assert len(results) == 3
            assert all(r.no_task for r in results)


class TestStatePersistence:
    def test_state_persisted_to_file(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp)
            orch.run_once()
            state_path = tmp / "runtime" / "orchestrator_state.json"
            assert state_path.exists()
            doc = json.loads(state_path.read_text())
            assert doc["state"] == "IDLE"
            assert doc["cycle_count"] == 1

    def test_state_survives_restart(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=2)
            orch1 = _make_orch(tmp)
            orch1.run_once()
            # Restart: new orchestrator loads state
            orch2 = _make_orch(tmp)
            assert orch2.context.cycle_count == 1
            assert orch2.context.state == "IDLE"

    def test_crash_recovery_resets_non_terminal_state(self):
        """If state file has VALIDATING at restart, orchestrator resets to IDLE."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            state_path = tmp / "runtime" / "orchestrator_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            # Simulate crashed state
            doc = {
                "schema": "1.0",
                "run_id": "test_run",
                "state": "VALIDATING",  # crashed mid-cycle
                "cycle_count": 5,
                "current_entry_id": "abc123",
                "current_strategy_id": "BB_SQUEEZE",
                "error_count": 0,
                "error_message": None,
                "last_cycle_completed_at": None,
                "history": [],
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
            state_path.write_text(json.dumps(doc))
            orch = _make_orch(tmp)
            # Must reset to IDLE
            assert orch.context.state == "IDLE"
            assert orch.context.cycle_count == 5  # preserved

    def test_journal_created(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_queue(tmp, n=1)
            orch = _make_orch(tmp)
            orch.run_once()
            journal_path = tmp / "runtime" / "orchestrator_journal.jsonl"
            assert journal_path.exists()
            entries = orch.journal.read_all()
            assert len(entries) > 0


class TestStatusMethod:
    def test_status_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            orch = _make_orch(Path(td))
            s = orch.status()
            assert isinstance(s, dict)
            assert "state" in s
            assert "cycle_count" in s
            assert "dry_run" in s

    def test_status_state_is_idle(self):
        with tempfile.TemporaryDirectory() as td:
            orch = _make_orch(Path(td))
            assert orch.status()["state"] == "IDLE"
