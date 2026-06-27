from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator
from uuid import uuid4

import pytest

from core.experiment.models import ExperimentConfig, ExperimentResult, ExperimentStage
from core.hypothesis.models import HypothesisStatus
from core.hypothesis.service import HypothesisRegistry
from core.knowledge.models import KnowledgeEntry, KnowledgeType
from core.research_orchestrator.models import (
    OrchestrationStatus,
    ResearchPlan,
    ResearchTask,
    ResearchTaskStatus,
)
from core.research_orchestrator.orchestrator import ResearchOrchestrator
from core.research_orchestrator.policy import DefaultResearchPolicy
from core.research_pipeline.pipeline import ResearchPipelineResult
from core.validation.models import ValidationReport, ValidationStatus


# ── helpers ───────────────────────────────────────────────────────────────────


def _fixed_clock(ts: datetime) -> Iterator[datetime]:
    """Yields the same timestamp repeatedly."""
    while True:
        yield ts


def _make_clock(ts: datetime | None = None):
    dt = ts or datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ticks = _fixed_clock(dt)
    return lambda: next(ticks)


def _config(hypothesis_id: str = "h1") -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id=f"exp_{uuid4().hex[:6]}",
        hypothesis_id=hypothesis_id,
        dataset_id="ds_1",
        strategy_name="strat",
        feature_set=[],
    )


def _pipeline_result(
    hypothesis_id: str,
    pass_rate: float = 0.9,
    windows_total: int = 10,
    entry_id: str | None = None,
) -> ResearchPipelineResult:
    eid = entry_id or uuid4().hex
    cfg = _config(hypothesis_id)
    validation = ValidationReport(
        status=ValidationStatus.PASS if pass_rate >= 0.8 else ValidationStatus.FAIL,
        metrics=[],
        windows_total=windows_total,
        windows_passed=int(windows_total * pass_rate),
        windows_failed=windows_total - int(windows_total * pass_rate),
        pass_rate=pass_rate,
    )
    experiment_result = ExperimentResult(
        config=cfg,
        stage=ExperimentStage.VALIDATED,
        validation=validation,
    )
    knowledge_entry = KnowledgeEntry(
        id=eid,
        knowledge_type=KnowledgeType.EXPERIMENT,
        reference_id=hypothesis_id,
        summary="test",
        tags=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return ResearchPipelineResult(
        hypothesis_id=hypothesis_id,
        experiment_result=experiment_result,
        knowledge_entry=knowledge_entry,
    )


class _StubPipeline:
    """Test double for ResearchPipeline."""

    def __init__(
        self,
        result: ResearchPipelineResult | None = None,
        raise_exc: Exception | None = None,
        results: list[ResearchPipelineResult] | None = None,
    ) -> None:
        self._result = result
        self._raise = raise_exc
        self._iter = iter(results) if results is not None else None
        self.call_count = 0
        self.last_hypothesis = None

    def run(self, hypothesis, config):
        self.call_count += 1
        self.last_hypothesis = hypothesis
        if self._raise is not None:
            raise self._raise
        if self._iter is not None:
            return next(self._iter)
        return self._result


def _registry_with_hypothesis(
    status: HypothesisStatus = HypothesisStatus.IDEA,
) -> tuple[HypothesisRegistry, str]:
    registry = HypothesisRegistry()
    h = registry.create("Test Hypothesis", "Some statement")
    # Advance to the desired starting status
    pipeline = [
        HypothesisStatus.DRAFT,
        HypothesisStatus.RESEARCH,
        HypothesisStatus.BACKTEST,
        HypothesisStatus.WALKFORWARD,
        HypothesisStatus.PAPER_TRADING,
        HypothesisStatus.PRODUCTION,
    ]
    for step in pipeline:
        if h.status == status:
            break
        registry.move_to(h.id, step)
        if step == status:
            break
    return registry, h.id


# ── empty plan ────────────────────────────────────────────────────────────────


def test_empty_plan_returns_completed_result() -> None:
    orchestrator = ResearchOrchestrator(_clock=_make_clock())
    registry = HypothesisRegistry()
    pipeline = _StubPipeline()
    plan = ResearchPlan(tasks=())
    result = orchestrator.run(plan, registry, pipeline)
    assert result.final_status == OrchestrationStatus.COMPLETED
    assert result.completed_tasks == ()
    assert result.failed_tasks == ()
    assert result.skipped_tasks == ()


def test_empty_plan_session_id_is_non_empty() -> None:
    orchestrator = ResearchOrchestrator(_clock=_make_clock())
    result = orchestrator.run(
        ResearchPlan(tasks=()), HypothesisRegistry(), _StubPipeline()
    )
    assert result.session_id
    assert isinstance(result.session_id, str)


# ── happy path: IDEA hypothesis ───────────────────────────────────────────────


def test_idea_hypothesis_task_completes() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline(result=_pipeline_result(hid))
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    result = orchestrator.run(plan, registry, pipeline)

    assert result.final_status == OrchestrationStatus.COMPLETED
    assert len(result.completed_tasks) == 1
    assert task.status == ResearchTaskStatus.COMPLETED


def test_idea_hypothesis_advanced_through_draft_to_research() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline(result=_pipeline_result(hid))
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    orchestrator.run(plan, registry, pipeline)

    # Hypothesis must be in RESEARCH status after orchestration
    h = registry.get(hid)
    assert h.status == HypothesisStatus.RESEARCH


def test_draft_hypothesis_advanced_to_research() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.DRAFT)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline(result=_pipeline_result(hid))
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    orchestrator.run(plan, registry, pipeline)

    h = registry.get(hid)
    assert h.status == HypothesisStatus.RESEARCH


