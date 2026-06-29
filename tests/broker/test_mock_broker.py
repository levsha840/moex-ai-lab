"""M12.5 — MockBroker full coverage tests (20 tests).

Also implicitly tests the BrokerInterface contract.
"""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.broker.adapters.mock_broker import MockBroker
from services.broker.broker_models import (
    OrderRequest, OrderSide, OrderType, OrderStatus,
    BrokerNotConnectedError,
)


def _request(instrument="SBER", quantity=1, price=258.0, side=OrderSide.BUY,
             strategy_id="STRAT_A", cycle_id="cycle_0001"):
    return OrderRequest(
        instrument=instrument,
        side=side,
        quantity=quantity,
        price=price,
        strategy_id=strategy_id,
        cycle_id=cycle_id,
    )


class TestMockBrokerImport:
    def test_importable(self):
        from services.broker.adapters.mock_broker import MockBroker
        assert MockBroker is not None

    def test_is_broker_interface(self):
        from services.broker.broker_interface import BrokerInterface
        assert issubclass(MockBroker, BrokerInterface)


class TestLifecycle:
    def test_not_connected_at_init(self):
        b = MockBroker()
        assert not b.is_connected

    def test_connect_returns_true(self):
        b = MockBroker()
        assert b.connect() is True
        assert b.is_connected

    def test_disconnect(self):
        b = MockBroker()
        b.connect()
        b.disconnect()
        assert not b.is_connected

    def test_is_sandbox_true(self):
        b = MockBroker()
        assert b.is_sandbox is True

    def test_broker_name(self):
        assert MockBroker().broker_name == "MockBroker"

    def test_raises_if_not_connected(self):
        b = MockBroker()
        with pytest.raises(BrokerNotConnectedError):
            b.get_account()


class TestAccount:
    def test_get_account(self):
        b = MockBroker()
        b.connect()
        acc = b.get_account()
        assert acc.account_id != ""
        assert acc.account_type == "sandbox"

    def test_get_balance_initial(self):
        b = MockBroker(initial_balance_rub=500_000.0)
        b.connect()
        balances = b.get_balance()
        assert len(balances) == 1
        assert balances[0].currency == "RUB"
        assert balances[0].available == 500_000.0

    def test_get_positions_empty(self):
        b = MockBroker()
        b.connect()
        assert b.get_positions() == []


class TestPlaceOrder:
    def test_place_buy_returns_filled(self):
        b = MockBroker()
        b.connect()
        order = b.place_order(_request())
        assert order.status == OrderStatus.FILLED
        assert order.order_id.startswith("MOCK-")

    def test_place_order_has_strategy(self):
        b = MockBroker()
        b.connect()
        req = _request(strategy_id="BB_SQUEEZE", cycle_id="cycle_0005")
        order = b.place_order(req)
        assert order.strategy_id == "BB_SQUEEZE"
        assert order.cycle_id == "cycle_0005"

    def test_buy_creates_position(self):
        b = MockBroker()
        b.connect()
        b.place_order(_request(quantity=10, price=258.0))
        positions = b.get_positions()
        assert len(positions) == 1
        assert positions[0].instrument == "SBER"
        assert positions[0].quantity == 10

    def test_buy_reduces_balance(self):
        b = MockBroker(initial_balance_rub=100_000.0)
        b.connect()
        b.place_order(_request(quantity=10, price=100.0))
        bal = b.get_balance()[0].available
        assert bal < 100_000.0

    def test_sell_removes_position(self):
        b = MockBroker()
        b.connect()
        b.place_order(_request(quantity=5))
        b.place_order(_request(quantity=5, side=OrderSide.SELL))
        assert len(b.get_positions()) == 0

    def test_sell_increases_balance(self):
        b = MockBroker(initial_balance_rub=0.0)
        b.connect()
        # Seed a position artificially
        from services.broker.broker_models import Position
        b._positions["GAZP"] = Position("GAZP", 10, 170.0, 170.0)
        req = _request(instrument="GAZP", quantity=10, price=170.0, side=OrderSide.SELL)
        b.place_order(req)
        assert b.get_balance()[0].available > 0

    def test_market_order_uses_market_price(self):
        b = MockBroker(market_price=300.0)
        b.connect()
        req = OrderRequest(
            instrument="SBER", side=OrderSide.BUY,
            quantity=1, price=0.0, order_type=OrderType.MARKET,
        )
        order = b.place_order(req)
        assert order.avg_price == 300.0


class TestCancelOrder:
    def test_cancel_nonexistent_returns_false(self):
        b = MockBroker()
        b.connect()
        assert b.cancel_order("NONEXISTENT") is False

    def test_cannot_cancel_filled_order(self):
        b = MockBroker()
        b.connect()
        order = b.place_order(_request())
        assert order.status == OrderStatus.FILLED
        assert b.cancel_order(order.order_id) is False


class TestGetOrders:
    def test_get_orders_empty(self):
        b = MockBroker()
        b.connect()
        assert b.get_orders() == []

    def test_get_orders_after_place(self):
        b = MockBroker()
        b.connect()
        b.place_order(_request())
        assert len(b.get_orders()) == 1

    def test_get_trades_only_filled(self):
        b = MockBroker()
        b.connect()
        b.place_order(_request())
        trades = b.get_trades()
        assert all(t.status == OrderStatus.FILLED for t in trades)

    def test_get_order_by_id(self):
        b = MockBroker()
        b.connect()
        order = b.place_order(_request())
        found = b.get_order(order.order_id)
        assert found is not None
        assert found.order_id == order.order_id

    def test_get_order_nonexistent(self):
        b = MockBroker()
        b.connect()
        assert b.get_order("X") is None


class TestHealth:
    def test_health_offline(self):
        b = MockBroker()
        h = b.health()
        assert h["overall"] == "OFFLINE"
        assert h["connected"] is False

    def test_health_connected(self):
        b = MockBroker()
        b.connect()
        h = b.health()
        assert h["overall"] == "OK"
        assert h["sandbox_mode"] is True
