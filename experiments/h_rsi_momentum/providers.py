"""H-RSI-MOMENTUM — RSI momentum + ADX trend confirmation (Momentum, Tier A)."""
from experiments.generic.providers import GenericProviderFactory


class RsiMomentumProviderFactory(GenericProviderFactory):
    signal_type = "rsi_momentum"
    hold_bars = 8
    signal_params = {"rsi_min": 55.0, "adx_min": 20.0}
