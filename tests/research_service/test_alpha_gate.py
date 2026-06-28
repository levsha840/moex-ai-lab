"""Tests for services.research.alpha_gate.AlphaLibraryGate."""
from __future__ import annotations

import pytest

from services.research.alpha_gate import AlphaGateResult, AlphaLibraryGate, RESEARCH_MIN_PASS_RATE


class TestAlphaGateResult:
    def test_str_includes_mark(self):
        r = AlphaGateResult(passed=True, pass_rate=0.55, windows_total=30, reason="ok")
        assert "PASS" in str(r)

    def test_str_fail_mark(self):
        r = AlphaGateResult(passed=False, pass_rate=0.30, windows_total=10, reason="low")
        assert "FAIL" in str(r)

    def test_str_none_pass_rate(self):
        r = AlphaGateResult(passed=False, pass_rate=None, windows_total=0, reason="no data")
        assert "n/a" in str(r)


class TestAlphaLibraryGate:
    @pytest.fixture
    def gate(self) -> AlphaLibraryGate:
        return AlphaLibraryGate()

    # ── Passing cases ─────────────────────────────────────────────────────────

    def test_passes_at_minimum_threshold(self, gate):
        result = gate.check(pass_rate=0.40, windows_total=10)
        assert result.passed is True

    def test_passes_above_threshold(self, gate):
        result = gate.check(pass_rate=0.65, windows_total=20)
        assert result.passed is True

    def test_passes_with_many_windows(self, gate):
        result = gate.check(pass_rate=0.50, windows_total=100)
        assert result.passed is True

    def test_pass_result_contains_pass_rate(self, gate):
        result = gate.check(pass_rate=0.55, windows_total=20)
        assert result.pass_rate == 0.55
        assert result.windows_total == 20

    # ── Failing cases ─────────────────────────────────────────────────────────

    def test_fails_none_pass_rate(self, gate):
        result = gate.check(pass_rate=None, windows_total=20)
        assert result.passed is False

    def test_fails_below_threshold(self, gate):
        result = gate.check(pass_rate=0.39, windows_total=20)
        assert result.passed is False

    def test_fails_zero_pass_rate(self, gate):
        result = gate.check(pass_rate=0.0, windows_total=20)
        assert result.passed is False

    def test_fails_insufficient_windows(self, gate):
        result = gate.check(pass_rate=0.90, windows_total=4)
        assert result.passed is False

    def test_fails_zero_windows(self, gate):
        result = gate.check(pass_rate=0.90, windows_total=0)
        assert result.passed is False

    def test_reason_mentions_pass_rate_when_too_low(self, gate):
        result = gate.check(pass_rate=0.20, windows_total=20)
        assert "0.20" in result.reason or "pass_rate" in result.reason

    def test_reason_mentions_windows_when_too_few(self, gate):
        result = gate.check(pass_rate=0.90, windows_total=3)
        assert "windows" in result.reason.lower()

    def test_reason_mentions_no_trades_when_none(self, gate):
        result = gate.check(pass_rate=None, windows_total=20)
        assert "no trades" in result.reason.lower() or "not available" in result.reason.lower()

    # ── Boundary ─────────────────────────────────────────────────────────────

    def test_exactly_at_threshold_passes(self, gate):
        result = gate.check(pass_rate=RESEARCH_MIN_PASS_RATE, windows_total=5)
        assert result.passed is True

    def test_just_below_threshold_fails(self, gate):
        result = gate.check(pass_rate=RESEARCH_MIN_PASS_RATE - 0.001, windows_total=5)
        assert result.passed is False

    def test_exactly_min_windows_passes(self, gate):
        result = gate.check(pass_rate=0.50, windows_total=5)
        assert result.passed is True

    def test_one_below_min_windows_fails(self, gate):
        result = gate.check(pass_rate=0.50, windows_total=4)
        assert result.passed is False

    # ── Custom thresholds ─────────────────────────────────────────────────────

    def test_custom_min_pass_rate(self):
        gate = AlphaLibraryGate(min_pass_rate=0.60)
        assert gate.check(pass_rate=0.59, windows_total=10).passed is False
        assert gate.check(pass_rate=0.60, windows_total=10).passed is True

    def test_custom_min_windows(self):
        gate = AlphaLibraryGate(min_windows=10)
        assert gate.check(pass_rate=0.50, windows_total=9).passed is False
        assert gate.check(pass_rate=0.50, windows_total=10).passed is True
