"""M12 Sprint 2 — OrchestratorContext and CycleResult.

OrchestratorContext is persisted to runtime/orchestrator_state.json.
CycleResult is appended to context.history after each completed cycle.

The context is the single source of truth for:
- current FSM state
- cycle counter
- current task being processed
- error counter
- recent history (last 50 cycles)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime_state import OrchestratorState, TERMINAL_STATES

SCHEMA_VERSION = "1.0"
MAX_HISTORY = 50


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── CycleResult ───────────────────────────────────────────────────────────────

@dataclass
class CycleResult:
    cycle_id: str
    entry_id: str | None
    strategy_id: str
    final_state: str              # "IDLE" (success) or "ERROR"
    no_task: bool                 # True when queue was empty
    pipeline_success: bool
    pipeline_events: list[str]
    started_at: str
    completed_at: str
    duration_s: float
    error: str | None
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "entry_id": self.entry_id,
            "strategy_id": self.strategy_id,
            "final_state": self.final_state,
            "no_task": self.no_task,
            "pipeline_success": self.pipeline_success,
            "pipeline_events": self.pipeline_events,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_s": round(self.duration_s, 3),
            "error": self.error,
            "dry_run": self.dry_run,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CycleResult":
        return cls(
            cycle_id=d.get("cycle_id", ""),
            entry_id=d.get("entry_id"),
            strategy_id=d.get("strategy_id", ""),
            final_state=d.get("final_state", "IDLE"),
            no_task=d.get("no_task", False),
            pipeline_success=d.get("pipeline_success", False),
            pipeline_events=d.get("pipeline_events", []),
            started_at=d.get("started_at", ""),
            completed_at=d.get("completed_at", ""),
            duration_s=d.get("duration_s", 0.0),
            error=d.get("error"),
            dry_run=d.get("dry_run", False),
        )


# ── OrchestratorContext ───────────────────────────────────────────────────────

@dataclass
class OrchestratorContext:
    run_id: str
    state: str
    cycle_count: int
    current_entry_id: str | None
    current_strategy_id: str | None
    error_count: int
    error_message: str | None
    last_cycle_completed_at: str | None
    history: list[dict]           # CycleResult.to_dict() entries, last N
    created_at: str
    updated_at: str

    # ── Persistence ───────────────────────────────────────────────────────────

    @classmethod
    def load_or_new(cls, path: Path, run_id: str = "") -> "OrchestratorContext":
        """Load from disk, or create fresh context if file not found/corrupt."""
        if path.exists():
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                ctx = cls(
                    run_id=doc.get("run_id", run_id or _generate_run_id()),
                    state=doc.get("state", "IDLE"),
                    cycle_count=doc.get("cycle_count", 0),
                    current_entry_id=doc.get("current_entry_id"),
                    current_strategy_id=doc.get("current_strategy_id"),
                    error_count=doc.get("error_count", 0),
                    error_message=doc.get("error_message"),
                    last_cycle_completed_at=doc.get("last_cycle_completed_at"),
                    history=doc.get("history", []),
                    created_at=doc.get("created_at", _now()),
                    updated_at=doc.get("updated_at", _now()),
                )
                return ctx
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        return cls(
            run_id=run_id or _generate_run_id(),
            state="IDLE",
            cycle_count=0,
            current_entry_id=None,
            current_strategy_id=None,
            error_count=0,
            error_message=None,
            last_cycle_completed_at=None,
            history=[],
            created_at=_now(),
            updated_at=_now(),
        )

    def save(self, path: Path) -> None:
        self.updated_at = _now()
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = {
            "schema": SCHEMA_VERSION,
            "run_id": self.run_id,
            "state": self.state,
            "cycle_count": self.cycle_count,
            "current_entry_id": self.current_entry_id,
            "current_strategy_id": self.current_strategy_id,
            "error_count": self.error_count,
            "error_message": self.error_message,
            "last_cycle_completed_at": self.last_cycle_completed_at,
            "history": self.history[-MAX_HISTORY:],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def push_cycle(self, result: CycleResult) -> None:
        """Append cycle result to history, trim to MAX_HISTORY."""
        self.history.append(result.to_dict())
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        self.last_cycle_completed_at = result.completed_at

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "state": self.state,
            "cycle_count": self.cycle_count,
            "current_entry_id": self.current_entry_id,
            "current_strategy_id": self.current_strategy_id,
            "error_count": self.error_count,
            "error_message": self.error_message,
            "last_cycle_completed_at": self.last_cycle_completed_at,
        }


def _generate_run_id() -> str:
    import uuid
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"orch_{ts}_{uuid.uuid4().hex[:6]}"
