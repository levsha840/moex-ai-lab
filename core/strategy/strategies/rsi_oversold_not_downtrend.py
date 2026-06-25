from core.strategy.base import BaseStrategy, Signal


class RSIOversoldNotDowntrend(BaseStrategy):
    strategy_name = "RSI_OVERSOLD_NOT_DOWNTREND"
    version = "1.0"
    author = "human"
    source = "manual"

    def generate_signal(self, row) -> Signal:
        if row["rsi_14"] < 30 and row["regime"] != "TREND_DOWN":
            return Signal("BUY", confidence=1.0, reason="RSI_OVERSOLD_NOT_DOWNTREND")
        return Signal("HOLD", confidence=0.0, reason="NO_SIGNAL")
