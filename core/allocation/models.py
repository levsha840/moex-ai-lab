from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AllocationDecisionType(str, Enum):
    ALLOCATE = "ALLOCATE"
    REDUCE = "REDUCE"
    REJECT = "REJECT"


class AllocationReason(str, Enum):
    APPROVED = "APPROVED"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    MAX_POSITION_PCT_EXCEEDED = "MAX_POSITION_PCT_EXCEEDED"
    MAX_STRATEGY_PCT_EXCEEDED = "MAX_STRATEGY_PCT_EXCEEDED"
    MAX_CORRELATED_PCT_EXCEEDED = "MAX_CORRELATED_PCT_EXCEEDED"
    CASH_BUFFER_REQUIRED = "CASH_BUFFER_REQUIRED"
    INVALID_REQUEST = "INVALID_REQUEST"


@dataclass(frozen=True)
class AllocationConfig:
    max_position_pct: float = 0.10
    max_strategy_pct: float = 0.30
    max_correlated_pct: float = 0.30
    cash_buffer: float = 0.05
    rebalance_threshold: float = 0.02


@dataclass(frozen=True)
class AllocationRequest:
    ticker: str
    strategy_name: str
    price: float
    requested_quantity: float
    cash: float
    portfolio_value: float
    current_position_value: float = 0.0
    strategy_exposure: float = 0.0
    correlated_exposure: float = 0.0


@dataclass(frozen=True)
class AllocationDecision:
    decision: AllocationDecisionType
    approved_quantity: float
    reasons: tuple[AllocationReason, ...]
