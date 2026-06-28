"""H-RSI-OVERSOLD — RSI oversold bounce (Mean Reversion, Tier A)."""
from experiments.generic.providers import GenericProviderFactory


class RsiOversoldProviderFactory(GenericProviderFactory):
    signal_type = "rsi_oversold"
    hold_bars = 5
    signal_params = {"rsi_threshold": 30.0}
