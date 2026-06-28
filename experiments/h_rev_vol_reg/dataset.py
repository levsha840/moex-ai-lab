"""Dataset for H-REV-VOL-REG: Mean Reversion with Volatility Spike and Regime Filter."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RevVolRegDataset:
    """Pre-computed feature arrays for H-REV-VOL-REG strategy evaluation.

    All tuples are parallel (same length as the input candle series).
    None values indicate insufficient history for the indicator at that bar.
    """

    closes: tuple[float, ...]
    highs: tuple[float, ...]
    lows: tuple[float, ...]
    adx_values: tuple[float | None, ...]
    rsi_values: tuple[float | None, ...]
    bb_zscore_values: tuple[float | None, ...]
    realized_vol_values: tuple[float | None, ...]
    atr_values: tuple[float | None, ...]
    bb_upper_values: tuple[float | None, ...]
    bb_lower_values: tuple[float | None, ...]

    def __len__(self) -> int:
        return len(self.closes)
