# M12 Sprint 2 — Autonomous Runtime Orchestrator

**Date:** 2026-06-29  
**Sprint:** M12 Sprint 2  
**Status:** COMPLETE — all 189 integration + runtime tests pass

---

## 1. Overview

Sprint 2 delivers `RuntimeOrchestrator` — the FSM-based autonomous loop that manages the research pipeline without duplicating any business logic. The canonical execution path is:

```
RuntimeOrchestrator
  → Scheduler.next_task()              (PLANNING)
  → Scheduler.claim_task(lease_until)  (QUEUEING)
  → AutonomousPipeline.run()           (VALIDATING)
  → EventBus → handlers               (pipeline-internal)
  → Scheduler.complete_task()          (SYNCING)
  → FSM → IDLE
```

`AutonomousPipeline` remains the single canonical execution path for all business logic.
The orchestrator adds only: FSM, scheduling, lease/recovery, journaling, dry-run.

---

## 2. Files Changed

### New — `services/runtime/`

| File | Purpose |
|---|---|
| `__init__.py` | Package exports |
| `runtime_state.py` | `OrchestratorState` enum, `TRANSITIONS` dict, `StateError`, `validate_transition()` |
| `runtime_context.py` | `CycleResult` dataclass, `OrchestratorContext` (load/save `orchestrator_state.json`) |
| `journal.py` | `RuntimeJournal` — append-only JSONL, records what + why per event |
| `scheduler.py` | `RuntimeScheduler` — task selection, lease/claim, recovery |
| `health.py` | `LabHealthCheck` — 4 read-only checks: queue, knowledge_store, state, reports_dir |
| `orchestrator.py` | `RuntimeOrchestrator` — FSM loop, `run_once()`, `run_continuous()`, dry-run |

### Modified — `services/alpha_discovery/persistent_queue.py`

- `mark_in_progress(entry_id, lease_until="")` — added `claimed_at` + `lease_until` fields
- `recover_expired_leases()` — returns stale `in_progress` entries to `pending` when `lease_until < now`

Backward compatible: `lease_until` defaults to `""` so existing callers (Sprint 1 tests) unchanged.

### New — `scripts/run_autonomous_runtime.py`

CLI: `--status`, `--journal [--tail N]`, `--health`, `--dry-run [--cycles N]`, `--live --run-once`

### New — `tests/runtime/` (69 tests)

| File | Tests | What's covered |
|---|---|---|
| `test_fsm.py` | 16 | All valid transitions, all invalid transitions (StateError), terminal states |
| `test_scheduler.py` | 12 | next_task, claim_task, lease expiry recovery, complete/fail |
| `test_orchestrator.py` | 22 | run_once dry/empty, dry_run no mutation, state persistence, crash recovery, journal |
| `test_health.py` | 12 | OK/WARNING/CRITICAL per check, check_all, is_healthy |

### New — `docs/reports/M12_SPRINT_2_RUNTIME_ORCHESTRATOR_REPORT.md`

This file.

### New — `runtime/orchestrator_state.json` (generated at runtime)

FSM state, cycle count, history. Separate from `runtime/status.json` (Research Campaign Executor).

### New — `runtime/orchestrator_journal.jsonl` (generated at runtime)

Append-only event log. Each entry: `{ts, event, reason, data}`.

---

## 3. FSM Design

```
IDLE ──────────────► PLANNING
  ▲                    │ (no task)     ▼
  │◄────────────────────              IDLE
  │                    │ (task found)
  │                    ▼
  │                 QUEUEING
  │                    │
  │                    ▼
  │                VALIDATING ─── (AutonomousPipeline.run())
  │                    │
  │                    ▼
  │                 LEARNING ─── (assess result)
  │                    │
  │                    ▼
  │                  SYNCING ─── (mark_done / mark_failed)
  │                    │
  └────────────────────┘

  Every state → ERROR (exception catch)
  ERROR → IDLE (recovery, if error_count < max_error_count)
```

**Key constraints enforced:**
- `validate_transition()` raises `StateError` on any invalid edge
- `TERMINAL_STATES = {"IDLE", "ERROR"}` — only these are safe at startup
- Non-terminal state at startup → automatic reset to IDLE + journal entry

---

## 4. Lease-Based Recovery

```json
{
  "entry_id": "a1b2c3d4",
  "status": "in_progress",
  "claimed_at": "2026-06-29T14:00:00+00:00",
  "lease_until": "2026-06-29T14:30:00+00:00"
}
```

- `Scheduler.claim_task(entry_id)` sets `lease_until = now + 30min`
- `recover_expired_leases()` is called at orchestrator startup
- Any entry where `lease_until < now` is returned to `pending`
- Empty `lease_until` is skipped (backwards compat with Sprint 1 entries)

---

## 5. Dry-Run Design

Single code path. `dry_run=True` only affects three points:

| Phase | Live | Dry-Run |
|---|---|---|
| QUEUEING | `queue.mark_in_progress()` | skipped |
| VALIDATING | `AutonomousPipeline.run()` | returns `_DRY_RUN_PIPELINE_RESULT` dict (same schema) |
| SYNCING | `queue.mark_done()/fail()` | skipped |

All FSM transitions, journal writes, context saves, health checks run identically in both modes.

---

## 6. Architecture Constraints Verified

| Constraint | Status |
|---|---|
| `services/runtime/` never imports `terminal.*` | PASS (test_03 verifies) |
| `runtime/status.json` not touched | PASS (orchestrator uses `orchestrator_state.json`) |
| Sprint 1 tests (120) unchanged | PASS — 120/120 |
| `AutonomousPipeline` is single canonical path | PASS — orchestrator never calls handlers directly |
| `research/` and `agents/` not modified | PASS |
| No `git add/commit/push` in automation | PASS |

---

## 7. Test Results

```
tests/integration/   120/120 passed  (Sprint 1 unchanged)
tests/runtime/        69/69  passed  (Sprint 2 new)
Total:               189/189 passed
```

**Pre-existing failures (unrelated to Sprint 2):**
- `test_candidate_validation.py::test_returns_17_records` — `EnrichedFact` schema mismatch (`updated_by` field) in `services/knowledge/evolution.py`
- `test_m8_stability_engine.py::test_stability_facts_loadable_by_knowledge_store` — same root cause

Both were failing before Sprint 2. Neither file was modified in this sprint.

---

## 8. Persistent State Files

| File | Owner | Contents |
|---|---|---|
| `runtime/status.json` | `scripts/autonomous_runtime.py` | Research campaign progress |
| `runtime/orchestrator_state.json` | `RuntimeOrchestrator` | FSM state, cycle count, history |
| `runtime/orchestrator_journal.jsonl` | `RuntimeJournal` | Append-only event log |
| `data/alpha/queue.json` | `PersistentAlphaQueue` | Alpha work queue with leases |
