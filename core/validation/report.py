from __future__ import annotations

from typing import Any, Callable

from core.validation.models import ValidationMetric, ValidationReport, ValidationStatus
from core.walkforward.models import WalkForwardSummary

_PASS_THRESHOLD = 0.80


class ValidationReportBuilder:
    def build(
        self,
        summary: WalkForwardSummary,
        evaluator: Callable[[Any], bool],
    ) -> ValidationReport:
        windows_total = len(summary.runs)

        if windows_total == 0:
            windows_passed = 0
            windows_failed = 0
            pass_rate = 0.0
        else:
            windows_passed = sum(1 for run in summary.runs if evaluator(run.result))
            windows_failed = windows_total - windows_passed
            pass_rate = windows_passed / windows_total

        status = ValidationStatus.PASS if pass_rate >= _PASS_THRESHOLD else ValidationStatus.FAIL

        metrics = [
            ValidationMetric(name="pass_rate", value=pass_rate),
            ValidationMetric(name="windows_total", value=float(windows_total)),
            ValidationMetric(name="windows_passed", value=float(windows_passed)),
            ValidationMetric(name="windows_failed", value=float(windows_failed)),
        ]

        notes: list[str] = []
        if status == ValidationStatus.FAIL:
            notes.append("Insufficient pass rate")

        return ValidationReport(
            status=status,
            metrics=metrics,
            windows_total=windows_total,
            windows_passed=windows_passed,
            windows_failed=windows_failed,
            pass_rate=pass_rate,
            notes=notes,
        )
