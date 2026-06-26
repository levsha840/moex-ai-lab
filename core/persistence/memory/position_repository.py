from copy import deepcopy

from core.persistence.interfaces import PositionRepository
from core.position.models import Position, PositionSide


PositionKey = tuple[str, str, PositionSide]


class MemoryPositionRepository(PositionRepository):
    """In-memory implementation of position repository."""

    def __init__(self) -> None:
        self._positions: dict[PositionKey, Position] = {}

    def save(self, position: Position) -> None:
        """Save or update position."""

        self._positions[self._make_key(
            ticker=position.ticker,
            strategy_name=position.strategy_name,
            side=position.side,
        )] = deepcopy(position)

    def get(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
    ) -> Position | None:
        """Return position if it exists."""

        key = self._make_key(
            ticker=ticker,
            strategy_name=strategy_name,
            side=PositionSide.normalize(side),
        )
        position = self._positions.get(key)

        if position is None:
            return None

        return deepcopy(position)

    def delete(
        self,
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide | str,
    ) -> None:
        """Delete position if it exists."""

        self._positions.pop(
            self._make_key(
                ticker=ticker,
                strategy_name=strategy_name,
                side=PositionSide.normalize(side),
            ),
            None,
        )

    def list_all(self) -> list[Position]:
        """Return all stored positions."""

        return [
            deepcopy(position)
            for position in sorted(
                self._positions.values(),
                key=lambda item: (item.strategy_name, item.ticker, item.side.value),
            )
        ]

    @staticmethod
    def _make_key(
        *,
        ticker: str,
        strategy_name: str,
        side: PositionSide,
    ) -> PositionKey:
        return (strategy_name.strip(), ticker.upper().strip(), side)