"""
Position Manager for MOEX AI LAB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from core.position.models import Position, PositionCloseResult, PositionSide

if TYPE_CHECKING:
    from core.persistence.interfaces import PositionRepository

PositionKey = tuple[str, str, PositionSide]


class PositionManager:
    """Manage opened LONG and SHORT positions per strategy/ticker/side."""

    def __init__(self, position_repository: "PositionRepository | None" = None) -> None:
        self._positions: dict[PositionKey, Position] = {}
        self._repository = position_repository

    def open_position(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
        quantity: float,
        price: float,
        timestamp: datetime | None = None,
    ) -> Position:
        """Open a new position or increase an existing one."""

        normalized_side = PositionSide.normalize(side)
        self._validate_identity(ticker=ticker, strategy_name=strategy_name)
        self._validate_positive_number(quantity, "quantity")
        self._validate_positive_number(price, "price")

        key = self._make_key(ticker, strategy_name, normalized_side)
        now = self._resolve_timestamp(timestamp)

        if self._get_position_by_key(key) is not None:
            return self.add_to_position(
                ticker=ticker,
                strategy_name=strategy_name,
                side=normalized_side,
                quantity=quantity,
                price=price,
                timestamp=now,
            )

        position = Position(
            ticker=ticker.upper().strip(),
            strategy_name=strategy_name.strip(),
            side=normalized_side,
            quantity=float(quantity),
            average_price=float(price),
            current_price=float(price),
            realized_pnl=0.0,
            opened_at=now,
            updated_at=now,
        )
        self._save_position(key, position)
        return position

    def add_to_position(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
        quantity: float,
        price: float,
        timestamp: datetime | None = None,
    ) -> Position:
        """Increase an existing position and recalculate weighted average price."""

        normalized_side = PositionSide.normalize(side)
        self._validate_positive_number(quantity, "quantity")
        self._validate_positive_number(price, "price")

        key = self._make_key(ticker, strategy_name, normalized_side)
        position = self._require_position(ticker, strategy_name, normalized_side)
        now = self._resolve_timestamp(timestamp)

        total_cost = position.average_price * position.quantity + float(price) * float(quantity)
        total_quantity = position.quantity + float(quantity)

        position.quantity = total_quantity
        position.average_price = total_cost / total_quantity
        position.current_price = float(price)
        position.updated_at = now

        self._save_position(key, position)
        return position

    def reduce_position(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
        quantity: float,
        price: float,
        timestamp: datetime | None = None,
    ) -> PositionCloseResult:
        """Partially reduce an existing position."""

        normalized_side = PositionSide.normalize(side)
        self._validate_positive_number(quantity, "quantity")
        self._validate_positive_number(price, "price")

        key = self._make_key(ticker, strategy_name, normalized_side)
        position = self._require_position(ticker, strategy_name, normalized_side)

        if quantity > position.quantity:
            raise ValueError(
                f"Cannot reduce {quantity} units from position with "
                f"{position.quantity} units"
            )

        now = self._resolve_timestamp(timestamp)
        realized_pnl = self._calculate_realized_pnl(
            side=normalized_side,
            entry_price=position.average_price,
            exit_price=float(price),
            quantity=float(quantity),
        )

        remaining_quantity = position.quantity - float(quantity)
        position.realized_pnl += realized_pnl
        position.quantity = remaining_quantity
        position.current_price = float(price)
        position.updated_at = now

        if remaining_quantity == 0:
            self._delete_position(key)
        else:
            self._save_position(key, position)

        return PositionCloseResult(
            ticker=position.ticker,
            strategy_name=position.strategy_name,
            side=normalized_side,
            closed_quantity=float(quantity),
            exit_price=float(price),
            realized_pnl=realized_pnl,
            remaining_quantity=remaining_quantity,
            closed_at=now,
        )

    def close_position(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
        price: float,
        timestamp: datetime | None = None,
    ) -> PositionCloseResult:
        """Fully close an existing position."""

        normalized_side = PositionSide.normalize(side)
        position = self._require_position(ticker, strategy_name, normalized_side)

        return self.reduce_position(
            ticker=ticker,
            strategy_name=strategy_name,
            side=normalized_side,
            quantity=position.quantity,
            price=price,
            timestamp=timestamp,
        )

    def update_market_price(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
        price: float,
        timestamp: datetime | None = None,
    ) -> Position:
        """Update the current market price and refresh unrealized PnL."""

        normalized_side = PositionSide.normalize(side)
        self._validate_positive_number(price, "price")

        key = self._make_key(ticker, strategy_name, normalized_side)
        position = self._require_position(ticker, strategy_name, normalized_side)

        position.current_price = float(price)
        position.updated_at = self._resolve_timestamp(timestamp)

        self._save_position(key, position)
        return position

    def get_position(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
    ) -> Position | None:
        """Return an open position if it exists."""

        normalized_side = PositionSide.normalize(side)
        key = self._make_key(ticker, strategy_name, normalized_side)
        return self._get_position_by_key(key)

    def list_positions(self) -> list[Position]:
        """Return all open positions sorted for deterministic reports/tests."""

        if self._repository is not None:
            return self._repository.list_all()

        return sorted(
            self._positions.values(),
            key=lambda item: (item.strategy_name, item.ticker, item.side.value),
        )

    def has_position(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
    ) -> bool:
        """Check whether an open position exists."""

        return self.get_position(
            ticker=ticker,
            strategy_name=strategy_name,
            side=side,
        ) is not None

    def total_unrealized_pnl(self) -> float:
        """Aggregate unrealized PnL across all open positions."""

        return sum(position.unrealized_pnl for position in self.list_positions())

    def total_realized_pnl(self) -> float:
        """Aggregate realized PnL for currently open positions."""

        return sum(position.realized_pnl for position in self.list_positions())

    def snapshots(self) -> list[dict[str, object]]:
        """Return serializable snapshots for all open positions."""

        return [position.snapshot() for position in self.list_positions()]

    def _get_position_by_key(self, key: PositionKey) -> Position | None:
        if self._repository is not None:
            strategy_name, ticker, side = key
            return self._repository.get(
                ticker=ticker,
                strategy_name=strategy_name,
                side=side,
            )

        return self._positions.get(key)

    def _save_position(self, key: PositionKey, position: Position) -> None:
        if self._repository is not None:
            self._repository.save(position)
            return

        self._positions[key] = position

    def _delete_position(self, key: PositionKey) -> None:
        if self._repository is not None:
            strategy_name, ticker, side = key
            self._repository.delete(
                ticker=ticker,
                strategy_name=strategy_name,
                side=side,
            )
            return

        del self._positions[key]

    @staticmethod
    def _calculate_realized_pnl(
        *,
        side: PositionSide,
        entry_price: float,
        exit_price: float,
        quantity: float,
    ) -> float:
        if side == PositionSide.LONG:
            return (exit_price - entry_price) * quantity

        return (entry_price - exit_price) * quantity

    @staticmethod
    def _resolve_timestamp(timestamp: datetime | None) -> datetime:
        if timestamp is None:
            return datetime.now(timezone.utc)

        return timestamp

    @staticmethod
    def _validate_positive_number(value: float, field_name: str) -> None:
        if not isinstance(value, int | float):
            raise TypeError(f"{field_name} must be numeric")

        if value <= 0:
            raise ValueError(f"{field_name} must be positive")

    @staticmethod
    def _validate_identity(*, ticker: str, strategy_name: str) -> None:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError("ticker must be a non-empty string")

        if not isinstance(strategy_name, str) or not strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")

    @staticmethod
    def _make_key(
        ticker: str,
        strategy_name: str,
        side: PositionSide,
    ) -> PositionKey:
        return (strategy_name.strip(), ticker.upper().strip(), side)

    def _require_position(
        self,
        ticker: str,
        strategy_name: str,
        side: PositionSide,
    ) -> Position:
        self._validate_identity(ticker=ticker, strategy_name=strategy_name)

        position = self.get_position(
            ticker=ticker,
            strategy_name=strategy_name,
            side=side,
        )

        if position is None:
            raise KeyError(
                f"Position not found: strategy={strategy_name!r}, "
                f"ticker={ticker!r}, side={side.value}"
            )

        return position