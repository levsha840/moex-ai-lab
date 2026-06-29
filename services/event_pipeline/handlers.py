"""M12 Event handlers — each handler processes one event and emits the next.

Handler signature: handler(event: LabEvent, bus: EventBus) -> None

Handlers CALL existing services — they never modify them.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from .events import (
    AlphaPlannerUpdated,
    DashboardUpdated,
    KnowledgeUpdated,
    LearningUpdated,
    ResearchFinished,
    ValidationCompleted,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

log = logging.getLogger(__name__)


# ── Handler 1: ResearchFinished → KnowledgeUpdated ───────────────────────────

def on_research_finished(event: ResearchFinished, bus) -> None:
    """Persist learning cycle to knowledge store after research completes."""
    log.info("[H1] ResearchFinished: strategy=%s outcome=%s", event.strategy_id, event.outcome)

    facts_added = 0
    store_version = 0
    ingestion_count = 0

    try:
        from scripts.persist_learning_cycle import run_cycle_and_persist
        result = run_cycle_and_persist(
            strategy_id=event.strategy_id or "UNKNOWN",
            outcome=event.outcome or "FAIL",
        )
        facts_added = result.get("facts_added", 0)
        store_version = result.get("store_version", 0)
        ingestion_count = result.get("ingestion_count", 0)
        log.info("[H1] Knowledge persisted: +%d facts, store v%d", facts_added, store_version)
    except Exception as exc:
        log.warning("[H1] persist_learning_cycle failed (%s), continuing", exc)
        try:
            store_path = PROJECT_ROOT / "data" / "knowledge" / "evolution" / "store.json"
            if store_path.exists():
                d = json.loads(store_path.read_text(encoding="utf-8"))
                store_version = d.get("version", 0)
                ingestion_count = d.get("ingestion_count", 0)
                facts_added = len(d.get("facts", {}))
        except Exception:
            pass

    bus.emit(KnowledgeUpdated(
        facts_added=facts_added,
        store_version=store_version,
        ingestion_count=ingestion_count,
    ))


# ── Handler 2: KnowledgeUpdated → ValidationCompleted ────────────────────────

def on_knowledge_updated(event: KnowledgeUpdated, bus) -> None:
    """Run validation passports after knowledge store is updated."""
    log.info("[H2] KnowledgeUpdated: v%d +%d facts", event.store_version, event.facts_added)

    passports_count = 0
    try:
        from services.validation.passport import PassportRegistry
        registry = PassportRegistry()
        passports = registry.build_all()
        passports_count = len(passports)
        log.info("[H2] Validation: %d passports built", passports_count)
    except Exception as exc:
        log.warning("[H2] Validation skipped (%s)", exc)

    bus.emit(ValidationCompleted(passports_count=passports_count))


# ── Handler 3: ValidationCompleted → AlphaPlannerUpdated ─────────────────────

def on_validation_completed(event: ValidationCompleted, bus) -> None:
    """Refresh alpha discovery queue and sync to planner."""
    log.info("[H3] ValidationCompleted: %d passports", event.passports_count)

    queue_size = 0
    persistent_entries = 0
    critical_entries = 0

    try:
        from services.alpha_discovery.engine import AlphaDiscoveryEngine
        from services.alpha_discovery.persistent_queue import PersistentAlphaQueue
        from services.continuous_learning.planner_bridge import PlannerBridge

        engine = AlphaDiscoveryEngine(PROJECT_ROOT)
        report = engine.run()
        queue_size = len(report.queue)

        pq = PersistentAlphaQueue(PROJECT_ROOT / "data" / "alpha" / "queue.json")
        pq.load()
        sync_result = pq.update_from_discovery(report.queue)
        persistent_entries = sync_result["total_entries"]
        pq.save()

        bridge = PlannerBridge()
        bridge.sync_queue_to_planner(report.queue)
        critical_entries = sum(
            1 for e in pq.all_pending() if e.get("priority") == "CRITICAL"
        )

        log.info(
            "[H3] Alpha queue: %d entries (%d persistent, %d critical)",
            queue_size, persistent_entries, critical_entries,
        )
    except Exception as exc:
        log.warning("[H3] Alpha planner update failed (%s)", exc)

    bus.emit(AlphaPlannerUpdated(
        queue_size=queue_size,
        persistent_entries=persistent_entries,
        critical_entries=critical_entries,
    ))


# ── Handler 4: AlphaPlannerUpdated → LearningUpdated ─────────────────────────

def on_alpha_planner_updated(event: AlphaPlannerUpdated, bus) -> None:
    """Regenerate frontend export JSONs after alpha queue is refreshed."""
    log.info("[H4] AlphaPlannerUpdated: %d queue entries", event.queue_size)

    exports_refreshed = []
    export_scripts = [
        "scripts/export_alpha_discovery.py",
        "scripts/export_learning_state.py",
    ]

    for script_path in export_scripts:
        full_path = PROJECT_ROOT / script_path
        if not full_path.exists():
            log.warning("[H4] Export script not found: %s", script_path)
            continue
        try:
            result = subprocess.run(
                [sys.executable, str(full_path)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                exports_refreshed.append(script_path)
                log.info("[H4] Exported: %s", script_path)
            else:
                log.warning("[H4] Export failed %s: %s", script_path, result.stderr[:200])
        except subprocess.TimeoutExpired:
            log.warning("[H4] Export timed out: %s", script_path)
        except Exception as exc:
            log.warning("[H4] Export error %s: %s", script_path, exc)

    bus.emit(LearningUpdated(exports_refreshed=exports_refreshed))


# ── Handler 5: LearningUpdated → DashboardUpdated ────────────────────────────

def on_learning_updated(event: LearningUpdated, bus) -> None:
    """Invalidate reports cache so dashboard serves fresh data."""
    log.info("[H5] LearningUpdated: %d exports refreshed", len(event.exports_refreshed))

    try:
        from services.cache.reports_cache import ReportsCache
        ReportsCache.get_instance(PROJECT_ROOT / "reports").invalidate()
        log.info("[H5] ReportsCache invalidated")
    except Exception as exc:
        log.warning("[H5] Cache invalidation failed (%s)", exc)

    bus.emit(DashboardUpdated(cache_invalidated=True))


# ── Handler 6: DashboardUpdated (terminal) ───────────────────────────────────

def on_dashboard_updated(event: DashboardUpdated, bus) -> None:
    """Write pipeline completion marker to runtime/status.json."""
    from datetime import datetime, timezone
    log.info("[H6] DashboardUpdated — pipeline cycle complete")

    status_path = PROJECT_ROOT / "runtime" / "status.json"
    try:
        status = {}
        if status_path.exists():
            status = json.loads(status_path.read_text(encoding="utf-8"))
        status["pipeline_last_completed"] = datetime.now(timezone.utc).isoformat()
        status["pipeline_completed"] = True
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("[H6] runtime/status.json updated")
    except Exception as exc:
        log.warning("[H6] Failed to update runtime/status.json: %s", exc)
