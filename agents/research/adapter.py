"""ValidationAgentAdapter — Layer 3 RESEARCH Agent.

Safe bridge between ExperimentPlanner and the existing Research Service.
Executes an already-formed ExperimentPlan; makes NO research decisions.

Constraints (enforced, not configurable):
  - dry_run=True by default; real execution requires execute=True explicitly.
  - Plans with high overfitting_risk are blocked unless allow_high_risk=True.
  - Stop conditions from ExperimentPlan are checked before every task.
  - Research Service is called read-only (config constructed per-task, no modifications).
  - DatasetLoader is not modified.

Planning rules (from Phase 6) are NOT re-implemented here.
This adapter ONLY executes plans produced by ExperimentPlanner.

Mode labels in ValidationRun.mode:
  "dry_run" — execute=False (no Research Service calls, plan fully validated)
  "execute" — execute=True, FileValidationSource (real Research Service runs)
  "fixture" — execute=True, _source injected (pre-baked fixture, used in tests)

Storage: {data_dir}/research_programs/validation_runs/{run_id}.json
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from agents.models import (
    AgentResult,
    ConfidenceScore,
    EvidenceRef,
    ExperimentPlan,
    ExperimentTask,
    OverfittingRisk,
    StopCondition,
    ValidationBatchResult,
    ValidationRun,
    ValidationTaskResult,
)

_AGENT_ID = "validation-agent-adapter"
_AGENT_TYPE = "RESEARCH"
_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Plan loader — read ExperimentPlan from research_programs/plans/
# ---------------------------------------------------------------------------

def load_plan(data_dir: Path, plan_id: str) -> ExperimentPlan:
    """Deserialize an ExperimentPlan JSON written by ExperimentPlanner.

    Raises FileNotFoundError if plan_id.json does not exist.
    """
    path = data_dir / "research_programs" / "plans" / f"{plan_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"ExperimentPlan not found: {path}")

    with open(path, encoding="utf-8") as fp:
        d = json.load(fp)

    return ExperimentPlan(
        plan_id=d["plan_id"],
        plan_type=d["plan_type"],
        objective=d["objective"],
        hypothesis_id=d["hypothesis_id"],
        instruments=tuple(d["instruments"]),
        datasets=tuple(d["datasets"]),
        regime_filter=d["regime_filter"],
        tasks=tuple(
            ExperimentTask(
                task_id=t["task_id"],
                hypothesis_id=t["hypothesis_id"],
                instrument=t["instrument"],
                dataset_id=t["dataset_id"],
                regime_filter=t["regime_filter"],
                parameters=tuple(sorted(t["parameters"].items())),
            )
            for t in d["tasks"]
        ),
        parameters=tuple(sorted(d["parameters"].items())),
        expected_evidence=tuple(d["expected_evidence"]),
        rationale=d["rationale"],
        priority=d["priority"],
        overfitting_risk=OverfittingRisk(
            level=d["overfitting_risk"]["level"],
            parameter_count=d["overfitting_risk"]["parameter_count"],
            reasons=tuple(d["overfitting_risk"]["reasons"]),
        ),
        stop_conditions=tuple(
            StopCondition(
                condition_type=sc["condition_type"],
                value=sc["value"],
                description=sc["description"],
            )
            for sc in d["stop_conditions"]
        ),
        confidence=d["confidence"],
        source_pattern_id=d["source_pattern_id"],
    )


# ---------------------------------------------------------------------------
# ValidationSource implementations
# ---------------------------------------------------------------------------

class FileValidationSource:
    """Production source — checks real filesystem, calls ResearchRunner.

    ResearchRunner import is deferred to run_task() to avoid heavy import costs
    during test collection and dry-run validation.
    """

    def __init__(self, data_dir: Path, output_dir: Path) -> None:
        self._data_dir = data_dir
        self._output_dir = output_dir

    def dataset_exists(self, dataset_id: str) -> bool:
        dataset_dir = self._data_dir / "datasets" / dataset_id
        return (dataset_dir / "ohlcv.csv").exists()

    def run_task(self, task: ExperimentTask, dry_run: bool) -> ValidationTaskResult:
        if dry_run:
            return _dry_run_result(task)

        # Deferred import — keeps test collection fast and avoids side effects.
        from services.research.config import ServiceConfig
        from services.research.runner import ResearchRunner

        config = ServiceConfig(
            dataset_id=task.dataset_id,
            data_dir=self._data_dir,
            output_dir=self._output_dir,
        )
        t0 = time.monotonic()
        try:
            run_result = ResearchRunner().run(config)
            duration = time.monotonic() - t0
            return ValidationTaskResult(
                task_id=task.task_id,
                hypothesis_id=task.hypothesis_id,
                dataset_id=task.dataset_id,
                status="success",
                exit_code=run_result.exit_code,
                pass_rate=None,  # aggregate is in the report JSON
                report_path=str(run_result.report_path),
                error="",
                duration_seconds=round(duration, 3),
            )
        except Exception as exc:
            duration = time.monotonic() - t0
            return ValidationTaskResult(
                task_id=task.task_id,
                hypothesis_id=task.hypothesis_id,
                dataset_id=task.dataset_id,
                status="error",
                exit_code=1,
                pass_rate=None,
                report_path="",
                error=str(exc),
                duration_seconds=round(duration, 3),
            )


class FixtureValidationSource:
    """Test fixture source — returns pre-configured results without I/O.

    task_results:     {task_id: dict} — override per-task (optional).
    missing_datasets: dataset_ids to report as non-existent.
    default_pass_rate: pass_rate for tasks without a specific override.

    dict keys for task_results: status, exit_code, pass_rate, report_path, error, duration_seconds
    """

    def __init__(
        self,
        task_results: Optional[dict[str, dict]] = None,
        missing_datasets: Optional[list[str]] = None,
        default_pass_rate: float = 0.65,
    ) -> None:
        self._results = task_results or {}
        self._missing: set[str] = set(missing_datasets or [])
        self._default_pass_rate = default_pass_rate

    def dataset_exists(self, dataset_id: str) -> bool:
        return dataset_id not in self._missing

    def run_task(self, task: ExperimentTask, dry_run: bool) -> ValidationTaskResult:
        if dry_run:
            return _dry_run_result(task)

        override = self._results.get(task.task_id, {})
        return ValidationTaskResult(
            task_id=task.task_id,
            hypothesis_id=task.hypothesis_id,
            dataset_id=task.dataset_id,
            status=override.get("status", "success"),
            exit_code=override.get("exit_code", 0),
            pass_rate=override.get("pass_rate", self._default_pass_rate),
            report_path=override.get("report_path", f"reports/{task.dataset_id}/report.json"),
            error=override.get("error", ""),
            duration_seconds=override.get("duration_seconds", 1.0),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dry_run_result(task: ExperimentTask) -> ValidationTaskResult:
    return ValidationTaskResult(
        task_id=task.task_id,
        hypothesis_id=task.hypothesis_id,
        dataset_id=task.dataset_id,
        status="dry_run",
        exit_code=-1,
        pass_rate=None,
        report_path="",
        error="",
        duration_seconds=0.0,
    )


def _blocked_result(task: ExperimentTask, reason: str) -> ValidationTaskResult:
    return ValidationTaskResult(
        task_id=task.task_id,
        hypothesis_id=task.hypothesis_id,
        dataset_id=task.dataset_id,
        status="blocked",
        exit_code=-3,
        pass_rate=None,
        report_path="",
        error=reason,
        duration_seconds=0.0,
    )


def _error_result(task: ExperimentTask, reason: str) -> ValidationTaskResult:
    return ValidationTaskResult(
        task_id=task.task_id,
        hypothesis_id=task.hypothesis_id,
        dataset_id=task.dataset_id,
        status="error",
        exit_code=1,
        pass_rate=None,
        report_path="",
        error=reason,
        duration_seconds=0.0,
    )


def _check_stop_conditions(
    stop_conditions: tuple[StopCondition, ...],
    task_results: list[ValidationTaskResult],
) -> tuple[bool, str]:
    """Check all stop conditions against current task_results.

    Returns (triggered, reason).  Called BEFORE each new task.
    """
    n_run = len(task_results)

    for sc in stop_conditions:
        if sc.condition_type == "max_experiments" and n_run >= int(sc.value):
            return True, f"max_experiments={int(sc.value)} reached after {n_run} tasks"

    # min_pass_rate: only meaningful after at least one completed task
    rates = [r.pass_rate for r in task_results if r.pass_rate is not None]
    if rates:
        avg = sum(rates) / len(rates)
        for sc in stop_conditions:
            if sc.condition_type == "min_pass_rate" and avg < sc.value:
                return (
                    True,
                    f"avg_pass_rate={avg:.3f} below min_pass_rate={sc.value}",
                )

    return False, ""


def _make_batch_result(
    batch_id: str,
    plan_id: str,
    campaign_id: str,
    task_results: list[ValidationTaskResult],
    stop_triggered: bool,
    stop_reason: str,
    run_path: str,
    created_at: str,
) -> ValidationBatchResult:
    completed = [r for r in task_results if r.status == "success"]
    rates = [r.pass_rate for r in completed if r.pass_rate is not None]

    return ValidationBatchResult(
        batch_id=batch_id,
        plan_id=plan_id,
        campaign_id=campaign_id,
        total_tasks=len(task_results),
        completed_tasks=len(completed),
        stopped_tasks=sum(1 for r in task_results if r.status == "stopped"),
        error_tasks=sum(1 for r in task_results if r.status == "error"),
        dry_run_tasks=sum(1 for r in task_results if r.status == "dry_run"),
        blocked_tasks=sum(1 for r in task_results if r.status == "blocked"),
        avg_pass_rate=round(sum(rates) / len(rates), 6) if rates else None,
        stop_triggered=stop_triggered,
        stop_reason=stop_reason,
        report_paths=tuple(r.report_path for r in completed if r.report_path),
        validation_run_path=run_path,
        created_at=created_at,
    )


def _write_validation_run(data_dir: Path, run: ValidationRun) -> Path:
    out = data_dir / "research_programs" / "validation_runs"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{run.run_id}.json"

    payload = {
        "run_id": run.run_id,
        "plan_id": run.plan_id,
        "campaign_id": run.campaign_id,
        "mode": run.mode,
        "stop_triggered": run.stop_triggered,
        "stop_reason": run.stop_reason,
        "created_at": run.created_at,
        "task_results": [
            {
                "task_id": r.task_id,
                "hypothesis_id": r.hypothesis_id,
                "dataset_id": r.dataset_id,
                "status": r.status,
                "exit_code": r.exit_code,
                "pass_rate": r.pass_rate,
                "report_path": r.report_path,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
            }
            for r in run.task_results
        ],
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)
    return path


def _make_run_id(plan_id: str, created_at: str) -> str:
    """Deterministic run_id from plan_id prefix and ISO timestamp."""
    ts = created_at.replace("-", "").replace(":", "").replace("T", "")
    safe_plan = plan_id[:24].replace("/", "_")
    return f"vrun_{safe_plan}_{ts}"


def _evidence_confidence(task_results: list[ValidationTaskResult], plan: ExperimentPlan, execute: bool) -> float:
    if not execute:
        # dry_run: plan confidence halved — structurally valid but not yet evidenced
        return round(plan.confidence * 0.5, 6)
    rates = [r.pass_rate for r in task_results if r.pass_rate is not None]
    if rates:
        return round(sum(rates) / len(rates), 6)
    # executed but no pass_rate available (e.g. Research Service reported none)
    return round(plan.confidence * 0.7, 6)


# ---------------------------------------------------------------------------
# ValidationAgentAdapter
# ---------------------------------------------------------------------------

class ValidationAgentAdapter:
    """Layer 3 RESEARCH Agent — safe execution bridge for ExperimentPlan.

    Converts ExperimentPlan tasks into Research Service calls.
    Enforces safety guards before any execution:
      1. High overfitting_risk blocked unless allow_high_risk=True.
      2. Missing datasets abort the run before any task starts.
      3. Stop conditions checked before each task.
      4. execute=False (dry_run) by default — no real Research Service calls.

    Does NOT modify ExperimentPlan, Research Service, DatasetLoader, or hypotheses.
    Does NOT generate new plans or trading signals.
    """

    agent_id = _AGENT_ID
    agent_type = _AGENT_TYPE
    version = _VERSION

    def __init__(self, data_dir: Path, output_dir: Optional[Path] = None) -> None:
        self._data_dir = data_dir
        self._output_dir = output_dir or data_dir

    def run(
        self,
        plan: ExperimentPlan,
        available_datasets: list[str],
        campaign_id: str = "default",
        execute: bool = False,
        allow_high_risk: bool = False,
        _clock: Optional[Callable[[], datetime]] = None,
        _source: Optional[object] = None,
    ) -> AgentResult:
        """Execute or dry-run an ExperimentPlan.

        Parameters
        ----------
        plan:               ExperimentPlan from ExperimentPlanner.
        available_datasets: list of known dataset_ids (used for cross-check).
        campaign_id:        label for logging.
        execute:            False (default) = dry_run only; True = call Research Service.
        allow_high_risk:    False (default) = block high overfitting_risk plans.
        _clock:             injected clock for deterministic created_at.
        _source:            injected ValidationSource for fixture testing.
        """
        clock = _clock or datetime.now
        created_at = clock().isoformat(timespec="seconds")
        run_id = _make_run_id(plan.plan_id, created_at)
        batch_id = f"{run_id}_batch"

        source = _source if _source is not None else FileValidationSource(
            self._data_dir, self._output_dir
        )
        mode = "fixture" if _source is not None else ("execute" if execute else "dry_run")

        evidence_ref = EvidenceRef(
            source=f"plan/{plan.plan_id}",
            reference=plan.plan_id,
            timestamp=created_at,
        )

        # ── Guard 1: High overfitting risk ────────────────────────────────────
        if plan.overfitting_risk.level == "high" and not allow_high_risk:
            block_reason = (
                f"Blocked: plan {plan.plan_id} has high overfitting_risk "
                f"(parameter_count={plan.overfitting_risk.parameter_count}). "
                f"Pass allow_high_risk=True to override."
            )
            task_results = [_blocked_result(t, block_reason) for t in plan.tasks]
            return self._finish(
                run_id, batch_id, plan, campaign_id, mode,
                task_results, True, block_reason,
                created_at, evidence_ref, execute,
            )

        # ── Guard 2: Dataset existence (only when executing — dry_run skips I/O) ──
        if execute:
            missing = [
                t.dataset_id for t in plan.tasks
                if not source.dataset_exists(t.dataset_id)  # type: ignore[attr-defined]
            ]
            if missing:
                miss_reason = f"Missing datasets: {missing}"
                task_results = [_error_result(t, f"Dataset not found: {t.dataset_id}") for t in plan.tasks]
                return self._finish(
                    run_id, batch_id, plan, campaign_id, mode,
                    task_results, True, miss_reason,
                    created_at, evidence_ref, execute,
                )

        # ── Execute tasks with stop condition checking ────────────────────────
        task_results: list[ValidationTaskResult] = []
        stop_triggered = False
        stop_reason = ""

        for task in plan.tasks:
            triggered, reason = _check_stop_conditions(plan.stop_conditions, task_results)
            if triggered:
                stop_triggered = True
                stop_reason = reason
                break

            result = source.run_task(task, dry_run=not execute)  # type: ignore[attr-defined]
            task_results.append(result)

        return self._finish(
            run_id, batch_id, plan, campaign_id, mode,
            task_results, stop_triggered, stop_reason,
            created_at, evidence_ref, execute,
        )

    # ── Internal finish helper ────────────────────────────────────────────────

    def _finish(
        self,
        run_id: str,
        batch_id: str,
        plan: ExperimentPlan,
        campaign_id: str,
        mode: str,
        task_results: list[ValidationTaskResult],
        stop_triggered: bool,
        stop_reason: str,
        created_at: str,
        evidence_ref: EvidenceRef,
        execute: bool,
    ) -> AgentResult:
        validation_run = ValidationRun(
            run_id=run_id,
            plan_id=plan.plan_id,
            campaign_id=campaign_id,
            mode=mode,
            task_results=tuple(task_results),
            stop_triggered=stop_triggered,
            stop_reason=stop_reason,
            created_at=created_at,
        )
        run_path = _write_validation_run(self._data_dir, validation_run)

        batch = _make_batch_result(
            batch_id, plan.plan_id, campaign_id,
            task_results, stop_triggered, stop_reason,
            str(run_path), created_at,
        )

        completed_count = sum(1 for r in task_results if r.status == "success")
        conf_value = _evidence_confidence(task_results, plan, execute)
        if stop_triggered and not task_results:
            conf_value = 0.0

        n_run = len(task_results)
        n_total = len(plan.tasks)
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            version=self.version,
            input_summary=(
                f"{mode} {plan.plan_id}: "
                f"{n_run}/{n_total} tasks"
                + (f" | stop: {stop_reason}" if stop_triggered else "")
                + (f" | completed: {completed_count}" if execute else "")
            ),
            output=batch,
            evidence=(evidence_ref,),
            confidence=ConfidenceScore(
                value=max(0.0, min(1.0, conf_value)),
                reason=(
                    f"{mode}: {n_run} tasks run"
                    + (f", avg_pass_rate={batch.avg_pass_rate:.3f}" if batch.avg_pass_rate is not None else "")
                ),
            ),
            created_at=created_at,
        )
