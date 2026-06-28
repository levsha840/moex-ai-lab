"""Domain models for the Paper Trading -> T-Invest Sandbox bridge layer.

This module defines the new vocabulary that connects Research Service output
(StrategyCandidate) through paper execution (TradeSignal, PositionSizingRule,
RiskLimit, PaperOrderRecord) to reporting (PaperPortfolio, ExecutionReport).

Core paper primitives (PaperOrder, PaperPosition, PaperPortfolioSnapshot) live
in core.paper.models and are re-exported via trading.__init__.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Strategy Candidate — gate between Research Service and paper trading
# ---------------------------------------------------------------------------

class StrategyCandidateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    CANDIDATE_RESEARCH_PASSED = "CANDIDATE_RESEARCH_PASSED"  # research gate cleared; pending risk review
    APPROVED_FOR_PAPER = "APPROVED_FOR_PAPER"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class StrategyCandidate:
    """Approved output from Research Service.

    Only candidates with status=APPROVED_FOR_PAPER are accepted by
    ApprovedCandidatePaperEngine. Candidates with any other status raise
    ValueError at engine.run() time.
    """

    candidate_id: str
    hypothesis_id: str
    instrument: str
    period: str
    timeframe: str
    pass_rate: float
    confidence: float
    regime_label: str
    source_ref: str
    status: StrategyCandidateStatus = StrategyCandidateStatus.PROPOSED
    approved_by: str = ""
    features: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id is required")
        if not self.hypothesis_id:
            raise ValueError("hypothesis_id is required")
        if not self.instrument:
            raise ValueError("instrument is required")
        if not 0.0 <= self.pass_rate <= 1.0:
            raise ValueError("pass_rate must be in [0.0, 1.0]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")

    @property
    def is_approved(self) -> bool:
        return self.status == StrategyCandidateStatus.APPROVED_FOR_PAPER


# ---------------------------------------------------------------------------
# Trade Signal — concrete instruction derived from a StrategyCandidate
# ---------------------------------------------------------------------------

class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeSignalStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class TradeSignal:
    """Concrete trade instruction generated from an approved StrategyCandidate."""

    signal_id: str
    candidate_id: str
    instrument: str
    direction: TradeDirection
    entry_price: float
    timeframe: str
    regime_label: str
    confidence: float
    ts: str
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str = ""
    status: TradeSignalStatus = TradeSignalStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.signal_id:
            raise ValueError("signal_id is required")
        if not self.instrument:
            raise ValueError("instrument is required")
        if self.entry_price <= 0:
            raise ValueError("entry_price must be > 0")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")
        if self.stop_loss is not None and self.stop_loss <= 0:
            raise ValueError("stop_loss must be > 0 when set")
        if self.take_profit is not None and self.take_profit <= 0:
            raise ValueError("take_profit must be > 0 when set")


# ---------------------------------------------------------------------------
# Position Sizing Rule
# ---------------------------------------------------------------------------

class SizingMethod(str, Enum):
    FIXED_LOTS = "FIXED_LOTS"
    FIXED_PCT = "FIXED_PCT"
    VOLATILITY_SCALED = "VOLATILITY_SCALED"


@dataclass(frozen=True)
class PositionSizingRule:
    """Computes lot count from equity, price, and optional volatility estimate.

    Methods
    -------
    FIXED_LOTS:
        Always trade `value` lots regardless of equity or price.
        value = number of lots (must be a whole number >= 1).

    FIXED_PCT:
        Allocate `value` fraction of equity to each position.
        value = fraction in (0, 1]; e.g. 0.05 means 5% of equity.
        lots = floor(equity * value / price).

    VOLATILITY_SCALED:
        Risk-target sizing: target `value` volatility contribution
        from each position as a fraction of equity.
        value = vol target in (0, 1]; e.g. 0.01 means 1% daily vol.
        lots = floor((equity * value / daily_vol) / price).
        Requires volatility argument in compute_lots(); falls back to
        min_lots if volatility is not provided or is zero.
    """

    method: SizingMethod
    value: float
    max_lots: int = 1000
    min_lots: int = 1

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("value must be > 0")
        if self.min_lots <= 0:
            raise ValueError("min_lots must be >= 1")
        if self.max_lots < self.min_lots:
            raise ValueError("max_lots must be >= min_lots")
        if self.method in (SizingMethod.FIXED_PCT, SizingMethod.VOLATILITY_SCALED):
            if self.value > 1.0:
                raise ValueError(
                    "value must be <= 1.0 for FIXED_PCT / VOLATILITY_SCALED"
                )

    def compute_lots(
        self,
        equity: float,
        price: float,
        volatility: float | None = None,
    ) -> int:
        """Return lot count clamped to [min_lots, max_lots]."""
        if price <= 0:
            raise ValueError("price must be > 0")
        if equity <= 0:
            return self.min_lots

        if self.method == SizingMethod.FIXED_LOTS:
            lots = int(self.value)

        elif self.method == SizingMethod.FIXED_PCT:
            position_value = equity * self.value
            lots = max(1, int(position_value / price))

        elif self.method == SizingMethod.VOLATILITY_SCALED:
            if volatility is None or volatility <= 0.0:
                return self.min_lots
            # Target: (equity * vol_target) / (price * daily_vol)
            lots = max(1, int((equity * self.value) / (price * volatility)))

        else:
            lots = self.min_lots

        return max(self.min_lots, min(self.max_lots, lots))


# ---------------------------------------------------------------------------
# Risk Limit — declarative strategy-level risk constraints
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskLimit:
    """Strategy-level risk constraints evaluated by the bridge engine.

    These sit above the per-trade RiskLimits in core.risk.models and add
    portfolio-level controls (drawdown stop, daily loss limit).
    """

    max_position_pct: float = 0.05      # max % of equity per position
    max_drawdown_pct: float = 0.10      # stop trading if drawdown exceeds this
    max_open_positions: int = 10        # max concurrent open positions
    max_daily_loss_pct: float = 0.02    # daily loss ceiling (not enforced intraday in v1)
    allow_short: bool = False

    def __post_init__(self) -> None:
        if not 0.0 < self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be in (0, 1]")
        if not 0.0 < self.max_drawdown_pct <= 1.0:
            raise ValueError("max_drawdown_pct must be in (0, 1]")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be >= 1")
        if not 0.0 < self.max_daily_loss_pct <= 1.0:
            raise ValueError("max_daily_loss_pct must be in (0, 1]")


# ---------------------------------------------------------------------------
# Paper Order Record — journal entry for one executed or rejected paper order
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaperOrderRecord:
    """Immutable journal record for a single paper trade attempt."""

    order_id: str
    signal_id: str
    instrument: str
    direction: str          # "LONG" | "SHORT"
    quantity: int
    price: float
    commission: float
    slippage: float
    realized_pnl: float
    ts: str
    status: str             # "FILLED" | "REJECTED"
    reject_reason: str = ""


# ---------------------------------------------------------------------------
# Paper Portfolio — portfolio snapshot exposed by the bridge engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaperPortfolio:
    """Point-in-time portfolio state computed from the paper engine's state."""

    initial_equity: float
    cash: float
    market_value: float
    equity: float
    realized_pnl: float
    open_positions: int
    peak_equity: float
    current_drawdown: float
    current_drawdown_pct: float


# ---------------------------------------------------------------------------
# Execution Report — summary of a completed paper trading run
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionReport:
    """Immutable summary of a complete paper trading session.

    Generated by ApprovedCandidatePaperEngine.run() after processing all
    TradeSignals for an approved StrategyCandidate.
    """

    report_id: str
    candidate_id: str
    instrument: str
    initial_equity: float
    final_equity: float
    peak_equity: float
    realized_pnl: float
    realized_pnl_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    trades_count: int           # total filled trades
    wins: int                   # close trades with realized_pnl > 0
    losses: int                 # close trades with realized_pnl < 0
    win_rate: float             # wins / close_trades; 0.0 if no close trades
    exposure_pct: float         # fraction of snapshots with open positions
    journal: tuple[PaperOrderRecord, ...]
    generated_at: str

    @property
    def is_profitable(self) -> bool:
        return self.realized_pnl > 0.0

    @property
    def close_trades(self) -> int:
        return self.wins + self.losses
