"""Common strategy signal model for MOEX AI LAB."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalAction(str, Enum):
    """Canonical strategy actions."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Signal:
    """A normalized trading signal produced by any strategy."""

    action: SignalAction
    ticker: str
    ts: Any
    strategy_name: str
    confidence: float = 1.0
    reason: str = ""
    price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not self.ticker:
            raise ValueError("ticker is required")
        if not self.strategy_name:
            raise ValueError("strategy_name is required")

    @classmethod
    def hold(
        cls,
        *,
        ticker: str,
        ts: Any,
        strategy_name: str,
        reason: str = "",
        price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "Signal":
        return cls(
            action=SignalAction.HOLD,
            ticker=ticker,
            ts=ts,
            strategy_name=strategy_name,
            confidence=1.0,
            reason=reason,
            price=price,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class OrderIntent:
    """Intent to be consumed later by paper/live execution layers."""

    action: SignalAction
    ticker: str
    ts: Any
    strategy_name: str
    price: float | None = None
    quantity: int | None = None
    confidence: float = 1.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
