from core.strategy.base import BaseStrategy, Signal

class TrendUpSMAConfirm(BaseStrategy):
    strategy_name = "TREND_UP_SMA_CONFIRM"

    def generate_signal(self, row):
        if row["close"] > row["sma_50"] and row["regime"] == "TREND_UP":
            return Signal("BUY", 1.0, self.strategy_name)
        return Signal("HOLD", 0.0, "NO_SIGNAL")
