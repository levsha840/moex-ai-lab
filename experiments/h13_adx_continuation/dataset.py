"""H-13 feature dataset: per-bar indicator arrays for the ADX Continuation experiment."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class H13Dataset:
    """Immutable per-bar indicator arrays for H-13 ADX Continuation."""

    closes: tuple[float, ...]
    highs: tuple[float, ...]
    lows: tuple[float, ...]
    adx_values: tuple[float | None, ...]
    rsi_values: tuple[float | None, ...]
    atr_values: tuple[float | None, ...]
    sma_fast_values: tuple[float | None, ...]
    sma_slow_values: tuple[float | None, ...]
    realized_vol_values: tuple[float | None, ...]

    def __len__(self) -> int:
        return len(self.closes)
