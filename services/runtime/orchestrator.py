"""M12 Sprint 2 — RuntimeOrchestrator.

The canonical autonomous loop:

  RuntimeOrchestrator
    → Scheduler selects next task from PersistentAlphaQueue
    → Scheduler claims task (lease/in_progress)
    → AutonomousPipeline.run(strategy_id, outcome)  [single canonical path]
    → EventBus → handlers → queue/knowledge/cache updates
    → Scheduler marks task done/failed
    → FSM returns to IDLE

AutonomousPipeline remains the single canonical execution path.
The orchestrator ONLY adds: FSM, scheduling, leasing, recovery, journaling.

dry_run flag (via context/config, single code path):
  - QUEUEING: skip actual queue claim
  - VALIDATING: return simulated pipeline result (same structure as real)
  - SYNCING: skip actual queue mark_done/fail
  - All FSM transitions, journal writes, context saves run normally.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from .runtime_state import OrchestratorState, validate_transition, StateError, TERMINAL_STATES
from .runtime_context import OrchestratorContext, CycleResult, _generate_run_id
from .journal import RuntimeJournal
from .scheduler import RuntimeScheduler
from .health import LabHealthCheck, HealthStatus
from services.alpha_discovery.persistent_queue import PersistentAlphaQueue

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_DRY_RUN_PIPELINE_RESULT = {
    "success": True,
    "events_emitted": [
        "ResearchFinished", "KnowledgeUpdated", "ValidationCompleted",
        "AlphaPlannerUpdated", "LearningUpdated", "DashboardUpdated",
    ],
    "stages": {
        "knowledge": True, "validation": True, "alpha_planner": True,
        "learning": True, "dashboard": True,
    },
    "total_events": 6,
    "_dry_run": True,
}


class RuntimeOrchestrator:
    """Autonomous research loop manager.

    Controls the FSM, delegates all business logic to AutonomousPipeline.
    """

    STATE_FILE    = "runtime/orchestrator_state.json"
    JOURNAL_FILE  = "runtime/orchestrator_journal.jsonl"
    QUEUE_FILE    = "data/alpha/queue.json"

    def __init__(
        self,
        project_root: Path = PROJECT_ROOT,
        dry_run: bool = False,
        max_error_count: int = 3,
        lease_minutes: int = 30,
        cycle_interval_s: float = 0.0,
    ) -> None:
        self._root            = project_root
        self._dry_run         = dry_run
        self._max_error_count = max_error_count
        self._lease_minutes   = lease_minutes
        self._cycle_interval  = cycle_interval_s

        state_path   = project_root / self.STATE_FILE
        journal_path = project_root / self.JOURNAL_FILE
        queue_path   = project_root / self.QUEUE_FILE

        self._state_path = state_path
        self._queue      = PersistentAlphaQueue(queue_path)
        self._queue.load()

        self._scheduler = RuntimeScheduler(self._queue, lease_minutes=lease_minutes)
        self._journal   = RuntimeJournal(journal_path)
        self._health    = LabHealthCheck(project_root)
        self._context   = OrchestratorContext.load_or_new(state_path)

        self._startup_recovery()

    # ── Public API ────────────────────────────────────────────────────────────

    def run_once(self) -> CycleResult:
        """Execute exactly one full FSM cycle and return its result."""
        return self._execute_cycle()

    def run_continuous(self, max_cycles: int | None = None) -> list[CycleResult]:
        """Run cycles until max_cycles reached or error limit hit.

        max_cycles=None → run until error limit or external stop (KeyboardInterrupt).
        """
        results: list[CycleResult] = []
        cycle_num = 0
        try:
            while max_cycles is None or cycle_num < max_cycles:
                result = self._execute_cycle()
                results.append(result)
                cycle_num += 1

                if self._context.error_count >= self._max_error_count:
                    log.warning(
                        "Stopping: error_count=%d >= max=%d",
                        self._context.error_count, self._max_error_count,
                    )
                    break

                if self._cycle_interval > 0:
                    time.sleep(self._cycle_interval)
        except KeyboardInterrupt:
            self._journal.record("ORCHESTRATOR_STOPPED", {}, reason="KeyboardInterrupt")
        return results

    def status(self) -> dict:
        """Return current orchestrator status as a plain dict."""
        return {
            "run_id":          self._context.run_id,
            "state":           self._context.state,
            "cycle_count":     self._context.cycle_count,
            "error_count":     self._context.error_count,
            "dry_run":         self._dry_run,
            "current_task":    self._context.current_entry_id,
            "last_completed":  self._context.last_cycle_completed_at,
            "queue_stats":     self._scheduler.queue_stats(),
        }

    # ── Core cycle ────────────────────────────────────────────────────────────

    def _execute_cycle(self) -> CycleResult:
        cycle_id     = f"cycle_{self._context.cycle_count + 1:04d}"
        started_at   = _now()
        t0           = time.monotonic()
        entry_id: str | None = None
        strategy_id  = ""
        pipeline_result: dict = {}
        no_task      = False
        error_msg: str | None = None

        try:
            # ── PLANNING ─────────────────────────────────────────────────────
            self._transition("PLANNING")
            task = self._phase_planning()

            if task is None:
                no_task = True
                self._journal.record("CYCLE_SKIP", {}, reason="Queue has no pending tasks")
                self._transition("IDLE")
                return self._make_result(
                    cycle_id, None, "", "IDLE",
                    no_task=True, pipeline_result={},
                    started_at=started_at, t0=t0, error=None,
                )

            entry_id    = task["entry_id"]
            strategy_id = task["strategy_or_instrument"]
            self._context.current_entry_id    = entry_id
            self._context.current_strategy_id = strategy_id
            self._context.save(self._state_path)

            # ── QUEUEING ─────────────────────────────────────────────────────
            self._transition("QUEUEING")
            self._phase_queueing(entry_id)

            # ── VALIDATING ───────────────────────────────────────────────────
            self._transition("VALIDATING")
            pipeline_result = self._phase_validating(strategy_id)

            # ── LEARNING ─────────────────────────────────────────────────────
            self._transition("LEARNING")
            self._phase_learning(pipeline_result)

            # ── SYNCING ──────────────────────────────────────────────────────
            self._transition("SYNCING")
            self._phase_syncing(entry_id, pipeline_result)

            # ── Back to IDLE ─────────────────────────────────────────────────
            self._transition("IDLE")
            self._context.cycle_count        += 1
            self._context.error_count         = 0
            self._context.current_entry_id    = None
            self._context.current_strategy_id = None

            result = self._make_result(
                cycle_id, entry_id, strategy_id, "IDLE",
                no_task=False, pipeline_result=pipeline_result,
                started_at=started_at, t0=t0, error=None,
            )

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            log.error("Cycle %s failed in state %s: %s",
                      cycle_id, self._context.state, error_msg)
            self._journal.record("CYCLE_ERROR", {
                "cycle_id": cycle_id,
                "state_at_error": self._context.state,
                "error": error_msg,
            }, reason="Unhandled exception during cycle")

            # Attempt FSM error transition (may itself fail if already in ERROR)
            try:
                self._transition("ERROR")
            except StateError:
                self._context.state = "ERROR"
                self._context.save(self._state_path)

            self._context.error_count += 1
            self._context.error_message = error_msg

            # Release claim on entry if we had one
            if entry_id and not self._dry_run:
                self._scheduler.fail_task(entry_id, error_msg)
                self._queue.save()

            # Recovery: back to IDLE unless error limit reached
            if self._context.error_count < self._max_error_count:
                try:
                    self._transition("IDLE")
                except StateError:
                    self._context.state = "IDLE"
                    self._context.save(self._state_path)

            result = self._make_result(
                cycle_id, entry_id, strategy_id, "ERROR",
                no_task=no_task, pipeline_result=pipeline_result,
                started_at=started_at, t0=t0, error=error_msg,
            )

        self._context.push_cycle(result)
        self._context.save(self._state_path)
        return result

    # ── Phases ────────────────────────────────────────────────────────────────

    def _phase_planning(self) -> dict | None:
        task = self._scheduler.next_task()
        if task:
            self._journal.record(
                "TASK_SELECTED",
                {"entry_id": task["entry_id"], "strategy": task["strategy_or_instrument"],
                 "priority": task["priority"], "score": task.get("priority_score", 0)},
                reason="Highest-priority pending entry from queue",
            )
        return task

    def _phase_queueing(self, entry_id: str) -> None:
        if not self._dry_run:
            claimed = self._scheduler.claim_task(entry_id)
            if not claimed:
                raise RuntimeError(f"Failed to claim entry {entry_id} — may have been claimed by another process")
            self._queue.save()
        self._journal.record(
            "TASK_CLAIMED",
            {"entry_id": entry_id, "dry_run": self._dry_run,
             "lease_minutes": self._lease_minutes},
            reason="Entry marked in_progress with time-bounded lease",
        )

    def _phase_validating(self, strategy_id: str) -> dict:
        """Run AutonomousPipeline (live) or return simulated result (dry_run).

        dry_run uses the same code path — only the pipeline call is replaced
        by a pre-built result dict with the same schema.
        """
        if self._dry_run:
            result = dict(_DRY_RUN_PIPELINE_RESULT)
            self._journal.record(
                "PIPELINE_SIMULATED",
                {"strategy_id": strategy_id, "events": result["events_emitted"]},
                reason="dry_run=True: pipeline skipped, returning simulated result",
            )
            return result

        from services.event_pipeline.pipeline import AutonomousPipeline
        pipeline = AutonomousPipeline(verbose=False)
        result = pipeline.run(
            strategy_id=strategy_id,
            outcome="FAIL",   # Research hasn't run; pipeline processes post-research artifacts
        )
        self._journal.record(
            "PIPELINE_RUN",
            {"strategy_id": strategy_id, "success": result.get("success"),
             "events": result.get("events_emitted", [])},
            reason="AutonomousPipeline executed full event chain",
        )
        return result

    def _phase_learning(self, pipeline_result: dict) -> None:
        success = pipeline_result.get("success", False)
        stages  = pipeline_result.get("stages", {})
        self._journal.record(
            "PIPELINE_ASSESSED",
            {"success": success, "stages": stages,
             "dry_run": pipeline_result.get("_dry_run", False)},
            reason="Post-pipeline outcome assessment",
        )

    def _phase_syncing(self, entry_id: str, pipeline_result: dict) -> None:
        success = pipeline_result.get("success", False)
        if not self._dry_run:
            if success:
                self._scheduler.complete_task(entry_id)
                self._journal.record(
                    "TASK_COMPLETED", {"entry_id": entry_id},
                    reason="Pipeline succeeded — marking queue entry done",
                )
            else:
                self._scheduler.fail_task(entry_id, "Pipeline did not reach DashboardUpdated")
                self._journal.record(
                    "TASK_FAILED", {"entry_id": entry_id},
                    reason="Pipeline did not reach DashboardUpdated",
                )
            self._queue.save()
        else:
            self._journal.record(
                "TASK_SYNC_SKIPPED",
                {"entry_id": entry_id, "would_succeed": success},
                reason="dry_run=True: queue mutation skipped",
            )

    # ── FSM transition ────────────────────────────────────────────────────────

    def _transition(self, new_state: str) -> None:
        validate_transition(self._context.state, new_state)
        old_state = self._context.state
        self._context.state = new_state
        self._journal.record(
            "STATE_TRANSITION",
            {"from": old_state, "to": new_state},
        )
        self._context.save(self._state_path)

    # ── Startup recovery ──────────────────────────────────────────────────────

    def _startup_recovery(self) -> None:
        """On startup: recover expired leases and reset non-terminal FSM state."""
        recovered = self._scheduler.recover_expired_leases()
        if recovered > 0:
            self._journal.record(
                "LEASE_RECOVERY",
                {"recovered": recovered},
                reason="Expired leases found at startup → entries returned to pending",
            )
            self._queue.save()

        if self._context.state not in TERMINAL_STATES:
            self._journal.record(
                "STATE_RECOVERY",
                {"from": self._context.state, "to": "IDLE"},
                reason=f"Non-terminal state '{self._context.state}' at startup → resetting to IDLE",
            )
            self._context.state = "IDLE"
            self._context.save(self._state_path)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_result(
        self,
        cycle_id: str,
        entry_id: str | None,
        strategy_id: str,
        final_state: str,
        no_task: bool,
        pipeline_result: dict,
        started_at: str,
        t0: float,
        error: str | None,
    ) -> CycleResult:
        return CycleResult(
            cycle_id=cycle_id,
            entry_id=entry_id,
            strategy_id=strategy_id,
            final_state=final_state,
            no_task=no_task,
            pipeline_success=pipeline_result.get("success", False) if not no_task else False,
            pipeline_events=pipeline_result.get("events_emitted", []),
            started_at=started_at,
            completed_at=_now(),
            duration_s=time.monotonic() - t0,
            error=error,
            dry_run=self._dry_run,
        )

    @property
    def context(self) -> OrchestratorContext:
        return self._context

    @property
    def journal(self) -> RuntimeJournal:
        return self._journal

    @property
    def scheduler(self) -> RuntimeScheduler:
        return self._scheduler
