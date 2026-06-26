"""
Domain models for the position management layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class PositionSide(str, Enum):
    """Supported trading position directions."""

    LONG = "LONG"
    SHORT = "SHORT"

    @classmethod
    def normalize(cls, value: "PositionSide | str") -> "PositionSide":
        if isinstance(value, cls):
            return value

        normalized = str(value).upper().strip()
        try:
            return cls(normalized)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(f"Unsupported position side: {value!r}. Allowed: {allowed}") from exc


@dataclass(frozen=True)
class PositionCloseResult:
    """Result returned after a partial or full position reduction."""

    ticker: str
    strategy_name: str
    side: PositionSide
    closed_quantity: float
    exit_price: float
    realized_pnl: float
    remaining_quantity: float
    closed_at: datetime


@dataclass
class Position:
    """Current state of an opened trading position."""

    ticker: str
    strategy_name: str
    side: PositionSide
    quantity: float
    average_price: float
    current_price: float
    realized_pnl: float
    opened_at: datetime
    updated_at: datetime

    @property
    def entry_price(self) -> float:
        """Backward-compatible alias for the current average entry price."""

        return self.average_price

    @property
    def unrealized_pnl(self) -> float:
        """Calculate open PnL from current market price."""

        if self.side == PositionSide.LONG:
            return (self.current_price - self.average_price) * self.quantity

        return (self.average_price - self.current_price) * self.quantity

    @property
    def total_pnl(self) -> float:
        """Realized plus unrealized PnL."""

        return self.realized_pnl + self.unrealized_pnl

    @property
    def market_value(self) -> float:
        """Absolute market value of the open position."""

        return self.quantity * self.current_price

    def snapshot(self) -> dict[str, object]:
        """Return a serializable snapshot for logs, reports and future persistence."""

        return {
            "ticker": self.ticker,
            "strategy_name": self.strategy_name,
            "side": self.side.value,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "current_price": self.current_price,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "market_value": self.market_value,
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
