"""Strategy package exports."""

try:
    from core.strategy.base import BaseStrategy as LegacyBaseStrategy
    from core.strategy.base import Signal as LegacySignal
except Exception:  # pragma: no cover
    LegacyBaseStrategy = None  # type: ignore[assignment]
    LegacySignal = None  # type: ignore[assignment]

from core.strategy.base_strategy import BaseStrategy, ThresholdCloseStrategy
from core.strategy.signal import OrderIntent, PositionSide, Signal, SignalAction
from core.strategy.strategy_context import StrategyContext
from core.strategy.strategy_engine import StrategyDecision, StrategyEngine, StrategyEngineConfig
from core.strategy.strategy_registry import EngineStrategyRegistry

__all__ = [
    "BaseStrategy",
    "EngineStrategyRegistry",
    "LegacyBaseStrategy",
    "LegacySignal",
    "OrderIntent",
    "PositionSide",
    "Signal",
    "SignalAction",
    "StrategyContext",
    "StrategyDecision",
    "StrategyEngine",
    "StrategyEngineConfig",
    "ThresholdCloseStrategy",
]
