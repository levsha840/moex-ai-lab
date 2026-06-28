"""H-DUAL-MA-TREND — SMA(5) > SMA(20) > SMA(50) full MA alignment (Momentum, Tier A)."""
from experiments.generic.providers import GenericProviderFactory


class DualMaTrendProviderFactory(GenericProviderFactory):
    signal_type = "dual_ma_trend"
    hold_bars = 5
    signal_params = {}
