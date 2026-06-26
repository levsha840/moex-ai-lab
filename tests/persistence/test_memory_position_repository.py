from datetime import datetime, timezone

from core.persistence import MemoryPositionRepository
from core.position.models import Position, PositionSide


def make_position() -> Position:
    now = datetime.now(timezone.utc)
    return Position(
        ticker="SBER",
        strategy_name="TREND",
        side=PositionSide.LONG,
        quantity=10,
        average_price=250,
        current_price=255,
        realized_pnl=0,
        opened_at=now,
        updated_at=now,
    )


def test_save_and_get_position():
    repository = MemoryPositionRepository()
    position = make_position()

    repository.save(position)

    stored = repository.get(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
    )

    assert stored is not None
    assert stored.ticker == "SBER"
    assert stored.strategy_name == "TREND"
    assert stored.side == PositionSide.LONG
    assert stored.quantity == 10


def test_repository_returns_copy_not_original_object():
    repository = MemoryPositionRepository()
    position = make_position()
    repository.save(position)

    stored = repository.get(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
    )
    assert stored is not None

    stored.quantity = 999

    stored_again = repository.get(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
    )

    assert stored_again is not None
    assert stored_again.quantity == 10


def test_delete_position():
    repository = MemoryPositionRepository()
    repository.save(make_position())

    repository.delete(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
    )

    assert repository.get(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
    ) is None


def test_list_all_positions_sorted():
    repository = MemoryPositionRepository()
    first = make_position()
    second = make_position()
    second.ticker = "GAZP"
    second.strategy_name = "MEAN_REVERSION"

    repository.save(first)
    repository.save(second)

    positions = repository.list_all()

    assert [position.ticker for position in positions] == ["GAZP", "SBER"]