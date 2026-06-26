from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ValidationMetric:
    name: str
    value: float


@dataclass
class ValidationReport:
    status: ValidationStatus
    metrics: list[ValidationMetric]
    windows_total: int
    windows_passed: int
    windows_failed: int
    pass_rate: float
    notes: list[str] = field(default_factory=list)
