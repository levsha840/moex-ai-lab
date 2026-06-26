from __future__ import annotations

from typing import Any, Protocol

from core.experiment.models import ExperimentConfig


class FeatureProvider(Protocol):
    def build_features(self, config: ExperimentConfig) -> Any: ...


class RegimeProvider(Protocol):
    def classify(self, features: Any) -> Any: ...


class StrategyRunner(Protocol):
    def run(self, config: ExperimentConfig, features: Any) -> Any: ...


class ValidationRunner(Protocol):
    def validate(self, strategy_result: Any) -> Any: ...
