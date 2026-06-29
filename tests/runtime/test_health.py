"""M12 Sprint 2 — LabHealthCheck tests (12 tests)."""
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
from services.runtime.health import LabHealthCheck, HealthStatus, HealthReport


class TestHealthImport:
    def test_importable(self):
        from services.runtime.health import LabHealthCheck, HealthStatus, HealthReport
        assert LabHealthCheck is not None

    def test_health_status_values(self):
        assert HealthStatus.OK == "OK"
        assert HealthStatus.WARNING == "WARNING"
        assert HealthStatus.CRITICAL == "CRITICAL"


class TestQueueHealth:
    def _checker(self, tmp: Path) -> LabHealthCheck:
        return LabHealthCheck(tmp)

    def test_ok_when_pending(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            q = PersistentAlphaQueue(tmp / "q.json")
            q.push({"strategy_or_instrument": "X", "priority": "HIGH",
                    "priority_score": 0.9, "estimated_cost": "LOW", "source": "T"})
            report = self._checker(tmp).check_queue(q)
            assert report.status == HealthStatus.OK

    def test_warning_when_no_pending(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            q = PersistentAlphaQueue(tmp / "q.json")
            q.push({"strategy_or_instrument": "X", "priority": "HIGH",
                    "priority_score": 0.9, "estimated_cost": "LOW", "source": "T"})
            task = q.next_pending()
            q.mark_in_progress(task["entry_id"])
            q.mark_done(task["entry_id"])
            report = self._checker(tmp).check_queue(q)
            assert report.status == HealthStatus.WARNING

    def test_warning_empty_queue(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            q = PersistentAlphaQueue(tmp / "q.json")
            report = self._checker(tmp).check_queue(q)
            assert report.status == HealthStatus.WARNING


class TestKnowledgeStoreHealth:
    def test_critical_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            checker = LabHealthCheck(Path(td))
            report = checker.check_knowledge_store()
            assert report.status == HealthStatus.CRITICAL

    def test_ok_with_facts(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            store_path = tmp / "data" / "knowledge" / "evolution" / "store.json"
            store_path.parent.mkdir(parents=True)
            store_path.write_text(json.dumps({
                "version": 3,
                "facts": {"SBER_TREND": {"value": 0.6}},
            }))
            report = LabHealthCheck(tmp).check_knowledge_store()
            assert report.status == HealthStatus.OK

    def test_warning_with_zero_facts(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            store_path = tmp / "data" / "knowledge" / "evolution" / "store.json"
            store_path.parent.mkdir(parents=True)
            store_path.write_text(json.dumps({"version": 1, "facts": {}}))
            report = LabHealthCheck(tmp).check_knowledge_store()
            assert report.status == HealthStatus.WARNING


class TestOrchestratorStateHealth:
    def test_ok_when_missing_fresh_start(self):
        with tempfile.TemporaryDirectory() as td:
            checker = LabHealthCheck(Path(td))
            report = checker.check_orchestrator_state(Path(td) / "nonexistent.json")
            assert report.status == HealthStatus.OK
            assert "fresh" in report.message.lower()

    def test_ok_when_file_exists(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            state_path = tmp / "orchestrator_state.json"
            state_path.write_text(json.dumps({"state": "IDLE", "cycle_count": 3}))
            report = LabHealthCheck(tmp).check_orchestrator_state(state_path)
            assert report.status == HealthStatus.OK


class TestCheckAll:
    def test_check_all_returns_dict_of_reports(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            q = PersistentAlphaQueue(tmp / "q.json")
            checker = LabHealthCheck(tmp)
            reports = checker.check_all(q, tmp / "state.json")
            assert isinstance(reports, dict)
            assert "queue" in reports
            assert "knowledge_store" in reports
            assert "orchestrator_state" in reports

    def test_is_healthy_no_critical(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            q = PersistentAlphaQueue(tmp / "q.json")
            # Create reports dir to avoid CRITICAL on reports_dir
            (tmp / "reports" / "sess").mkdir(parents=True)
            (tmp / "reports" / "sess" / "report.json").write_text("{}")
            # knowledge store — still CRITICAL
            reports = LabHealthCheck(tmp).check_all(q, tmp / "state.json")
            healthy = LabHealthCheck.is_healthy(reports)
            # knowledge_store is CRITICAL → not healthy
            assert healthy is False

    def test_is_healthy_all_ok(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # Seed all required artifacts
            store = tmp / "data" / "knowledge" / "evolution" / "store.json"
            store.parent.mkdir(parents=True)
            store.write_text(json.dumps({"version": 1, "facts": {"X": {}}}))
            (tmp / "reports" / "sess").mkdir(parents=True)
            (tmp / "reports" / "sess" / "report.json").write_text("{}")
            q = PersistentAlphaQueue(tmp / "q.json")
            q.push({"strategy_or_instrument": "A", "priority": "HIGH",
                    "priority_score": 0.8, "estimated_cost": "LOW", "source": "T"})
            checker = LabHealthCheck(tmp)
            reports = checker.check_all(q, tmp / "state.json")
            assert checker.is_healthy(reports) is True
