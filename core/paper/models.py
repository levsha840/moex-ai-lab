"""Domain models for the paper trading execution layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PaperOrderSide(str, Enum):
    """Supported paper order sides."""

    BUY = "BUY"
    SELL = "SELL"


class PaperOrderStatus(str, Enum):
    """Lifecycle states for virtual orders."""

    FILLED = "FILLED"
    REJECTED = "REJECTED"


class PaperPositionStatus(str, Enum):
    """Lifecycle states for paper positions."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class PaperExecutionConfig:
    """Execution parameters for deterministic paper trading."""

    initial_cash: float = 1_000_000.0
    default_quantity: int = 1
    commission_rate: float = 0.0005
    min_commission: float = 0.0
    slippage_bps: float = 0.0
    allow_short: bool = False
    reject_on_insufficient_cash: bool = True

    def __post_init__(self) -> None:
        if self.initial_cash < 0:
            raise ValueError("initial_cash must be >= 0")
        if self.default_quantity <= 0:
            raise ValueError("default_quantity must be > 0")
        if self.commission_rate < 0:
            raise ValueError("commission_rate must be >= 0")
        if self.min_commission < 0:
            raise ValueError("min_commission must be >= 0")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be >= 0")


@dataclass(frozen=True)
class PaperOrder:
    """Virtual order created from a strategy signal."""

    order_id: str
    strategy_name: str
    ticker: str
    ts: Any
    side: PaperOrderSide
    quantity: int
    requested_price: float
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperTrade:
    """Executed paper trade."""

    trade_id: str
    order_id: str
    strategy_name: str
    ticker: str
    ts: Any
    side: PaperOrderSide
    quantity: int
    price: float
    gross_value: float
    commission: float
    slippage: float
    cash_delta: float
    realized_pnl: float = 0.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperRejectedOrder:
    """Rejected virtual order with a stable reason."""

    order: PaperOrder
    status: PaperOrderStatus
    reason: str


@dataclass
class PaperPosition:
    """Aggregated long position per strategy and ticker."""

    strategy_name: str
    ticker: str
    quantity: int = 0
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    status: PaperPositionStatus = PaperPositionStatus.CLOSED

    @property
    def market_value(self) -> float:
        return self.quantity * self.avg_price

    def mark_status(self) -> None:
        self.status = PaperPositionStatus.OPEN if self.quantity != 0 else PaperPositionStatus.CLOSED


@dataclass(frozen=True)
class PaperPortfolioSnapshot:
    """Point-in-time account state."""

    ts: Any
    cash: float
    equity: float
    market_value: float
    realized_pnl: float
    unrealized_pnl: float
    positions: tuple[PaperPosition, ...]


@dataclass(frozen=True)
class PaperExecutionResult:
    """Result of processing a signal/order."""

    order: PaperOrder | None
    trade: PaperTrade | None
    rejected: PaperRejectedOrder | None
    snapshot: PaperPortfolioSnapshot

    @property
    def filled(self) -> bool:
        return self.trade is not None
