"""H-BB-SQUEEZE — Price near BB midline with bullish RSI (Market Structure, Tier B)."""
from experiments.generic.providers import GenericProviderFactory


class BBSqueezeProviderFactory(GenericProviderFactory):
    signal_type = "bb_squeeze"
    hold_bars = 8
    signal_params = {"bb_z_max": 0.5, "rsi_min": 50.0}
