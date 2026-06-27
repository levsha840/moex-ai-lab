from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.experiment.models import ExperimentConfig
from core.research_orchestrator.models import (
    ResearchTask,
    ResearchTaskStatus,
    ResearchTaskSummary,
)


def _config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="exp_1",
        hypothesis_id="hyp_1",
        dataset_id="ds_1",
        strategy_name="strat",
        feature_set=[],
    )


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _summary() -> ResearchTaskSummary:
    return ResearchTaskSummary(
        knowledge_entry_id="entry_abc",
        pass_rate=0.9,
        windows_total=10,
    )


# ── task_id ──────────────────────────────────────────────────────────────────


def test_task_id_is_generated() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    assert task.task_id
    assert isinstance(task.task_id, str)


def test_two_tasks_have_different_ids() -> None:
    t1 = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    t2 = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    assert t1.task_id != t2.task_id


# ── initial state ─────────────────────────────────────────────────────────────


def test_default_status_is_pending() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    assert task.status == ResearchTaskStatus.PENDING


def test_initial_timestamps_are_none() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    assert task.started_at is None
    assert task.completed_at is None


# ── mark_in_progress ──────────────────────────────────────────────────────────


def test_mark_in_progress_sets_status_and_timestamp() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    now = _now()
    task.mark_in_progress(now)
    assert task.status == ResearchTaskStatus.IN_PROGRESS
    assert task.started_at == now


def test_mark_in_progress_from_non_pending_raises() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    task.mark_in_progress(_now())
    with pytest.raises(ValueError, match="IN_PROGRESS"):
        task.mark_in_progress(_now())


# ── mark_completed ────────────────────────────────────────────────────────────


def test_mark_completed_sets_status_summary_and_timestamp() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    task.mark_in_progress(_now())
    summary = _summary()
    task.mark_completed(summary, _now())
    assert task.status == ResearchTaskStatus.COMPLETED
    assert task.summary == summary
    assert task.completed_at is not None


def test_mark_completed_from_non_in_progress_raises() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    with pytest.raises(ValueError, match="IN_PROGRESS"):
        task.mark_completed(_summary(), _now())


# ── mark_failed ───────────────────────────────────────────────────────────────


def test_mark_failed_sets_status_reason_and_timestamp() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    task.mark_in_progress(_now())
    task.mark_failed("data error", _now())
    assert task.status == ResearchTaskStatus.FAILED
    assert task.failure_reason == "data error"
    assert task.completed_at is not None


def test_mark_failed_from_non_in_progress_raises() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    with pytest.raises(ValueError, match="IN_PROGRESS"):
        task.mark_failed("reason", _now())


# ── mark_skipped ──────────────────────────────────────────────────────────────


def test_mark_skipped_sets_status() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    task.mark_skipped()
    assert task.status == ResearchTaskStatus.SKIPPED


def test_mark_skipped_from_non_pending_raises() -> None:
    task = ResearchTask(hypothesis_id="h1", experiment_config=_config())
    task.mark_in_progress(_now())
    with pytest.raises(ValueError, match="PENDING"):
        task.mark_skipped()
