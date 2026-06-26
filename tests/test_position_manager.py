import pytest

from core.position import PositionManager, PositionSide


def test_open_long_position():
    manager = PositionManager()

    position = manager.open_position(
        ticker="SBER",
        strategy_name="TREND_UP_SMA_CONFIRM",
        side="LONG",
        quantity=10,
        price=250,
    )

    assert position.ticker == "SBER"
    assert position.side == PositionSide.LONG
    assert position.quantity == 10
    assert position.average_price == 250
    assert position.entry_price == 250
    assert position.current_price == 250
    assert position.realized_pnl == 0
    assert position.unrealized_pnl == 0


def test_open_short_position():
    manager = PositionManager()

    position = manager.open_position(
        ticker="GAZP",
        strategy_name="RSI_OVERSOLD_NOT_DOWNTREND",
        side=PositionSide.SHORT,
        quantity=5,
        price=180,
    )

    assert position.ticker == "GAZP"
    assert position.side == PositionSide.SHORT
    assert position.quantity == 5
    assert position.average_price == 180


def test_add_to_position_recalculates_average_price():
    manager = PositionManager()
    manager.open_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        quantity=10,
        price=100,
    )

    position = manager.add_to_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        quantity=10,
        price=120,
    )

    assert position.quantity == 20
    assert position.average_price == 110
    assert position.current_price == 120


def test_reduce_long_position_calculates_realized_pnl():
    manager = PositionManager()
    manager.open_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        quantity=10,
        price=100,
    )

    result = manager.reduce_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        quantity=4,
        price=125,
    )

    position = manager.get_position(ticker="SBER", strategy_name="TREND", side="LONG")

    assert result.realized_pnl == 100
    assert result.closed_quantity == 4
    assert result.remaining_quantity == 6
    assert position is not None
    assert position.quantity == 6
    assert position.realized_pnl == 100
    assert position.unrealized_pnl == 150


def test_reduce_short_position_calculates_realized_pnl():
    manager = PositionManager()
    manager.open_position(
        ticker="GAZP",
        strategy_name="SHORT_REVERSION",
        side="SHORT",
        quantity=10,
        price=200,
    )

    result = manager.reduce_position(
        ticker="GAZP",
        strategy_name="SHORT_REVERSION",
        side="SHORT",
        quantity=3,
        price=180,
    )

    position = manager.get_position(ticker="GAZP", strategy_name="SHORT_REVERSION", side="SHORT")

    assert result.realized_pnl == 60
    assert result.remaining_quantity == 7
    assert position is not None
    assert position.quantity == 7
    assert position.realized_pnl == 60
    assert position.unrealized_pnl == 140


def test_close_position_removes_open_position():
    manager = PositionManager()
    manager.open_position(
        ticker="LKOH",
        strategy_name="SWING",
        side="LONG",
        quantity=2,
        price=7000,
    )

    result = manager.close_position(
        ticker="LKOH",
        strategy_name="SWING",
        side="LONG",
        price=7100,
    )

    assert result.realized_pnl == 200
    assert result.remaining_quantity == 0
    assert manager.get_position(ticker="LKOH", strategy_name="SWING", side="LONG") is None
    assert manager.list_positions() == []


def test_update_market_price_refreshes_unrealized_pnl():
    manager = PositionManager()
    manager.open_position(
        ticker="OZON",
        strategy_name="MOMENTUM",
        side="LONG",
        quantity=3,
        price=3000,
    )

    position = manager.update_market_price(
        ticker="OZON",
        strategy_name="MOMENTUM",
        side="LONG",
        price=3150,
    )

    assert position.current_price == 3150
    assert position.unrealized_pnl == 450
    assert position.total_pnl == 450


def test_open_position_with_same_key_increases_existing_position():
    manager = PositionManager()

    manager.open_position(
        ticker="afks",
        strategy_name="TREND",
        side="LONG",
        quantity=10,
        price=20,
    )
    position = manager.open_position(
        ticker="AFKS",
        strategy_name="TREND",
        side="LONG",
        quantity=30,
        price=40,
    )

    assert len(manager.list_positions()) == 1
    assert position.ticker == "AFKS"
    assert position.quantity == 40
    assert position.average_price == 35


def test_manager_rejects_invalid_side():
    manager = PositionManager()

    with pytest.raises(ValueError):
        manager.open_position(
            ticker="SBER",
            strategy_name="TREND",
            side="BUY",
            quantity=1,
            price=100,
        )


def test_manager_rejects_oversized_reduction():
    manager = PositionManager()
    manager.open_position(
        ticker="SBER",
        strategy_name="TREND",
        side="LONG",
        quantity=1,
        price=100,
    )

    with pytest.raises(ValueError):
        manager.reduce_position(
            ticker="SBER",
            strategy_name="TREND",
            side="LONG",
            quantity=2,
            price=100,
        )
