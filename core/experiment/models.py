from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass
class ExperimentConfig:
    experiment_id: str
    hypothesis_id: str
    dataset_id: str
    strategy_name: str
    feature_set: list[str]


class ExperimentStage(str, Enum):
    INITIALIZED = "INITIALIZED"
    FEATURES_READY = "FEATURES_READY"
    REGIME_CLASSIFIED = "REGIME_CLASSIFIED"
    STRATEGY_EXECUTED = "STRATEGY_EXECUTED"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"


@dataclass
class ExperimentResult:
    config: ExperimentConfig
    stage: ExperimentStage
    regime: Any = None
    validation: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
