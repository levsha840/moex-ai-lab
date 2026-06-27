"""Tests for ValidationAgentAdapter — Layer 3 RESEARCH Agent (Phase 7).

All tests use FixtureValidationSource or dry_run mode — no Research Service calls.
Covers: protocol compliance, plan loading, dataset validation, dry-run mode,
fixture execution, overfitting risk guard, stop conditions, persistence, determinism.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from agents.models import (
    AgentResult,
    ConfidenceScore,
    ExperimentPlan,
    ExperimentTask,
    KnowledgePattern,
    OverfittingRisk,
    StopCondition,
    ValidationBatchResult,
    ValidationRun,
    ValidationTaskResult,
)
from agents.research.adapter import (
    FileValidationSource,
    FixtureValidationSource,
    ValidationAgentAdapter,
    _check_stop_conditions,
    _make_batch_result,
    load_plan,
)
from agents.research.planner import ExperimentPlanner, _plan_from_underperformance

from agents.models import (
    ConfidenceScore,
    EvidenceRef,
    KnowledgeConnection,
    KnowledgeSnapshot,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_DATASETS = ["sber_1h_2023_main", "gazp_1h_2023_main", "lkoh_1h_2023_main"]


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 27, 12, 0, 0)


def _evidence() -> EvidenceRef:
    return EvidenceRef(source="test", reference="test", timestamp="2026-06-27T12:00:00")


def _conf(v: float = 0.7) -> ConfidenceScore:
    return ConfidenceScore(value=v, reason="test")


def _underperform_pattern(hyp_id: str = "H-13", occurrence_count: int = 3) -> KnowledgePattern:
    return KnowledgePattern(
        pattern_id="pat_0001",
        description=f"{hyp_id} consistently underperforms",
        pattern_type="underperformance",
        entities=(hyp_id,),
        occurrence_count=occurrence_count,
        confidence=0.6,
        supporting_facts=("f0", "f1", "f2"),
        contradicting_facts=(),
    )


def _make_plan(
    n_tasks: int = 3,
    overfitting_level: str = "low",
    stop_max_experiments: float = 10.0,
    stop_min_pass_rate: float | None = None,
    datasets: list[str] | None = None,
) -> ExperimentPlan:
    ds = (datasets or _DATASETS)[:n_tasks]
    tasks = tuple(
        ExperimentTask(
            task_id=f"plan_0001_t{i:02d}",
            hypothesis_id="H-13",
            instrument=ds[i].split("_")[0].upper(),
            dataset_id=ds[i],
            regime_filter="RANGE",
            parameters=(),
        )
        for i in range(min(n_tasks, len(ds)))
    )
    stop_conditions = [
        StopCondition(
            condition_type="max_experiments",
            value=stop_max_experiments,
            description=f"Stop after {int(stop_max_experiments)} runs",
        )
    ]
    if stop_min_pass_rate is not None:
        stop_conditions.append(StopCondition(
            condition_type="min_pass_rate",
            value=stop_min_pass_rate,
            description=f"Stop if avg pass_rate < {stop_min_pass_rate}",
        ))

    return ExperimentPlan(
        plan_id="plan_0001_explore_h13",
        plan_type="regime_exploration",
        objective="Test H-13 in RANGE regime",
        hypothesis_id="H-13",
        instruments=tuple(t.instrument for t in tasks),
        datasets=tuple(ds),
        regime_filter="RANGE",
        tasks=tasks,
        parameters=(),
        expected_evidence=("Better pass_rate in RANGE",),
        rationale="Underperformance pattern detected",
        priority="medium",
        overfitting_risk=OverfittingRisk(
            level=overfitting_level,
            parameter_count=0 if overfitting_level == "low" else (1 if overfitting_level == "medium" else 2),
            reasons=(f"{overfitting_level} risk",),
        ),
        stop_conditions=tuple(stop_conditions),
        confidence=0.6,
        source_pattern_id="pat_0001",
    )


def _fixture_source(pass_rate: float = 0.65) -> FixtureValidationSource:
    return FixtureValidationSource(default_pass_rate=pass_rate)


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------

class TestValidationAdapterProtocol:
    def test_agent_id(self, tmp_path: Path) -> None:
        assert ValidationAgentAdapter(tmp_path).agent_id == "validation-agent-adapter"

    def test_agent_type_is_research(self, tmp_path: Path) -> None:
        assert ValidationAgentAdapter(tmp_path).agent_type == "RESEARCH"

    def test_version_is_string(self, tmp_path: Path) -> None:
        assert isinstance(ValidationAgentAdapter(tmp_path).version, str)

    def test_run_is_callable(self, tmp_path: Path) -> None:
        assert callable(ValidationAgentAdapter(tmp_path).run)

    def test_run_returns_agent_result(self, tmp_path: Path) -> None:
        plan = _make_plan()
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, _clock=_fixed_clock, _source=_fixture_source()
        )
        assert isinstance(result, AgentResult)

    def test_output_is_validation_batch_result(self, tmp_path: Path) -> None:
        plan = _make_plan()
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, _clock=_fixed_clock, _source=_fixture_source()
        )
        assert isinstance(result.output, ValidationBatchResult)


# ---------------------------------------------------------------------------
# load_plan
# ---------------------------------------------------------------------------

class TestLoadPlan:
    def _write_plan(self, tmp_path: Path, plan: ExperimentPlan) -> None:
        """Use ExperimentPlanner to write the plan JSON."""
        from agents.research.planner import _write_plan
        _write_plan(tmp_path, plan)

    def test_roundtrip_plan_id(self, tmp_path: Path) -> None:
        plan = _make_plan()
        self._write_plan(tmp_path, plan)
        loaded = load_plan(tmp_path, plan.plan_id)
        assert loaded.plan_id == plan.plan_id

    def test_roundtrip_hypothesis_id(self, tmp_path: Path) -> None:
        plan = _make_plan()
        self._write_plan(tmp_path, plan)
        loaded = load_plan(tmp_path, plan.plan_id)
        assert loaded.hypothesis_id == plan.hypothesis_id

    def test_roundtrip_tasks_count(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=3)
        self._write_plan(tmp_path, plan)
        loaded = load_plan(tmp_path, plan.plan_id)
        assert len(loaded.tasks) == 3

    def test_roundtrip_overfitting_risk(self, tmp_path: Path) -> None:
        plan = _make_plan(overfitting_level="medium")
        self._write_plan(tmp_path, plan)
        loaded = load_plan(tmp_path, plan.plan_id)
        assert loaded.overfitting_risk.level == "medium"

    def test_roundtrip_stop_conditions(self, tmp_path: Path) -> None:
        plan = _make_plan()
        self._write_plan(tmp_path, plan)
        loaded = load_plan(tmp_path, plan.plan_id)
        assert len(loaded.stop_conditions) >= 1
        types = {sc.condition_type for sc in loaded.stop_conditions}
        assert "max_experiments" in types

    def test_missing_plan_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_plan(tmp_path, "plan_nonexistent")


# ---------------------------------------------------------------------------
# Dataset existence validation
# ---------------------------------------------------------------------------

class TestDatasetValidation:
    def test_missing_dataset_triggers_error_status(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=2)
        source = FixtureValidationSource(missing_datasets=["sber_1h_2023_main"])
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=source, _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.error_tasks > 0

    def test_missing_dataset_stops_entire_run(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=2)
        source = FixtureValidationSource(missing_datasets=["sber_1h_2023_main"])
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=source, _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.stop_triggered is True
        assert batch.completed_tasks == 0

    def test_all_datasets_valid_no_error(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=2)
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=_fixture_source(), _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.error_tasks == 0

    def test_file_source_nonexistent_dataset(self, tmp_path: Path) -> None:
        src = FileValidationSource(tmp_path, tmp_path)
        assert src.dataset_exists("nonexistent_dataset_xyz") is False

    def test_file_source_existing_dataset(self, tmp_path: Path) -> None:
        ds_dir = tmp_path / "datasets" / "my_dataset"
        ds_dir.mkdir(parents=True)
        (ds_dir / "ohlcv.csv").write_text("datetime,open,high,low,close,volume\n")
        src = FileValidationSource(tmp_path, tmp_path)
        assert src.dataset_exists("my_dataset") is True


# ---------------------------------------------------------------------------
# Dry-run mode (default)
# ---------------------------------------------------------------------------

class TestDryRunMode:
    def _run_dry(self, tmp_path: Path, n_tasks: int = 3) -> AgentResult:
        plan = _make_plan(n_tasks=n_tasks)
        return ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=False, _clock=_fixed_clock
        )

    def test_default_is_dry_run(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=2)
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, _source=_fixture_source(), _clock=_fixed_clock
        )
        # When _source is injected but execute=False → dry_run tasks
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.dry_run_tasks == len(plan.tasks)

    def test_dry_run_tasks_have_dry_run_status(self, tmp_path: Path) -> None:
        result = self._run_dry(tmp_path)
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.dry_run_tasks == 3
        assert batch.completed_tasks == 0

    def test_dry_run_no_report_paths(self, tmp_path: Path) -> None:
        result = self._run_dry(tmp_path)
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.report_paths == ()

    def test_dry_run_no_avg_pass_rate(self, tmp_path: Path) -> None:
        result = self._run_dry(tmp_path)
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.avg_pass_rate is None

    def test_dry_run_mode_label_in_batch(self, tmp_path: Path) -> None:
        # ValidationRun written to disk should have mode="dry_run"
        result = self._run_dry(tmp_path)
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        run_path = Path(batch.validation_run_path)
        with open(run_path) as fp:
            data = json.load(fp)
        assert data["mode"] == "dry_run"

    def test_dry_run_confidence_is_half_plan_confidence(self, tmp_path: Path) -> None:
        plan = _make_plan()
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=False, _clock=_fixed_clock
        )
        expected = plan.confidence * 0.5
        assert result.confidence.value == pytest.approx(expected, abs=1e-5)


# ---------------------------------------------------------------------------
# Fixture execution mode
# ---------------------------------------------------------------------------

class TestFixtureExecutionMode:
    def _run_fixture(
        self,
        tmp_path: Path,
        n_tasks: int = 3,
        pass_rate: float = 0.65,
    ) -> AgentResult:
        plan = _make_plan(n_tasks=n_tasks)
        return ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True,
            _source=FixtureValidationSource(default_pass_rate=pass_rate),
            _clock=_fixed_clock,
        )

    def test_all_tasks_succeed(self, tmp_path: Path) -> None:
        result = self._run_fixture(tmp_path, n_tasks=3)
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.completed_tasks == 3

    def test_mode_is_fixture(self, tmp_path: Path) -> None:
        result = self._run_fixture(tmp_path)
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        run_path = Path(batch.validation_run_path)
        with open(run_path) as fp:
            data = json.load(fp)
        assert data["mode"] == "fixture"

    def test_avg_pass_rate_computed(self, tmp_path: Path) -> None:
        result = self._run_fixture(tmp_path, pass_rate=0.72)
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.avg_pass_rate == pytest.approx(0.72, abs=1e-3)

    def test_report_paths_populated(self, tmp_path: Path) -> None:
        result = self._run_fixture(tmp_path, n_tasks=2)
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert len(batch.report_paths) == 2

    def test_per_task_override(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=2)
        task_results = {
            "plan_0001_t00": {"pass_rate": 0.90, "status": "success", "exit_code": 0, "report_path": "r/r.json", "error": "", "duration_seconds": 2.0},
        }
        source = FixtureValidationSource(task_results=task_results, default_pass_rate=0.40)
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=source, _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        # t00=0.90, t01=0.40 → avg=0.65
        assert batch.avg_pass_rate == pytest.approx(0.65, abs=1e-3)

    def test_fixture_error_result(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=1)
        task_results = {
            "plan_0001_t00": {"status": "error", "exit_code": 1, "pass_rate": None, "report_path": "", "error": "timeout", "duration_seconds": 0.5},
        }
        source = FixtureValidationSource(task_results=task_results)
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=source, _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.error_tasks == 1
        assert batch.completed_tasks == 0


# ---------------------------------------------------------------------------
# High overfitting risk block
# ---------------------------------------------------------------------------

class TestHighOverfittingRiskBlock:
    def test_high_risk_blocked_by_default(self, tmp_path: Path) -> None:
        plan = _make_plan(overfitting_level="high")
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=_fixture_source(), _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.stop_triggered is True
        assert batch.completed_tasks == 0

    def test_high_risk_blocked_status_on_all_tasks(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=3, overfitting_level="high")
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=_fixture_source(), _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.blocked_tasks == 3

    def test_high_risk_allowed_with_override(self, tmp_path: Path) -> None:
        plan = _make_plan(overfitting_level="high")
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, allow_high_risk=True,
            _source=_fixture_source(), _clock=_fixed_clock,
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.blocked_tasks == 0
        assert batch.completed_tasks == len(plan.tasks)

    def test_low_risk_not_blocked(self, tmp_path: Path) -> None:
        plan = _make_plan(overfitting_level="low")
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=_fixture_source(), _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.blocked_tasks == 0

    def test_medium_risk_not_blocked(self, tmp_path: Path) -> None:
        plan = _make_plan(overfitting_level="medium")
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=_fixture_source(), _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.blocked_tasks == 0

    def test_block_reason_in_stop_reason(self, tmp_path: Path) -> None:
        plan = _make_plan(overfitting_level="high")
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=_fixture_source(), _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert "high overfitting_risk" in batch.stop_reason.lower() or "blocked" in batch.stop_reason.lower()


# ---------------------------------------------------------------------------
# Stop condition handling
# ---------------------------------------------------------------------------

class TestStopConditions:
    def test_max_experiments_stops_early(self, tmp_path: Path) -> None:
        # plan has 3 tasks but max_experiments=1 → only 1 runs
        plan = _make_plan(n_tasks=3, stop_max_experiments=1.0)
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=_fixture_source(), _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.completed_tasks == 1
        assert batch.stop_triggered is True

    def test_max_experiments_stop_reason_mentions_count(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=3, stop_max_experiments=1.0)
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=_fixture_source(), _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert "max_experiments" in batch.stop_reason

    def test_min_pass_rate_stops_if_below_threshold(self, tmp_path: Path) -> None:
        # pass_rate=0.20 < threshold=0.50 → should stop after 1st task
        plan = _make_plan(n_tasks=3, stop_max_experiments=10.0, stop_min_pass_rate=0.50)
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True,
            _source=FixtureValidationSource(default_pass_rate=0.20),
            _clock=_fixed_clock,
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.stop_triggered is True
        # First task runs, then stop fires before second task
        assert batch.completed_tasks == 1

    def test_min_pass_rate_not_triggered_if_above_threshold(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=3, stop_max_experiments=10.0, stop_min_pass_rate=0.50)
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True,
            _source=FixtureValidationSource(default_pass_rate=0.80),
            _clock=_fixed_clock,
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.stop_triggered is False
        assert batch.completed_tasks == 3

    def test_no_stop_if_all_tasks_fit(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=2, stop_max_experiments=10.0)
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True, _source=_fixture_source(), _clock=_fixed_clock
        )
        batch: ValidationBatchResult = result.output  # type: ignore[assignment]
        assert batch.stop_triggered is False
        assert batch.completed_tasks == 2

    def test_check_stop_conditions_helper_max_experiments(self) -> None:
        scs = (StopCondition("max_experiments", 2.0, "stop after 2"),)
        results = [
            ValidationTaskResult("t0", "H-13", "ds", "success", 0, 0.65, "r", "", 1.0),
            ValidationTaskResult("t1", "H-13", "ds", "success", 0, 0.70, "r", "", 1.0),
        ]
        triggered, reason = _check_stop_conditions(scs, results)
        assert triggered is True
        assert "max_experiments" in reason

    def test_check_stop_conditions_helper_min_pass_rate(self) -> None:
        scs = (StopCondition("min_pass_rate", 0.5, "min 50%"),)
        results = [
            ValidationTaskResult("t0", "H-13", "ds", "success", 0, 0.20, "r", "", 1.0),
        ]
        triggered, reason = _check_stop_conditions(scs, results)
        assert triggered is True
        assert "min_pass_rate" in reason


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------

class TestResultPersistence:
    def _run(self, tmp_path: Path, execute: bool = False, n_tasks: int = 2) -> ValidationBatchResult:
        plan = _make_plan(n_tasks=n_tasks)
        source = _fixture_source() if execute else None
        result = ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=execute,
            _source=source, _clock=_fixed_clock,
        )
        return result.output  # type: ignore[return-value]

    def test_validation_run_json_created(self, tmp_path: Path) -> None:
        batch = self._run(tmp_path)
        run_path = Path(batch.validation_run_path)
        assert run_path.exists()

    def test_validation_run_dir_is_inside_research_programs(self, tmp_path: Path) -> None:
        batch = self._run(tmp_path)
        assert "research_programs" in batch.validation_run_path
        assert "validation_runs" in batch.validation_run_path

    def test_json_contains_run_id(self, tmp_path: Path) -> None:
        batch = self._run(tmp_path)
        with open(batch.validation_run_path) as fp:
            data = json.load(fp)
        assert "run_id" in data
        assert data["run_id"] == data["run_id"]  # non-empty

    def test_json_contains_plan_id(self, tmp_path: Path) -> None:
        batch = self._run(tmp_path)
        with open(batch.validation_run_path) as fp:
            data = json.load(fp)
        assert data["plan_id"] == "plan_0001_explore_h13"

    def test_json_task_results_is_list(self, tmp_path: Path) -> None:
        batch = self._run(tmp_path)
        with open(batch.validation_run_path) as fp:
            data = json.load(fp)
        assert isinstance(data["task_results"], list)
        assert len(data["task_results"]) == 2

    def test_json_mode_dry_run(self, tmp_path: Path) -> None:
        batch = self._run(tmp_path, execute=False)
        with open(batch.validation_run_path) as fp:
            data = json.load(fp)
        assert data["mode"] == "dry_run"

    def test_json_mode_fixture(self, tmp_path: Path) -> None:
        batch = self._run(tmp_path, execute=True)
        with open(batch.validation_run_path) as fp:
            data = json.load(fp)
        assert data["mode"] == "fixture"

    def test_second_run_overwrites_file(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=1)
        adapter = ValidationAgentAdapter(tmp_path)
        r1 = adapter.run(plan, _DATASETS, execute=False, _clock=_fixed_clock)
        r2 = adapter.run(plan, _DATASETS, execute=False, _clock=_fixed_clock)
        b1: ValidationBatchResult = r1.output  # type: ignore[assignment]
        b2: ValidationBatchResult = r2.output  # type: ignore[assignment]
        # Same run_id (same clock) → same path → overwritten
        assert b1.validation_run_path == b2.validation_run_path

    def test_path_outside_project_not_modified(self, tmp_path: Path) -> None:
        batch = self._run(tmp_path)
        run_path = Path(batch.validation_run_path)
        assert str(run_path).startswith(str(tmp_path.resolve()))


# ---------------------------------------------------------------------------
# AgentResult compliance
# ---------------------------------------------------------------------------

class TestAgentResultCompliance:
    def _result(self, tmp_path: Path) -> AgentResult:
        plan = _make_plan()
        return ValidationAgentAdapter(tmp_path).run(
            plan, _DATASETS, execute=True,
            _source=_fixture_source(), _clock=_fixed_clock,
        )

    def test_agent_id_in_result(self, tmp_path: Path) -> None:
        assert self._result(tmp_path).agent_id == "validation-agent-adapter"

    def test_agent_type_in_result(self, tmp_path: Path) -> None:
        assert self._result(tmp_path).agent_type == "RESEARCH"

    def test_created_at_from_clock(self, tmp_path: Path) -> None:
        assert self._result(tmp_path).created_at == "2026-06-27T12:00:00"

    def test_evidence_references_plan(self, tmp_path: Path) -> None:
        result = self._result(tmp_path)
        assert any("plan" in e.source for e in result.evidence)

    def test_confidence_in_valid_range(self, tmp_path: Path) -> None:
        result = self._result(tmp_path)
        assert 0.0 <= result.confidence.value <= 1.0

    def test_input_summary_contains_plan_id(self, tmp_path: Path) -> None:
        result = self._result(tmp_path)
        assert "plan_0001" in result.input_summary


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_run_id(self, tmp_path: Path) -> None:
        plan = _make_plan()
        adapter = ValidationAgentAdapter(tmp_path)
        r1 = adapter.run(plan, _DATASETS, execute=False, _clock=_fixed_clock)
        r2 = adapter.run(plan, _DATASETS, execute=False, _clock=_fixed_clock)
        b1: ValidationBatchResult = r1.output  # type: ignore[assignment]
        b2: ValidationBatchResult = r2.output  # type: ignore[assignment]
        assert b1.validation_run_path == b2.validation_run_path

    def test_different_clocks_different_run_ids(self, tmp_path: Path) -> None:
        plan = _make_plan()
        adapter = ValidationAgentAdapter(tmp_path)
        r1 = adapter.run(plan, _DATASETS, execute=False, _clock=lambda: datetime(2026, 1, 1, 0, 0, 0))
        r2 = adapter.run(plan, _DATASETS, execute=False, _clock=lambda: datetime(2026, 2, 2, 0, 0, 0))
        b1: ValidationBatchResult = r1.output  # type: ignore[assignment]
        b2: ValidationBatchResult = r2.output  # type: ignore[assignment]
        assert b1.validation_run_path != b2.validation_run_path

    def test_dry_run_task_count_deterministic(self, tmp_path: Path) -> None:
        plan = _make_plan(n_tasks=3)
        adapter = ValidationAgentAdapter(tmp_path)
        for _ in range(3):
            result = adapter.run(plan, _DATASETS, execute=False, _clock=_fixed_clock)
            batch: ValidationBatchResult = result.output  # type: ignore[assignment]
            assert batch.dry_run_tasks == 3


# ---------------------------------------------------------------------------
# FixtureValidationSource unit tests
# ---------------------------------------------------------------------------

class TestFixtureValidationSource:
    def test_dataset_exists_default(self) -> None:
        src = FixtureValidationSource()
        assert src.dataset_exists("any_dataset") is True

    def test_dataset_missing_when_listed(self) -> None:
        src = FixtureValidationSource(missing_datasets=["bad_ds"])
        assert src.dataset_exists("bad_ds") is False

    def test_run_task_dry_run(self) -> None:
        src = FixtureValidationSource()
        task = ExperimentTask("t0", "H-13", "SBER", "sber_ds", "", ())
        result = src.run_task(task, dry_run=True)
        assert result.status == "dry_run"

    def test_run_task_fixture_success(self) -> None:
        src = FixtureValidationSource(default_pass_rate=0.75)
        task = ExperimentTask("t0", "H-13", "SBER", "sber_ds", "", ())
        result = src.run_task(task, dry_run=False)
        assert result.status == "success"
        assert result.pass_rate == pytest.approx(0.75)

    def test_run_task_fixture_per_task_override(self) -> None:
        src = FixtureValidationSource(
            task_results={"t0": {"pass_rate": 0.99, "status": "success", "exit_code": 0, "report_path": "r", "error": "", "duration_seconds": 1.0}},
            default_pass_rate=0.50,
        )
        task = ExperimentTask("t0", "H-13", "SBER", "sber_ds", "", ())
        result = src.run_task(task, dry_run=False)
        assert result.pass_rate == pytest.approx(0.99)
