from core.persistence import MemoryPositionRepository
from core.position import PositionManager


def test_position_manager_saves_position_to_repository():
    repository = MemoryPositionRepository()
    manager = PositionManager(position_repository=repository)

    manager.open_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        quantity=10,
        price=250,
    )

    stored = repository.get(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
    )

    assert stored is not None
    assert stored.ticker == "SBER"
    assert stored.quantity == 10
    assert stored.average_price == 250


def test_position_manager_updates_position_in_repository():
    repository = MemoryPositionRepository()
    manager = PositionManager(position_repository=repository)

    manager.open_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        quantity=10,
        price=100,
    )
    manager.add_to_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        quantity=10,
        price=120,
    )

    stored = repository.get(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
    )

    assert stored is not None
    assert stored.quantity == 20
    assert stored.average_price == 110


def test_position_manager_deletes_closed_position_from_repository():
    repository = MemoryPositionRepository()
    manager = PositionManager(position_repository=repository)

    manager.open_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        quantity=10,
        price=100,
    )
    manager.close_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        price=105,
    )

    assert repository.get(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
    ) is None