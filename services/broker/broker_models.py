"""M12.5 — Broker domain models.

All types are plain Python — no SDK imports here.
These models cross the BrokerInterface boundary in both directions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Enums ────────────────────────────────────────────────────────────────────

class OrderSide(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT  = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(str, Enum):
    PENDING   = "PENDING"    # created, not yet sent
    ACCEPTED  = "ACCEPTED"   # broker accepted, awaiting fill
    FILLED    = "FILLED"     # fully executed
    PARTIAL   = "PARTIAL"    # partially filled
    CANCELLED = "CANCELLED"  # cancelled
    REJECTED  = "REJECTED"   # rejected by broker or risk guard


# ── Core models ───────────────────────────────────────────────────────────────

@dataclass
class OrderRequest:
    """Input to BrokerInterface.place_order(). Pure data, no defaults for required fields."""
    instrument: str            # FIGI or ticker (broker-specific)
    side: OrderSide
    quantity: int              # lots / shares
    price: float               # 0.0 for MARKET orders
    order_type: OrderType = OrderType.LIMIT
    strategy_id: str = ""
    cycle_id: str = ""
    comment: str = ""


@dataclass
class Order:
    """Represents a broker order (submitted or historical)."""
    order_id: str
    instrument: str
    side: OrderSide
    quantity: int
    price: float
    order_type: OrderType
    status: OrderStatus
    created_at: str
    updated_at: str
    filled_quantity: int = 0
    avg_price: float = 0.0
    commission: float = 0.0
    strategy_id: str = ""
    cycle_id: str = ""
    broker_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id":        self.order_id,
            "instrument":      self.instrument,
            "side":            self.side.value,
            "quantity":        self.quantity,
            "price":           self.price,
            "order_type":      self.order_type.value,
            "status":          self.status.value,
            "created_at":      self.created_at,
            "updated_at":      self.updated_at,
            "filled_quantity":  self.filled_quantity,
            "avg_price":       self.avg_price,
            "commission":      self.commission,
            "strategy_id":     self.strategy_id,
            "cycle_id":        self.cycle_id,
            "broker_response": self.broker_response,
        }


@dataclass
class Position:
    """An open position in the broker account."""
    instrument: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "instrument":    self.instrument,
            "quantity":      self.quantity,
            "avg_price":     self.avg_price,
            "current_price": self.current_price,
            "pnl":           round(self.pnl, 4),
            "pnl_pct":       round(self.pnl_pct, 6),
        }


@dataclass
class Balance:
    """Cash balance in a single currency."""
    currency: str
    available: float
    blocked: float = 0.0

    @property
    def total(self) -> float:
        return self.available + self.blocked

    def to_dict(self) -> dict:
        return {
            "currency":  self.currency,
            "available": round(self.available, 2),
            "blocked":   round(self.blocked, 2),
            "total":     round(self.total, 2),
        }


@dataclass
class BrokerAccount:
    """Broker account metadata."""
    account_id: str
    name: str
    account_type: str    # "sandbox", "broker", "iis"
    status: str = "active"

    def to_dict(self) -> dict:
        return {
            "account_id":   self.account_id,
            "name":         self.name,
            "account_type": self.account_type,
            "status":       self.status,
        }


# ── Exceptions ────────────────────────────────────────────────────────────────

class BrokerError(Exception):
    """Base exception for all broker errors."""


class BrokerUnavailableError(BrokerError):
    """Raised when the broker SDK or connection is unavailable."""


class BrokerNotConnectedError(BrokerError):
    """Raised when a broker method is called before connect()."""


class RiskViolationError(BrokerError):
    """Raised by RiskGuard when an order violates a risk rule.

    Attributes:
        rule:   name of the violated rule
        reason: human-readable explanation
    """
    def __init__(self, rule: str, reason: str) -> None:
        super().__init__(f"[{rule}] {reason}")
        self.rule = rule
        self.reason = reason
