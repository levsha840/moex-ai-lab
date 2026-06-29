"""
M12 Sprint 1 — Integration Tests: Event Pipeline

Verifies the full autonomous chain:
ResearchFinished → KnowledgeUpdated → ValidationCompleted
→ AlphaPlannerUpdated → LearningUpdated → DashboardUpdated
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ── Event Definitions ─────────────────────────────────────────────────────────

class TestEventDefinitions:
    def test_all_events_importable(self):
        from services.event_pipeline import (
            LabEvent,
            ResearchFinished,
            KnowledgeUpdated,
            ValidationCompleted,
            AlphaPlannerUpdated,
            LearningUpdated,
            DashboardUpdated,
        )
        assert LabEvent is not None

    def test_research_finished_has_required_fields(self):
        from services.event_pipeline.events import ResearchFinished
        e = ResearchFinished(
            strategy_id="BB_SQUEEZE",
            outcome="FAIL",
            findings_count=1,
        )
        assert e.event_type == "ResearchFinished"
        assert e.strategy_id == "BB_SQUEEZE"
        assert e.outcome == "FAIL"
        assert e.timestamp  # auto-generated

    def test_all_events_have_timestamps(self):
        from services.event_pipeline import events as ev
        for cls_name in [
            "ResearchFinished", "KnowledgeUpdated", "ValidationCompleted",
            "AlphaPlannerUpdated", "LearningUpdated", "DashboardUpdated",
        ]:
            cls = getattr(ev, cls_name)
            instance = cls()
            assert instance.timestamp, f"{cls_name} missing timestamp"
            assert instance.event_type == cls_name, f"{cls_name} wrong event_type"


# ── Event Bus ─────────────────────────────────────────────────────────────────

class TestEventBus:
    def test_bus_subscribe_and_emit(self):
        from services.event_pipeline.bus import EventBus
        from services.event_pipeline.events import ResearchFinished

        received = []

        def handler(event, bus):
            received.append(event)

        bus = EventBus()
        bus.subscribe("ResearchFinished", handler)
        bus.emit(ResearchFinished(strategy_id="TEST"))

        assert len(received) == 1
        assert received[0].strategy_id == "TEST"

    def test_bus_handler_error_does_not_stop_chain(self):
        from services.event_pipeline.bus import EventBus
        from services.event_pipeline.events import ResearchFinished

        calls = []

        def bad_handler(event, bus):
            raise ValueError("intentional error")

        def good_handler(event, bus):
            calls.append("ok")

        bus = EventBus()
        bus.subscribe("ResearchFinished", bad_handler)
        bus.subscribe("ResearchFinished", good_handler)
        bus.emit(ResearchFinished())  # should not raise

        assert calls == ["ok"]

    def test_bus_history_tracks_events(self):
        from services.event_pipeline.bus import EventBus
        from services.event_pipeline.events import ResearchFinished, KnowledgeUpdated

        bus = EventBus()
        bus.emit(ResearchFinished())
        bus.emit(KnowledgeUpdated(facts_added=3))

        assert len(bus.history) == 2
        assert bus.history[0].event_type == "ResearchFinished"
        assert bus.history[1].event_type == "KnowledgeUpdated"

    def test_bus_handler_can_emit_next_event(self):
        from services.event_pipeline.bus import EventBus
        from services.event_pipeline.events import ResearchFinished, KnowledgeUpdated

        emitted = []

        def handler(event, bus):
            emitted.append(event.event_type)
            bus.emit(KnowledgeUpdated(facts_added=1))

        def next_handler(event, bus):
            emitted.append(event.event_type)

        bus = EventBus()
        bus.subscribe("ResearchFinished", handler)
        bus.subscribe("KnowledgeUpdated", next_handler)
        bus.emit(ResearchFinished())

        assert emitted == ["ResearchFinished", "KnowledgeUpdated"]


# ── Pipeline ──────────────────────────────────────────────────────────────────

class TestAutonomousPipeline:
    def test_pipeline_importable(self):
        from services.event_pipeline.pipeline import AutonomousPipeline
        pipeline = AutonomousPipeline()
        assert pipeline is not None

    def test_pipeline_run_emits_all_stages(self):
        from services.event_pipeline.pipeline import AutonomousPipeline
        pipeline = AutonomousPipeline(verbose=False)
        result = pipeline.run(strategy_id="BB_SQUEEZE", outcome="FAIL")

        assert result["total_events"] >= 6, (
            f"Expected >=6 events in chain, got {result['total_events']}: "
            f"{result['events_emitted']}"
        )
        assert result["stages"]["knowledge"], "KnowledgeUpdated not emitted"
        assert result["stages"]["validation"], "ValidationCompleted not emitted"
        assert result["stages"]["alpha_planner"], "AlphaPlannerUpdated not emitted"
        assert result["stages"]["learning"], "LearningUpdated not emitted"
        assert result["stages"]["dashboard"], "DashboardUpdated not emitted"

    def test_pipeline_success_flag(self):
        from services.event_pipeline.pipeline import AutonomousPipeline
        pipeline = AutonomousPipeline()
        result = pipeline.run(strategy_id="TEST", outcome="FAIL")
        assert result["success"] is True

    def test_pipeline_updates_runtime_status(self):
        import json
        from services.event_pipeline.pipeline import AutonomousPipeline
        pipeline = AutonomousPipeline()
        pipeline.run(strategy_id="PIPELINE_TEST", outcome="FAIL")

        status_path = PROJECT_ROOT / "runtime" / "status.json"
        assert status_path.exists(), "runtime/status.json not written by pipeline"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert status.get("pipeline_completed") is True
        assert status.get("pipeline_last_completed")

    def test_pipeline_cli_script_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_event_pipeline",
            PROJECT_ROOT / "scripts" / "run_event_pipeline.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "main")


# ── Handlers ─────────────────────────────────────────────────────────────────

class TestHandlers:
    def test_handlers_importable(self):
        from services.event_pipeline.handlers import (
            on_research_finished,
            on_knowledge_updated,
            on_validation_completed,
            on_alpha_planner_updated,
            on_learning_updated,
            on_dashboard_updated,
        )
        assert callable(on_research_finished)

    def test_on_dashboard_updated_writes_status(self):
        import json
        from services.event_pipeline.bus import EventBus
        from services.event_pipeline.events import DashboardUpdated
        from services.event_pipeline.handlers import on_dashboard_updated

        bus = EventBus()
        on_dashboard_updated(DashboardUpdated(), bus)

        status_path = PROJECT_ROOT / "runtime" / "status.json"
        assert status_path.exists()
        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert "pipeline_last_completed" in status
