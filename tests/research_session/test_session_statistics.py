"""Tests for SessionStatistics model."""
from __future__ import annotations

import pytest

from core.research_session.models import SessionStatistics

_TS_SECONDS = 5.0


def _stats(
    candidates_generated: int = 0,
    hypotheses_accepted: int = 0,
    tasks_completed: int = 0,
    tasks_failed: int = 0,
    tasks_skipped: int = 0,
    validation_pass: int = 0,
    validation_fail: int = 0,
    validation_inconclusive: int = 0,
    avg_pass_rate: float | None = None,
    kb_entries_created: int = 0,
    duration_seconds: float = _TS_SECONDS,
) -> SessionStatistics:
    return SessionStatistics(
        candidates_generated=candidates_generated,
        hypotheses_accepted=hypotheses_accepted,
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        tasks_skipped=tasks_skipped,
        validation_pass=validation_pass,
        validation_fail=validation_fail,
        validation_inconclusive=validation_inconclusive,
        avg_pass_rate=avg_pass_rate,
        kb_entries_created=kb_entries_created,
        duration_seconds=duration_seconds,
    )


# ─────────────────────────────────────────────────────────────────────────────
# validation_pass_rate
# ─────────────────────────────────────────────────────────────────────────────

def test_validation_pass_rate_all_pass():
    s = _stats(validation_pass=3, validation_fail=0)
    assert s.validation_pass_rate == pytest.approx(1.0)


def test_validation_pass_rate_all_fail():
    s = _stats(validation_pass=0, validation_fail=3)
    assert s.validation_pass_rate == pytest.approx(0.0)


def test_validation_pass_rate_mixed():
    s = _stats(validation_pass=2, validation_fail=2)
    assert s.validation_pass_rate == pytest.approx(0.5)


def test_validation_pass_rate_none_when_no_conclusive():
    s = _stats(validation_pass=0, validation_fail=0, validation_inconclusive=5)
    assert s.validation_pass_rate is None


def test_validation_pass_rate_none_all_zeros():
    s = _stats()
    assert s.validation_pass_rate is None


def test_validation_pass_rate_ignores_inconclusive():
    # 2 pass, 0 fail, 5 inconclusive → pass_rate based on 2/(2+0)=1.0
    s = _stats(validation_pass=2, validation_fail=0, validation_inconclusive=5)
    assert s.validation_pass_rate == pytest.approx(1.0)


def test_validation_pass_rate_three_quarters():
    s = _stats(validation_pass=3, validation_fail=1)
    assert s.validation_pass_rate == pytest.approx(0.75)


# ─────────────────────────────────────────────────────────────────────────────
# Frozen dataclass
# ─────────────────────────────────────────────────────────────────────────────

def test_session_statistics_is_frozen():
    s = _stats(candidates_generated=3)
    with pytest.raises((AttributeError, TypeError)):
        s.candidates_generated = 99  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# avg_pass_rate independence from validation_pass_rate
# ─────────────────────────────────────────────────────────────────────────────

def test_avg_pass_rate_stored_independently():
    # avg_pass_rate is mean of individual task pass_rates; not same as pass_rate fraction
    s = _stats(validation_pass=1, validation_fail=1, avg_pass_rate=0.85)
    assert s.avg_pass_rate == pytest.approx(0.85)
    # validation_pass_rate = 1/(1+1) = 0.5 ≠ avg_pass_rate
    assert s.validation_pass_rate == pytest.approx(0.5)


def test_avg_pass_rate_none_propagates():
    s = _stats(avg_pass_rate=None)
    assert s.avg_pass_rate is None


def test_duration_seconds_stored():
    s = _stats(duration_seconds=42.5)
    assert s.duration_seconds == pytest.approx(42.5)
