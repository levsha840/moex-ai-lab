"""Tests for ResearchSession."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from core.experiment.models import ExperimentConfig
from core.hypothesis.models import Hypothesis, HypothesisStatus
from core.hypothesis_generator.models import (
    GenerationConfig,
    GenerationSession,
    HypothesisCandidate,
)
from core.research_orchestrator.models import (
    OrchestrationResult,
    OrchestrationStatus,
    ResearchPlan,
    ResearchTask,
    ResearchTaskSummary,
)
from core.research_session.models import ResearchSessionConfig, ResearchSessionStatus
from core.research_session.session import ResearchSession


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_TS = datetime(2026, 1, 1, 12, 0, 0)
_TS2 = datetime(2026, 1, 1, 12, 0, 5)

_EXP_CONFIG = ExperimentConfig(
    experiment_id="exp_test",
    hypothesis_id="hyp_test",
    dataset_id="dataset_h13",
    strategy_name="adx_continuation",
    feature_set=["adx", "rsi"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Stubs
# ─────────────────────────────────────────────────────────────────────────────

class _StubGenerator:
    def __init__(
        self,
        candidates: list[HypothesisCandidate] | None = None,
        hypotheses: list[Hypothesis] | None = None,
        raise_on_generate: Exception | None = None,
        raise_on_accept_all: Exception | None = None,
    ) -> None:
        self._candidates = candidates or []
        self._hypotheses = hypotheses or []
        self._raise_generate = raise_on_generate
        self._raise_accept_all = raise_on_accept_all
        self.generate_calls: list = []
        self.accept_all_calls: list = []

    def generate(self, config: GenerationConfig) -> GenerationSession:
        self.generate_calls.append(config)
        if self._raise_generate:
            raise self._raise_generate
        return GenerationSession(
            session_id=uuid4().hex,
            created_at=_TS,
            config=config,
            generated_candidates=tuple(self._candidates),
        )

    def accept_all(self, session: GenerationSession, registry) -> list[Hypothesis]:
        self.accept_all_calls.append((session, registry))
        if self._raise_accept_all:
            raise self._raise_accept_all
        return list(self._hypotheses)


class _StubExecutor:
    def __init__(
        self,
        result: OrchestrationResult | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._result = result
        self._raise_exc = raise_exc
        self.calls: list = []

    def run(self, plan, registry, pipeline, *, policy=None) -> OrchestrationResult:
        self.calls.append({"plan": plan, "registry": registry, "pipeline": pipeline, "policy": policy})
        if self._raise_exc:
            raise self._raise_exc
        return self._result or _empty_orch_result()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hypothesis(hypothesis_id: str | None = None) -> Hypothesis:
    return Hypothesis(
        id=hypothesis_id or uuid4().hex,
        title="ADX Continuation on SBER",
        statement="When ADX > 25 in TREND_UP, continuation probability exceeds 60%.",
        status=HypothesisStatus.IDEA,
        created_at=_TS,
        updated_at=_TS,
        metadata={"template_id": "tmpl_h13"},
    )


def _candidate() -> HypothesisCandidate:
    return HypothesisCandidate(
        candidate_id=uuid4().hex,
        template_id="tmpl_h13",
        title="ADX Continuation on SBER",
        statement="Statement.",
        parameters={},
        score=1.0,
        rationale="Priority A",
        created_at=_TS,
    )


def _session_config(description: str = "Test campaign") -> ResearchSessionConfig:
    return ResearchSessionConfig(
        generation_config=GenerationConfig(max_candidates=5),
        experiment_config=_EXP_CONFIG,
        description=description,
    )


def _empty_orch_result(
    completed: tuple[ResearchTask, ...] = (),
    failed: tuple[ResearchTask, ...] = (),
    skipped: tuple[ResearchTask, ...] = (),
    final_status: OrchestrationStatus = OrchestrationStatus.COMPLETED,
) -> OrchestrationResult:
    return OrchestrationResult(
        session_id=uuid4().hex,
        plan=ResearchPlan(tasks=()),
        completed_tasks=completed,
        failed_tasks=failed,
        skipped_tasks=skipped,
        started_at=_TS,
        finished_at=_TS,
        final_status=final_status,
    )


def _completed_task(pass_rate: float | None = 0.9, windows_total: int = 10) -> ResearchTask:
    task = ResearchTask(hypothesis_id=uuid4().hex, experiment_config=_EXP_CONFIG)
    task.mark_in_progress(_TS)
    task.mark_completed(
        ResearchTaskSummary(
            knowledge_entry_id=uuid4().hex,
            pass_rate=pass_rate,
            windows_total=windows_total,
        ),
        _TS,
    )
    return task


def _failed_task() -> ResearchTask:
    task = ResearchTask(hypothesis_id=uuid4().hex, experiment_config=_EXP_CONFIG)
    task.mark_in_progress(_TS)
    task.mark_failed("Pipeline error", _TS)
    return task


def _skipped_task() -> ResearchTask:
    task = ResearchTask(hypothesis_id=uuid4().hex, experiment_config=_EXP_CONFIG)
    task.mark_skipped()
    return task


def _session(
    candidates: list[HypothesisCandidate] | None = None,
    hypotheses: list[Hypothesis] | None = None,
    orch_result: OrchestrationResult | None = None,
    clock=None,
) -> tuple[ResearchSession, _StubGenerator, _StubExecutor]:
    gen = _StubGenerator(candidates=candidates, hypotheses=hypotheses)
    executor = _StubExecutor(result=orch_result)
    sess = ResearchSession(gen, executor, _clock=clock)
    return sess, gen, executor


_STUB_REGISTRY = object()
_STUB_PIPELINE = object()


# ─────────────────────────────────────────────────────────────────────────────
# Basic flow / Status
# ─────────────────────────────────────────────────────────────────────────────

def test_empty_generation_returns_completed_with_zero_stats():
    sess, _, _ = _session(candidates=[], hypotheses=[])
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.status == ResearchSessionStatus.COMPLETED
    s = result.statistics
    assert s.candidates_generated == 0
    assert s.hypotheses_accepted == 0
    assert s.tasks_completed == 0
    assert s.tasks_failed == 0
    assert s.tasks_skipped == 0


def test_single_hypothesis_completed_pass():
    orch = _empty_orch_result(completed=(_completed_task(pass_rate=0.9),))
    sess, _, _ = _session(
        candidates=[_candidate()],
        hypotheses=[_hypothesis()],
        orch_result=orch,
    )
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.status == ResearchSessionStatus.COMPLETED
    assert result.statistics.validation_pass == 1
    assert result.statistics.validation_fail == 0


def test_session_status_aborted_from_orchestrator_aborted():
    orch = _empty_orch_result(
        skipped=(_skipped_task(),),
        final_status=OrchestrationStatus.ABORTED,
    )
    sess, _, _ = _session(hypotheses=[_hypothesis()], orch_result=orch)
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.status == ResearchSessionStatus.ABORTED


def test_all_fail_pipeline_session_still_completed():
    orch = _empty_orch_result(failed=(_failed_task(), _failed_task()))
    sess, _, _ = _session(
        hypotheses=[_hypothesis(), _hypothesis()],
        orch_result=orch,
    )
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.status == ResearchSessionStatus.COMPLETED
    assert result.statistics.tasks_failed == 2
    assert result.statistics.tasks_completed == 0


# ─────────────────────────────────────────────────────────────────────────────
# Delegation: generate → accept_all → plan → executor
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_called_with_generation_config():
    config = _session_config()
    sess, gen, _ = _session()
    sess.run(config, _STUB_REGISTRY, _STUB_PIPELINE)
    assert len(gen.generate_calls) == 1
    assert gen.generate_calls[0] is config.generation_config


def test_accept_all_called_with_gen_session_and_registry():
    config = _session_config()
    registry = object()
    sess, gen, _ = _session(candidates=[_candidate()], hypotheses=[_hypothesis()])
    sess.run(config, registry, _STUB_PIPELINE)
    assert len(gen.accept_all_calls) == 1
    _, passed_registry = gen.accept_all_calls[0]
    assert passed_registry is registry


def test_plan_task_count_matches_accepted_hypotheses():
    hypotheses = [_hypothesis(), _hypothesis(), _hypothesis()]
    sess, _, executor = _session(hypotheses=hypotheses)
    sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert len(executor.calls) == 1
    plan = executor.calls[0]["plan"]
    assert len(plan.tasks) == 3


def test_plan_tasks_use_session_experiment_config():
    config = _session_config()
    h = _hypothesis(hypothesis_id="hyp_42")
    sess, _, executor = _session(hypotheses=[h])
    sess.run(config, _STUB_REGISTRY, _STUB_PIPELINE)
    plan = executor.calls[0]["plan"]
    assert plan.tasks[0].experiment_config is config.experiment_config


def test_plan_tasks_hypothesis_ids_from_accepted():
    h1 = _hypothesis(hypothesis_id="hyp_111")
    h2 = _hypothesis(hypothesis_id="hyp_222")
    sess, _, executor = _session(hypotheses=[h1, h2])
    sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    plan = executor.calls[0]["plan"]
    ids = [t.hypothesis_id for t in plan.tasks]
    assert ids == ["hyp_111", "hyp_222"]


def test_executor_receives_registry_and_pipeline():
    registry = object()
    pipeline = object()
    sess, _, executor = _session()
    sess.run(_session_config(), registry, pipeline)
    call = executor.calls[0]
    assert call["registry"] is registry
    assert call["pipeline"] is pipeline


def test_policy_forwarded_to_executor():
    policy = object()
    sess, _, executor = _session()
    sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE, policy=policy)
    assert executor.calls[0]["policy"] is policy


def test_plan_description_from_session_config():
    config = ResearchSessionConfig(
        generation_config=GenerationConfig(max_candidates=2),
        experiment_config=_EXP_CONFIG,
        description="Phase 4 campaign",
    )
    sess, _, executor = _session()
    sess.run(config, _STUB_REGISTRY, _STUB_PIPELINE)
    plan = executor.calls[0]["plan"]
    assert plan.description == "Phase 4 campaign"


# ─────────────────────────────────────────────────────────────────────────────
# Result content
# ─────────────────────────────────────────────────────────────────────────────

def test_result_contains_orchestration_result():
    orch = _empty_orch_result()
    sess, _, _ = _session(orch_result=orch)
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.orchestration_result is orch


def test_result_session_id_is_unique_per_call():
    sess, _, _ = _session()
    r1 = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    r2 = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert r1.session_id != r2.session_id


def test_result_config_preserved():
    config = _session_config("campaign alpha")
    sess, _, _ = _session()
    result = sess.run(config, _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.config is config


def test_result_started_at_not_after_finished_at():
    times = [_TS, _TS2]
    clock = iter(times).__next__
    sess, _, _ = _session(clock=clock)
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.started_at <= result.finished_at


# ─────────────────────────────────────────────────────────────────────────────
# Statistics aggregation
# ─────────────────────────────────────────────────────────────────────────────

def test_statistics_candidates_generated():
    candidates = [_candidate(), _candidate(), _candidate()]
    sess, _, _ = _session(candidates=candidates, hypotheses=[_hypothesis()] * 3)
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.statistics.candidates_generated == 3


def test_statistics_hypotheses_accepted():
    hypotheses = [_hypothesis(), _hypothesis()]
    sess, _, _ = _session(hypotheses=hypotheses)
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.statistics.hypotheses_accepted == 2


def test_statistics_tasks_completed():
    orch = _empty_orch_result(completed=(_completed_task(), _completed_task()))
    sess, _, _ = _session(orch_result=orch)
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.statistics.tasks_completed == 2


def test_statistics_tasks_failed():
    orch = _empty_orch_result(failed=(_failed_task(),))
    sess, _, _ = _session(orch_result=orch)
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.statistics.tasks_failed == 1


def test_statistics_tasks_skipped():
    orch = _empty_orch_result(skipped=(_skipped_task(), _skipped_task()))
    sess, _, _ = _session(orch_result=orch)
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.statistics.tasks_skipped == 2


def test_statistics_validation_pass_above_threshold():
    orch = _empty_orch_result(
        completed=(
            _completed_task(pass_rate=0.90),   # PASS
            _completed_task(pass_rate=0.80),   # PASS (exactly at threshold)
            _completed_task(pass_rate=0.75),   # FAIL
        )
    )
    sess, _, _ = _session(orch_result=orch)
    s = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE).statistics
    assert s.validation_pass == 2
    assert s.validation_fail == 1
    assert s.validation_inconclusive == 0


def test_statistics_validation_inconclusive_when_pass_rate_none():
    orch = _empty_orch_result(
        completed=(_completed_task(pass_rate=None),)
    )
    sess, _, _ = _session(orch_result=orch)
    s = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE).statistics
    assert s.validation_inconclusive == 1
    assert s.validation_pass == 0
    assert s.validation_fail == 0


def test_statistics_avg_pass_rate():
    orch = _empty_orch_result(
        completed=(
            _completed_task(pass_rate=0.9),
            _completed_task(pass_rate=0.7),
        )
    )
    sess, _, _ = _session(orch_result=orch)
    s = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE).statistics
    assert s.avg_pass_rate == pytest.approx(0.8)


def test_statistics_avg_pass_rate_none_when_all_inconclusive():
    orch = _empty_orch_result(completed=(_completed_task(pass_rate=None),))
    sess, _, _ = _session(orch_result=orch)
    s = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE).statistics
    assert s.avg_pass_rate is None


def test_statistics_kb_entries_created():
    orch = _empty_orch_result(
        completed=(_completed_task(), _completed_task()),
        failed=(_failed_task(),),
    )
    sess, _, _ = _session(orch_result=orch)
    s = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE).statistics
    # Only completed tasks have KB entries
    assert s.kb_entries_created == 2


def test_statistics_validation_pass_rate_property():
    orch = _empty_orch_result(
        completed=(
            _completed_task(pass_rate=0.9),
            _completed_task(pass_rate=0.9),
            _completed_task(pass_rate=0.5),
        )
    )
    sess, _, _ = _session(orch_result=orch)
    s = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE).statistics
    assert s.validation_pass == 2
    assert s.validation_fail == 1
    assert s.validation_pass_rate == pytest.approx(2 / 3)


# ─────────────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────────────

def test_generator_exception_propagates():
    gen = _StubGenerator(raise_on_generate=RuntimeError("generator failure"))
    sess = ResearchSession(gen, _StubExecutor())
    with pytest.raises(RuntimeError, match="generator failure"):
        sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)


def test_executor_exception_propagates():
    gen = _StubGenerator(hypotheses=[_hypothesis()])
    executor = _StubExecutor(raise_exc=RuntimeError("executor failure"))
    sess = ResearchSession(gen, executor)
    with pytest.raises(RuntimeError, match="executor failure"):
        sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)


# ─────────────────────────────────────────────────────────────────────────────
# Clock injection
# ─────────────────────────────────────────────────────────────────────────────

def test_clock_injection_controls_timestamps():
    call_count = 0
    times = [_TS, _TS2]

    def fixed_clock():
        nonlocal call_count
        t = times[min(call_count, len(times) - 1)]
        call_count += 1
        return t

    sess, _, _ = _session(clock=fixed_clock)
    result = sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    assert result.started_at == _TS
    assert result.finished_at == _TS2
    assert result.statistics.duration_seconds == pytest.approx(5.0)


# ─────────────────────────────────────────────────────────────────────────────
# Determinism
# ─────────────────────────────────────────────────────────────────────────────

def test_same_inputs_produce_same_statistics():
    orch = _empty_orch_result(
        completed=(_completed_task(pass_rate=0.9), _completed_task(pass_rate=0.7)),
        failed=(_failed_task(),),
    )
    config = _session_config()

    def make_session():
        gen = _StubGenerator(
            candidates=[_candidate(), _candidate()],
            hypotheses=[_hypothesis(), _hypothesis()],
        )
        return ResearchSession(gen, _StubExecutor(result=orch), _clock=lambda: _TS)

    r1 = make_session().run(config, _STUB_REGISTRY, _STUB_PIPELINE)
    r2 = make_session().run(config, _STUB_REGISTRY, _STUB_PIPELINE)

    assert r1.statistics.candidates_generated == r2.statistics.candidates_generated
    assert r1.statistics.hypotheses_accepted == r2.statistics.hypotheses_accepted
    assert r1.statistics.tasks_completed == r2.statistics.tasks_completed
    assert r1.statistics.tasks_failed == r2.statistics.tasks_failed
    assert r1.statistics.validation_pass == r2.statistics.validation_pass
    assert r1.statistics.avg_pass_rate == pytest.approx(r2.statistics.avg_pass_rate)
    # session_ids differ (uuid4) — correct per ADR-0006
    assert r1.session_id != r2.session_id


# ─────────────────────────────────────────────────────────────────────────────
# accept_all on HypothesisGenerator (direct unit test)
# ─────────────────────────────────────────────────────────────────────────────

def test_accept_all_called_once_not_per_candidate():
    """ResearchSession must call accept_all once (not a per-candidate loop)."""
    hypotheses = [_hypothesis(), _hypothesis(), _hypothesis()]
    sess, gen, _ = _session(
        candidates=[_candidate(), _candidate(), _candidate()],
        hypotheses=hypotheses,
    )
    sess.run(_session_config(), _STUB_REGISTRY, _STUB_PIPELINE)
    # Exactly one accept_all call, never individual accept() calls
    assert len(gen.accept_all_calls) == 1
