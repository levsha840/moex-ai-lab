"""Base strategy interface for Strategy Engine v1.4."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.strategy.signal import Signal, SignalAction
from core.strategy.strategy_context import StrategyContext


class BaseStrategy(ABC):
    """Base class for all new strategies.

    Old strategies using ``generate_signal(row)`` can still be adapted by
    StrategyEngine, but new code should implement ``on_event(context)``.
    """

    strategy_name = "base_strategy"
    version = "1.0"
    author = "MOEX AI LAB"
    source = "manual"

    @abstractmethod
    def on_event(self, context: StrategyContext) -> Signal:
        """Produce one normalized signal for one replay step."""

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "version": self.version,
            "author": self.author,
            "source": self.source,
        }

    def hold(self, context: StrategyContext, reason: str = "") -> Signal:
        return Signal.hold(
            ticker=context.ticker,
            ts=context.ts,
            strategy_name=self.strategy_name,
            reason=reason,
            price=context.close,
        )


class ThresholdCloseStrategy(BaseStrategy):
    """Simple built-in example strategy for tests and smoke checks."""

    strategy_name = "THRESHOLD_CLOSE"

    def __init__(self, buy_above: float, sell_below: float) -> None:
        if sell_below > buy_above:
            raise ValueError("sell_below must be <= buy_above")
        self.buy_above = float(buy_above)
        self.sell_below = float(sell_below)

    def on_event(self, context: StrategyContext) -> Signal:
        close = context.close
        if close is None:
            return self.hold(context, "close price is missing")
        if close >= self.buy_above:
            return Signal(
                action=SignalAction.BUY,
                ticker=context.ticker,
                ts=context.ts,
                strategy_name=self.strategy_name,
                confidence=0.7,
                reason=f"close >= {self.buy_above}",
                price=close,
            )
        if close <= self.sell_below:
            return Signal(
                action=SignalAction.SELL,
                ticker=context.ticker,
                ts=context.ts,
                strategy_name=self.strategy_name,
                confidence=0.7,
                reason=f"close <= {self.sell_below}",
                price=close,
            )
        return self.hold(context, "close inside neutral zone")
