"""M12.5 — Broker domain model tests (10 tests)."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.broker.broker_models import (
    OrderSide, OrderType, OrderStatus,
    OrderRequest, Order, Position, Balance, BrokerAccount,
    BrokerError, BrokerUnavailableError, BrokerNotConnectedError, RiskViolationError,
)


class TestEnums:
    def test_order_side_values(self):
        assert OrderSide.BUY == "BUY"
        assert OrderSide.SELL == "SELL"

    def test_order_type_values(self):
        assert OrderType.LIMIT == "LIMIT"
        assert OrderType.MARKET == "MARKET"

    def test_order_status_values(self):
        assert set(s.value for s in OrderStatus) == {
            "PENDING", "ACCEPTED", "FILLED", "PARTIAL", "CANCELLED", "REJECTED"
        }

    def test_enums_are_strings(self):
        assert isinstance(OrderSide.BUY, str)
        assert isinstance(OrderStatus.FILLED, str)


class TestOrderRequest:
    def test_create_minimal(self):
        req = OrderRequest(instrument="SBER", side=OrderSide.BUY, quantity=1, price=258.0)
        assert req.instrument == "SBER"
        assert req.quantity == 1
        assert req.order_type == OrderType.LIMIT

    def test_strategy_id_defaults(self):
        req = OrderRequest(instrument="GAZP", side=OrderSide.SELL, quantity=5, price=170.0)
        assert req.strategy_id == ""
        assert req.cycle_id == ""


class TestOrder:
    def test_to_dict(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        order = Order(
            order_id="TEST-001",
            instrument="SBER",
            side=OrderSide.BUY,
            quantity=2,
            price=258.0,
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            created_at=now,
            updated_at=now,
            filled_quantity=2,
            avg_price=258.0,
        )
        d = order.to_dict()
        assert d["order_id"] == "TEST-001"
        assert d["side"] == "BUY"
        assert d["status"] == "FILLED"
        assert "broker_response" in d


class TestBalance:
    def test_total_property(self):
        b = Balance(currency="RUB", available=900.0, blocked=100.0)
        assert b.total == 1000.0

    def test_to_dict(self):
        b = Balance(currency="RUB", available=500.0)
        d = b.to_dict()
        assert d["currency"] == "RUB"
        assert d["total"] == 500.0


class TestExceptions:
    def test_risk_violation_has_rule(self):
        exc = RiskViolationError("kill_switch", "Kill switch ON")
        assert exc.rule == "kill_switch"
        assert "kill_switch" in str(exc)

    def test_exception_hierarchy(self):
        assert issubclass(BrokerUnavailableError, BrokerError)
        assert issubclass(BrokerNotConnectedError, BrokerError)
        assert issubclass(RiskViolationError, BrokerError)