# ── pipeline is called with the advanced hypothesis ───────────────────────────


def test_pipeline_receives_hypothesis_in_research_status() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline(result=_pipeline_result(hid))
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    orchestrator.run(plan, registry, pipeline)

    assert pipeline.last_hypothesis.status == HypothesisStatus.RESEARCH


# ── validation FAIL is still COMPLETED (not a pipeline error) ─────────────────


def test_validation_fail_task_is_completed_not_failed() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    low_pass_result = _pipeline_result(hid, pass_rate=0.2, windows_total=10)
    pipeline = _StubPipeline(result=low_pass_result)
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    result = orchestrator.run(plan, registry, pipeline)

    assert task.status == ResearchTaskStatus.COMPLETED
    assert result.final_status == OrchestrationStatus.COMPLETED
    assert task.summary is not None
    assert task.summary.pass_rate == pytest.approx(0.2)


# ── pipeline exception → FAILED task ─────────────────────────────────────────


def test_pipeline_exception_marks_task_failed() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline(raise_exc=RuntimeError("data unavailable"))
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    result = orchestrator.run(plan, registry, pipeline)

    assert task.status == ResearchTaskStatus.FAILED
    assert task.failure_reason == "data unavailable"
    assert len(result.failed_tasks) == 1


def test_pipeline_exception_below_threshold_session_still_completed() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline(raise_exc=RuntimeError("err"))
    orchestrator = ResearchOrchestrator(_clock=_make_clock())
    policy = DefaultResearchPolicy(max_consecutive_failures=3)

    result = orchestrator.run(plan, registry, pipeline, policy=policy)

    assert result.final_status == OrchestrationStatus.COMPLETED


# ── ABORT on consecutive failures ─────────────────────────────────────────────


def test_abort_after_max_consecutive_failures() -> None:
    registry = HypothesisRegistry()
    h1 = registry.create("H1", "stmt")
    h2 = registry.create("H2", "stmt")

    t1 = ResearchTask(hypothesis_id=h1.id, experiment_config=_config(h1.id))
    t2 = ResearchTask(hypothesis_id=h2.id, experiment_config=_config(h2.id))
    plan = ResearchPlan(tasks=(t1, t2))
    pipeline = _StubPipeline(raise_exc=RuntimeError("crash"))
    policy = DefaultResearchPolicy(max_consecutive_failures=1)
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    result = orchestrator.run(plan, registry, pipeline, policy=policy)

    assert result.final_status == OrchestrationStatus.ABORTED
    assert t1.status == ResearchTaskStatus.FAILED
    assert t2.status == ResearchTaskStatus.SKIPPED


