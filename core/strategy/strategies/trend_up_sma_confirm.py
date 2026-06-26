from core.strategy.base_strategy import BaseStrategy
from core.strategy.signal import Signal, SignalAction
from core.strategy.strategy_context import StrategyContext


class TrendUpSMAConfirm(BaseStrategy):
    strategy_name = "TREND_UP_SMA_CONFIRM"

    def on_event(self, context: StrategyContext) -> Signal:
        features = context.features or {}
        close = context.close
        sma_50 = features.get("sma_50")
        regime = features.get("regime", "")
        if close is not None and sma_50 is not None and float(close) > float(sma_50) and regime == "TREND_UP":
            return Signal(
                action=SignalAction.BUY,
                ticker=context.ticker,
                ts=context.ts,
                strategy_name=self.strategy_name,
                confidence=1.0,
                price=context.close,
            )
        return self.hold(context, "conditions not met")
