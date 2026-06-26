"""Domain models for the Risk Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskDecisionType(str, Enum):
    """Possible outcomes of a risk check."""

    ALLOW = "ALLOW"
    REJECT = "REJECT"


class RiskReason(str, Enum):
    """Discrete reasons for a REJECT decision."""

    MAX_TRADE_VALUE_EXCEEDED = "MAX_TRADE_VALUE_EXCEEDED"
    MAX_POSITION_VALUE_EXCEEDED = "MAX_POSITION_VALUE_EXCEEDED"
    MAX_POSITION_PCT_EXCEEDED = "MAX_POSITION_PCT_EXCEEDED"
    MAX_OPEN_POSITIONS_EXCEEDED = "MAX_OPEN_POSITIONS_EXCEEDED"
    SHORT_NOT_ALLOWED = "SHORT_NOT_ALLOWED"


@dataclass(frozen=True)
class RiskLimits:
    """Portfolio-level and per-trade risk limits."""

    max_trade_value: float = float("inf")
    max_position_value: float = float("inf")
    max_position_pct: float = 1.0
    max_open_positions: int = 100
    allow_short: bool = False

    def __post_init__(self) -> None:
        if self.max_trade_value <= 0:
            raise ValueError("max_trade_value must be > 0")
        if self.max_position_value <= 0:
            raise ValueError("max_position_value must be > 0")
        if not (0.0 < self.max_position_pct <= 1.0):
            raise ValueError("max_position_pct must be in (0.0, 1.0]")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be > 0")


@dataclass(frozen=True)
class RiskCheckRequest:
    """All context required for one pre-trade risk evaluation."""

    side: str                      # "BUY" or "SELL"
    ticker: str
    strategy_name: str
    quantity: int
    price: float
    current_position_value: float  # market value of existing position for this (strategy, ticker)
    open_positions_count: int      # total number of open positions in the portfolio
    portfolio_equity: float        # current equity (cash + market value of all positions)


@dataclass(frozen=True)
class RiskDecision:
    """Deterministic outcome of a risk check."""

    decision: RiskDecisionType
    reasons: tuple[RiskReason, ...] = field(default_factory=tuple)

    @property
    def allowed(self) -> bool:
        return self.decision == RiskDecisionType.ALLOW

    @classmethod
    def allow(cls) -> RiskDecision:
        return cls(decision=RiskDecisionType.ALLOW, reasons=())

    @classmethod
    def reject(cls, *reasons: RiskReason) -> RiskDecision:
        return cls(decision=RiskDecisionType.REJECT, reasons=reasons)