def test_consecutive_failures_reset_after_success() -> None:
    registry = HypothesisRegistry()
    h1 = registry.create("H1", "stmt")
    h2 = registry.create("H2", "stmt")
    h3 = registry.create("H3", "stmt")

    t1 = ResearchTask(hypothesis_id=h1.id, experiment_config=_config(h1.id))
    t2 = ResearchTask(hypothesis_id=h2.id, experiment_config=_config(h2.id))
    t3 = ResearchTask(hypothesis_id=h3.id, experiment_config=_config(h3.id))
    plan = ResearchPlan(tasks=(t1, t2, t3))

    # t1 fails, t2 succeeds (resets counter), t3 fails — no abort with max=2
    pipeline = _StubPipeline(
        results=[
            None,  # t1: will raise instead — handled below
            _pipeline_result(h2.id),
            None,  # t3: will raise
        ]
    )

    call_n = [0]
    original_run = pipeline.run

    def run_with_selective_failure(hypothesis, config):
        call_n[0] += 1
        if call_n[0] in (1, 3):
            raise RuntimeError("fail")
        return _pipeline_result(hypothesis.id)

    pipeline.run = run_with_selective_failure

    policy = DefaultResearchPolicy(max_consecutive_failures=2)
    orchestrator = ResearchOrchestrator(_clock=_make_clock())
    result = orchestrator.run(plan, registry, pipeline, policy=policy)

    assert t1.status == ResearchTaskStatus.FAILED
    assert t2.status == ResearchTaskStatus.COMPLETED
    assert t3.status == ResearchTaskStatus.FAILED
    assert result.final_status == OrchestrationStatus.COMPLETED  # counter reset at t2


# ── skip scenarios ────────────────────────────────────────────────────────────


def test_hypothesis_already_in_research_is_skipped() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.RESEARCH)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline()
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    result = orchestrator.run(plan, registry, pipeline)

    assert task.status == ResearchTaskStatus.SKIPPED
    assert pipeline.call_count == 0
    assert len(result.skipped_tasks) == 1


def test_hypothesis_not_found_in_registry_is_skipped() -> None:
    registry = HypothesisRegistry()
    task = ResearchTask(hypothesis_id="nonexistent_id", experiment_config=_config())
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline()
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    result = orchestrator.run(plan, registry, pipeline)

    assert task.status == ResearchTaskStatus.SKIPPED
    assert pipeline.call_count == 0


# ── multi-task plan ───────────────────────────────────────────────────────────


def test_three_tasks_all_complete() -> None:
    registry = HypothesisRegistry()
    ids = [registry.create(f"H{i}", "stmt").id for i in range(3)]
    tasks = [
        ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
        for hid in ids
    ]
    plan = ResearchPlan(tasks=tuple(tasks))
    pipeline = _StubPipeline(
        results=[_pipeline_result(hid) for hid in ids]
    )
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    result = orchestrator.run(plan, registry, pipeline)

    assert result.final_status == OrchestrationStatus.COMPLETED
    assert len(result.completed_tasks) == 3
    assert all(t.status == ResearchTaskStatus.COMPLETED for t in tasks)


# ── summary fields ────────────────────────────────────────────────────────────


def test_task_summary_knowledge_entry_id_matches() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    fixed_entry_id = "entry_xyz"
    pipeline = _StubPipeline(
        result=_pipeline_result(hid, entry_id=fixed_entry_id)
    )
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    orchestrator.run(plan, registry, pipeline)

    assert task.summary is not None
    assert task.summary.knowledge_entry_id == fixed_entry_id


def test_task_summary_pass_rate_matches() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline(result=_pipeline_result(hid, pass_rate=0.85))
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    orchestrator.run(plan, registry, pipeline)

    assert task.summary is not None
    assert task.summary.pass_rate == pytest.approx(0.85)


def test_task_summary_windows_total_matches() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline(result=_pipeline_result(hid, windows_total=12))
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    orchestrator.run(plan, registry, pipeline)

    assert task.summary is not None
    assert task.summary.windows_total == 12


# ── OrchestrationResult structure ─────────────────────────────────────────────


def test_orchestration_result_plan_matches_input() -> None:
    registry, hid = _registry_with_hypothesis(HypothesisStatus.IDEA)
    task = ResearchTask(hypothesis_id=hid, experiment_config=_config(hid))
    plan = ResearchPlan(tasks=(task,))
    pipeline = _StubPipeline(result=_pipeline_result(hid))
    orchestrator = ResearchOrchestrator(_clock=_make_clock())

    result = orchestrator.run(plan, registry, pipeline)

    assert result.plan is plan


def test_started_at_is_set() -> None:
    ts = datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
    orchestrator = ResearchOrchestrator(_clock=_make_clock(ts))
    result = orchestrator.run(ResearchPlan(tasks=()), HypothesisRegistry(), _StubPipeline())
    assert result.started_at == ts


def test_finished_at_is_set() -> None:
    orchestrator = ResearchOrchestrator(_clock=_make_clock())
    result = orchestrator.run(ResearchPlan(tasks=()), HypothesisRegistry(), _StubPipeline())
    assert result.finished_at is not None
