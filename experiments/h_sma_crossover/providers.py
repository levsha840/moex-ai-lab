"""H-SMA-CROSSOVER — SMA(20) crosses above SMA(50) golden cross (Trend Following, Tier A)."""
from experiments.generic.providers import GenericProviderFactory


class SmaCrossoverProviderFactory(GenericProviderFactory):
    signal_type = "sma_crossover"
    hold_bars = 10
    signal_params = {}
