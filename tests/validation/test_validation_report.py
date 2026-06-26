from __future__ import annotations

import pytest

from core.validation import ValidationReport, ValidationReportBuilder, ValidationStatus
from core.walkforward.models import WalkForwardRunResult, WalkForwardSummary, WalkForwardWindow


def _window(index: int = 0) -> WalkForwardWindow:
    return WalkForwardWindow(
        index=index,
        train_start=index * 50,
        train_end=index * 50 + 100,
        test_start=index * 50 + 100,
        test_end=index * 50 + 150,
    )


def _summary(*results) -> WalkForwardSummary:
    runs = [WalkForwardRunResult(window=_window(i), result=r) for i, r in enumerate(results)]
    return WalkForwardSummary(runs=runs)


_always_pass = lambda result: True
_always_fail = lambda result: False
_identity = lambda result: bool(result)


def test_empty_summary():
    builder = ValidationReportBuilder()
    report = builder.build(WalkForwardSummary(runs=[]), _always_pass)

    assert report.status == ValidationStatus.FAIL
    assert report.windows_total == 0
    assert report.windows_passed == 0
    assert report.windows_failed == 0
    assert report.pass_rate == 0.0


def test_all_passed():
    builder = ValidationReportBuilder()
    report = builder.build(_summary(True, True, True, True, True), _identity)

    assert report.status == ValidationStatus.PASS
    assert report.windows_total == 5
    assert report.windows_passed == 5
    assert report.windows_failed == 0
    assert report.pass_rate == pytest.approx(1.0)


def test_all_failed():
    builder = ValidationReportBuilder()
    report = builder.build(_summary(False, False, False), _identity)

    assert report.status == ValidationStatus.FAIL
    assert report.windows_total == 3
    assert report.windows_passed == 0
    assert report.windows_failed == 3
    assert report.pass_rate == pytest.approx(0.0)


def test_partial_pass():
    # 3 of 4 pass → 75% → FAIL (below 80%)
    builder = ValidationReportBuilder()
    report = builder.build(_summary(True, True, True, False), _identity)

    assert report.status == ValidationStatus.FAIL
    assert report.windows_passed == 3
    assert report.windows_failed == 1
    assert report.pass_rate == pytest.approx(0.75)


def test_exactly_80_percent():
    # 4 of 5 pass → 80% → PASS (>= 0.80)
    builder = ValidationReportBuilder()
    report = builder.build(_summary(True, True, True, True, False), _identity)

    assert report.status == ValidationStatus.PASS
    assert report.pass_rate == pytest.approx(0.80)


def test_below_80_percent():
    # 7 of 10 pass → 70% → FAIL
    results = [True] * 7 + [False] * 3
    builder = ValidationReportBuilder()
    report = builder.build(_summary(*results), _identity)

    assert report.status == ValidationStatus.FAIL
    assert report.pass_rate == pytest.approx(0.70)


def test_metrics_generated():
    builder = ValidationReportBuilder()
    report = builder.build(_summary(True, True, False), _identity)

    metric_map = {m.name: m.value for m in report.metrics}
    assert "pass_rate" in metric_map
    assert "windows_total" in metric_map
    assert "windows_passed" in metric_map
    assert "windows_failed" in metric_map
    assert metric_map["pass_rate"] == pytest.approx(2 / 3)
    assert metric_map["windows_total"] == pytest.approx(3.0)
    assert metric_map["windows_passed"] == pytest.approx(2.0)
    assert metric_map["windows_failed"] == pytest.approx(1.0)


def test_notes_on_fail_contain_explanation():
    builder = ValidationReportBuilder()
    report = builder.build(_summary(False), _identity)

    assert report.status == ValidationStatus.FAIL
    assert len(report.notes) > 0
    assert any("pass rate" in note.lower() for note in report.notes)


def test_notes_empty_on_pass():
    builder = ValidationReportBuilder()
    report = builder.build(_summary(True, True, True, True, True), _identity)

    assert report.status == ValidationStatus.PASS
    assert report.notes == []


def test_deterministic():
    summary = _summary(True, False, True, True, False, True)
    builder = ValidationReportBuilder()
    report_a = builder.build(summary, _identity)
    report_b = builder.build(summary, _identity)

    assert report_a.status == report_b.status
    assert report_a.pass_rate == pytest.approx(report_b.pass_rate)
    assert report_a.windows_total == report_b.windows_total
    assert report_a.windows_passed == report_b.windows_passed
    assert report_a.windows_failed == report_b.windows_failed
    assert len(report_a.metrics) == len(report_b.metrics)


def test_evaluator_exception_propagates():
    def broken_evaluator(result):
        raise RuntimeError("evaluator failed")

    builder = ValidationReportBuilder()
    with pytest.raises(RuntimeError, match="evaluator failed"):
        builder.build(_summary(True, True), broken_evaluator)


def test_evaluator_receives_run_result_value():
    received = []

    def capturing_evaluator(result):
        received.append(result)
        return True

    summary = _summary(42, "hello", 3.14)
    ValidationReportBuilder().build(summary, capturing_evaluator)

    assert received == [42, "hello", 3.14]


def test_validation_report_is_independent_of_paper_trading():
    # ValidationReport is built from WalkForwardSummary alone — no paper/broker/db imports
    import core.validation.report as report_module
    import inspect
    source = inspect.getsource(report_module)
    assert "paper" not in source.lower()
    assert "broker" not in source.lower()
    assert "database" not in source.lower()
    assert "position" not in source.lower()
