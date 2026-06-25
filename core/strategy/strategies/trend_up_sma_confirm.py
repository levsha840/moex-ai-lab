from core.strategy.base import BaseStrategy, Signal


class TrendUpSMAConfirm(BaseStrategy):
    strategy_name = "TREND_UP_SMA_CONFIRM"
    version = "1.0"
    author = "human"
    source = "manual"

    def generate_signal(self, row) -> Signal:
        if row["close"] > row["sma_50"] and row["regime"] == "TREND_UP":
            return Signal("BUY", confidence=1.0, reason="TREND_UP_SMA_CONFIRM")
        return Signal("HOLD", confidence=0.0, reason="NO_SIGNAL")
