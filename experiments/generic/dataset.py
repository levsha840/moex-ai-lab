"""Shared OHLCV feature dataset used by all generic hypotheses."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenericOHLCVDataset:
    """Pre-computed feature arrays covering all generic signal types.

    SMA periods: 5 (fast), 20 (medium/BB), 50 (slow).
    All tuples are parallel (same length as input candle series).
    None = insufficient history at that bar.
    """

    closes: tuple[float, ...]
    highs: tuple[float, ...]
    lows: tuple[float, ...]
    adx_values: tuple[float | None, ...]
    rsi_values: tuple[float | None, ...]
    atr_values: tuple[float | None, ...]
    sma_5_values: tuple[float | None, ...]
    sma_20_values: tuple[float | None, ...]
    sma_50_values: tuple[float | None, ...]
    bb_zscore_values: tuple[float | None, ...]
    realized_vol_values: tuple[float | None, ...]

    def __len__(self) -> int:
        return len(self.closes)
