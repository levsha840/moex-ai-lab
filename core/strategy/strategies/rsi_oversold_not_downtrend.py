from core.strategy.base import BaseStrategy, Signal

class RSIOversoldNotDowntrend(BaseStrategy):
    strategy_name = "RSI_OVERSOLD_NOT_DOWNTREND"

    def generate_signal(self, row):
        if row["rsi_14"] < 30 and row["regime"] != "TREND_DOWN":
            return Signal("BUY", 1.0, self.strategy_name)
        return Signal("HOLD", 0.0, "NO_SIGNAL")
