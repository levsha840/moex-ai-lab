"""H-MOMENTUM-PULLBACK — Price above SMA50 pulls back to SMA20 (Momentum, Tier A)."""
from experiments.generic.providers import GenericProviderFactory


class MomentumPullbackProviderFactory(GenericProviderFactory):
    signal_type = "momentum_pullback"
    hold_bars = 5
    signal_params = {}
