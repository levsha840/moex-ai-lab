from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RegimeType(str, Enum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RegimeFeatures:
    adx: float
    atr_pct: float
    sma_fast: float
    sma_slow: float
    realized_volatility: float


@dataclass
class RegimeSnapshot:
    regime: RegimeType
    confidence: float
    reasons: list[str] = field(default_factory=list)
