from __future__ import annotations

import pytest

from core.research_orchestrator.models import FailureAction
from core.research_orchestrator.policy import DefaultResearchPolicy


# ── should_continue ───────────────────────────────────────────────────────────


def test_should_continue_always_returns_true() -> None:
    policy = DefaultResearchPolicy()
    assert policy.should_continue(completed=0, failed=0, skipped=0) is True
    assert policy.should_continue(completed=10, failed=5, skipped=2) is True


# ── on_task_failure ───────────────────────────────────────────────────────────


def test_on_task_failure_returns_continue_below_threshold() -> None:
    policy = DefaultResearchPolicy(max_consecutive_failures=3)
    assert policy.on_task_failure(1) == FailureAction.CONTINUE
    assert policy.on_task_failure(2) == FailureAction.CONTINUE


def test_on_task_failure_returns_abort_at_threshold() -> None:
    policy = DefaultResearchPolicy(max_consecutive_failures=3)
    assert policy.on_task_failure(3) == FailureAction.ABORT


def test_on_task_failure_returns_abort_above_threshold() -> None:
    policy = DefaultResearchPolicy(max_consecutive_failures=3)
    assert policy.on_task_failure(5) == FailureAction.ABORT


def test_max_consecutive_failures_1_aborts_immediately() -> None:
    policy = DefaultResearchPolicy(max_consecutive_failures=1)
    assert policy.on_task_failure(1) == FailureAction.ABORT


def test_max_consecutive_failures_default_is_3() -> None:
    policy = DefaultResearchPolicy()
    assert policy.on_task_failure(2) == FailureAction.CONTINUE
    assert policy.on_task_failure(3) == FailureAction.ABORT


# ── validation ────────────────────────────────────────────────────────────────


def test_zero_max_consecutive_failures_raises() -> None:
    with pytest.raises(ValueError, match="max_consecutive_failures"):
        DefaultResearchPolicy(max_consecutive_failures=0)


def test_negative_max_consecutive_failures_raises() -> None:
    with pytest.raises(ValueError, match="max_consecutive_failures"):
        DefaultResearchPolicy(max_consecutive_failures=-1)
