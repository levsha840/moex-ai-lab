"""H-VOL-BREAKOUT — Realized vol spike + trend confirmation (Volatility, Tier B)."""
from experiments.generic.providers import GenericProviderFactory


class VolBreakoutProviderFactory(GenericProviderFactory):
    signal_type = "vol_breakout"
    hold_bars = 5
    signal_params = {"vol_threshold": 0.010, "adx_min": 20.0}
