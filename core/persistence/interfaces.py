from typing import Protocol

from core.position.models import Position, PositionSide


class PositionRepository(Protocol):
    """Storage interface for trading positions."""

    def save(self, position: Position) -> None:
        """Save or update position."""

    def get(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
    ) -> Position | None:
        """Return position if it exists."""

    def delete(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
    ) -> None:
        """Delete position if it exists."""

    def list_all(self) -> list[Position]:
        """Return all stored positions."""