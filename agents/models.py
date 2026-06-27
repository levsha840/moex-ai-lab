"""Domain models shared across all Intelligence Era agents.

All models are frozen dataclasses — immutable and serialisable.
MacroSnapshot contains a tuple[tuple[str, int], ...] for missing_values
to remain hashable (dict fields would break hashability).

No external dependencies: stdlib only.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceRef:
    """Pointer to the evidence backing an agent's output.

    source:    human-readable name of the data origin
               ("MOEX ISS API", "fixture", "calculation")
    reference: URL, file path, or free-form description
    timestamp: ISO-format datetime string — when evidence was collected
    """

    source: str
    reference: str
    timestamp: str


@dataclass(frozen=True)
class ConfidenceScore:
    """Normalised confidence in an agent's output.

    value: float in [0.0, 1.0]
    reason: short explanation of the score
    """

    value: float
    reason: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(
                f"ConfidenceScore.value must be in [0.0, 1.0], got {self.value}"
            )


@dataclass(frozen=True)
class AgentResult:
    """Universal envelope returned by every agent.

    Carries identity, provenance, and the domain-specific payload (output).
    Matches the agent contract from docs/30_INTELLIGENCE_ARCHITECTURE.md.
    """

    agent_id: str
    agent_type: str        # "DATA" | "ANALYSIS" | "RESEARCH" | "KNOWLEDGE" | "CHIEF_SCIENTIST"
    version: str
    input_summary: str     # brief description of what the agent consumed
    output: object         # domain-specific payload (e.g. DatasetManifest)
    evidence: tuple[EvidenceRef, ...]
    confidence: ConfidenceScore
    created_at: str        # ISO-format timestamp from injected clock


@dataclass(frozen=True)
class MarketSnapshot:
    """Lightweight summary of available market data — not the data itself."""

    ticker: str
    timeframe: str
    bar_count: int
    date_from: str
    date_to: str
    session_filter: str    # "main" | "full"


@dataclass(frozen=True)
class MacroSeries:
    """One macro time series stored by MacroAgent.

    path points to the CSV file in data/context/macro/{period}/{symbol}_{timeframe}.csv.
    CSV columns: date, open, high, low, close, volume
    """

    symbol: str        # "IMOEX" | "USDRUB" | "RGBI"
    timeframe: str     # "1d" | "1h"
    date_from: str
    date_to: str
    value_count: int
    path: str          # absolute path to saved CSV


@dataclass(frozen=True)
class MacroSnapshot:
    """Output of MacroAgent — a collection of macro time series.

    missing_values: tuple of (symbol, 0) pairs for symbols that returned
    no data. Use dict(snapshot.missing_values) to convert to dict.
    Stored as tuple-of-tuples to keep MacroSnapshot hashable.
    """

    snapshot_id: str
    period: str
    observations: tuple[MacroSeries, ...]
    source_refs: tuple[EvidenceRef, ...]
    missing_values: tuple[tuple[str, int], ...]   # (symbol, missing_count)
    confidence: ConfidenceScore


class RegimeLabel:
    """String constants for every possible regime label.

    Three regime dimensions:
      trend      — TREND_UP | TREND_DOWN | RANGE
      volatility — LOW_VOL  | NORMAL_VOL | HIGH_VOL
      risk       — RISK_ON  | RISK_OFF   | NEUTRAL
    """

    # Trend
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"

    # Volatility
    LOW_VOL = "LOW_VOL"
    NORMAL_VOL = "NORMAL_VOL"
    HIGH_VOL = "HIGH_VOL"

    # Risk (macro-derived)
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"

    _TREND = frozenset([TREND_UP, TREND_DOWN, RANGE])
    _VOLATILITY = frozenset([LOW_VOL, NORMAL_VOL, HIGH_VOL])
    _RISK = frozenset([RISK_ON, RISK_OFF, NEUTRAL])


@dataclass(frozen=True)
class RegimeSegment:
    """One classified window in a regime analysis.

    regime_type: "trend" | "volatility" | "risk"
    metrics:     (name, value) pairs — all named indicators used for classification
    evidence:    short text strings explaining why this label was assigned
    confidence:  0.0–1.0, derived from signal strength
    """

    regime_type: str
    label: str
    date_from: str
    date_to: str
    confidence: float
    metrics: tuple[tuple[str, float], ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class RegimeSnapshot:
    """Output of RegimeDetectionAgent.

    segments contains RegimeSegment entries for each regime type × each
    time window in the period.
    Saved to data/context/regime/{instrument.lower()}_{period}.json.
    """

    snapshot_id: str
    instrument: str
    period: str
    segments: tuple[RegimeSegment, ...]
    source_refs: tuple[EvidenceRef, ...]
    confidence: ConfidenceScore


@dataclass(frozen=True)
class CorrelationPair:
    """Pearson correlation of daily returns between one instrument and one macro series.

    lag > 0: macro leads instrument by lag trading days
    lag < 0: instrument leads macro by abs(lag) trading days
    lag == 0: same-period correlation

    correlation is math.nan when observation_count < 3 or variance is zero.
    """

    instrument: str          # e.g. "SBER"
    macro_symbol: str        # "IMOEX" | "USDRUB" | "RGBI"
    lag: int
    correlation: float       # Pearson r in [-1.0, 1.0] or math.nan
    observation_count: int   # number of aligned return pairs used


@dataclass(frozen=True)
class CorrelationSnapshot:
    """Output of CorrelationAgent — full correlation analysis for one instrument.

    Saved to data/context/correlation/{instrument.lower()}_{period}.json.
    """

    snapshot_id: str
    instrument: str
    period: str
    pairs: tuple[CorrelationPair, ...]
    total_instrument_bars: int   # daily close count in instrument series
    aligned_dates: int           # instrument dates also present in macro series
    missing_alignment: int       # total_instrument_bars - aligned_dates
    source_refs: tuple[EvidenceRef, ...]
    confidence: ConfidenceScore


@dataclass(frozen=True)
class DatasetManifest:
    """Describes a dataset written to disk — compatible with DatasetLoader.

    ohlcv_path and metadata_path are absolute paths.
    All fields required by DatasetLoader are present.
    """

    dataset_id: str
    dataset_path: str
    ohlcv_path: str
    metadata_path: str
    ticker: str
    timeframe: str
    bar_count: int
    date_from: str
    date_to: str
    session_filter: str
    source: str
