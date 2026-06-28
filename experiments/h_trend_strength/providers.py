"""H-TREND-STRENGTH — Strong trend ADX>30 + RSI momentum (Trend Following, Tier A)."""
from experiments.generic.providers import GenericProviderFactory


class TrendStrengthProviderFactory(GenericProviderFactory):
    signal_type = "trend_strength"
    hold_bars = 10
    signal_params = {"adx_min": 30.0, "rsi_min": 50.0}
