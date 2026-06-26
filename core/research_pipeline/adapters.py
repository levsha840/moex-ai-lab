from __future__ import annotations

from typing import Any, Callable

from core.common import OrderSide
from core.costs.engine import ExecutionCostEngine
from core.costs.models import ExecutionCostConfig, ExecutionRequest
from core.experiment.models import ExperimentConfig
from core.regime.engine import MarketRegimeEngine
from core.regime.models import RegimeFeatures, RegimeSnapshot
from core.validation.models import ValidationReport
from core.validation.report import ValidationReportBuilder
from core.walkforward.engine import WalkForwardEngine
from core.walkforward.models import WalkForwardSummary, WalkForwardWindow


class StubFeatureProvider:
    """Returns a fixed RegimeFeatures regardless of ExperimentConfig.

    This is glue code — a stub adapter that satisfies the FeatureProvider
    protocol so the pipeline can run without a real feature-engineering layer.
    """

    def __init__(self, features: RegimeFeatures) -> None:
        self._features = features

    def build_features(self, config: ExperimentConfig) -> RegimeFeatures:
        return self._features


class RegimeEngineAdapter:
    """Adapts MarketRegimeEngine to the RegimeProvider protocol."""

    def __init__(self, engine: MarketRegimeEngine) -> None:
        self._engine = engine

    def classify(self, features: Any) -> RegimeSnapshot:
        return self._engine.classify(features)


class WalkForwardStrategyAdapter:
    """Adapts WalkForwardEngine + ExecutionCostEngine to the StrategyRunner protocol.

    Simulates one round-trip trade (BUY then SELL) per walk-forward window
    using ExecutionCostEngine to calculate realistic costs. This is a stub —
    no real strategy signals are generated; it exists only to wire the engines
    together for the first end-to-end pipeline.

    Returns WalkForwardSummary where each run result is a dict:
        {"pnl": float, "profitable": bool, "window_index": int}
    """

    _BUY_PRICE: float = 100.0
    _SELL_PRICE: float = 101.0
    _QUANTITY: float = 1.0

    def __init__(
        self,
        walkforward_engine: WalkForwardEngine,
        cost_engine: ExecutionCostEngine,
        data_length: int,
    ) -> None:
        self._wf = walkforward_engine
        self._cost = cost_engine
        self._data_length = data_length

    def run(self, config: ExperimentConfig, features: Any) -> WalkForwardSummary:
        ticker = config.strategy_name

        def _simulate_window(window: WalkForwardWindow) -> dict:
            buy = self._cost.calculate(
                ExecutionRequest(
                    ticker=ticker,
                    side=OrderSide.BUY,
                    price=self._BUY_PRICE,
                    quantity=self._QUANTITY,
                )
            )
            sell = self._cost.calculate(
                ExecutionRequest(
                    ticker=ticker,
                    side=OrderSide.SELL,
                    price=self._SELL_PRICE,
                    quantity=self._QUANTITY,
                )
            )
            pnl = (
                (self._SELL_PRICE - self._BUY_PRICE) * self._QUANTITY
                - buy.total_cost
                - sell.total_cost
            )
            return {
                "pnl": pnl,
                "profitable": pnl > 0,
                "window_index": window.index,
            }

        return self._wf.run(data_length=self._data_length, runner=_simulate_window)


class ValidationReportAdapter:
    """Adapts ValidationReportBuilder to the ValidationRunner protocol."""

    def __init__(
        self,
        builder: ValidationReportBuilder,
        evaluator: Callable[[Any], bool],
    ) -> None:
        self._builder = builder
        self._evaluator = evaluator

    def validate(self, strategy_result: Any) -> ValidationReport:
        return self._builder.build(strategy_result, self._evaluator)
