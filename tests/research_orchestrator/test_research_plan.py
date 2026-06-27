from __future__ import annotations

import pytest

from core.experiment.models import ExperimentConfig
from core.research_orchestrator.models import ResearchPlan, ResearchTask


def _config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="exp_1",
        hypothesis_id="h1",
        dataset_id="ds_1",
        strategy_name="strat",
        feature_set=[],
    )


def _task() -> ResearchTask:
    return ResearchTask(hypothesis_id="h1", experiment_config=_config())


# ── plan_id ───────────────────────────────────────────────────────────────────


def test_plan_id_is_generated() -> None:
    plan = ResearchPlan(tasks=())
    assert plan.plan_id
    assert isinstance(plan.plan_id, str)


def test_two_plans_have_different_ids() -> None:
    p1 = ResearchPlan(tasks=())
    p2 = ResearchPlan(tasks=())
    assert p1.plan_id != p2.plan_id


# ── tasks ─────────────────────────────────────────────────────────────────────


def test_tasks_stored_correctly() -> None:
    t1, t2 = _task(), _task()
    plan = ResearchPlan(tasks=(t1, t2))
    assert plan.tasks == (t1, t2)


def test_non_tuple_tasks_raises() -> None:
    with pytest.raises(ValueError, match="tuple"):
        ResearchPlan(tasks=[_task()])  # type: ignore[arg-type]


def test_empty_plan_is_valid() -> None:
    plan = ResearchPlan(tasks=())
    assert len(plan.tasks) == 0


# ── description ───────────────────────────────────────────────────────────────


def test_description_defaults_to_empty_string() -> None:
    plan = ResearchPlan(tasks=())
    assert plan.description == ""


def test_description_stored_when_provided() -> None:
    plan = ResearchPlan(tasks=(), description="Phase 4 batch")
    assert plan.description == "Phase 4 batch"
