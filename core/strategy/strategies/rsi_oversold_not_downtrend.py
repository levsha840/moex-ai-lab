from core.strategy.base_strategy import BaseStrategy
from core.strategy.signal import Signal, SignalAction
from core.strategy.strategy_context import StrategyContext


class RSIOversoldNotDowntrend(BaseStrategy):
    strategy_name = "RSI_OVERSOLD_NOT_DOWNTREND"

    def on_event(self, context: StrategyContext) -> Signal:
        features = context.features or {}
        rsi = features.get("rsi_14", 100.0)
        regime = features.get("regime", "")
        if float(rsi) < 30 and regime != "TREND_DOWN":
            return Signal(
                action=SignalAction.BUY,
                ticker=context.ticker,
                ts=context.ts,
                strategy_name=self.strategy_name,
                confidence=1.0,
                price=context.close,
            )
        return self.hold(context, "conditions not met")
