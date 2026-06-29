"""M12.5 — MockBroker: in-memory broker for testing and offline use.

No external calls. No SDK dependency. Fully deterministic.

place_order() immediately fills LIMIT orders at the requested price.
cancel_order() cancels any ACCEPTED or PENDING order.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from ..broker_interface import BrokerInterface
from ..broker_models import (
    Balance,
    BrokerAccount,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _order_id() -> str:
    return f"MOCK-{uuid.uuid4().hex[:8].upper()}"


class MockBroker(BrokerInterface):
    """In-memory broker. Suitable for unit tests, dry-run, and offline CI.

    Simulates an immediate fill at the requested price (LIMIT) or at
    `market_price` (MARKET, default 100.0 per lot).
    """

    def __init__(
        self,
        initial_balance_rub: float = 1_000_000.0,
        market_price: float = 100.0,
    ) -> None:
        self._balance_rub = initial_balance_rub
        self._market_price = market_price
        self._connected = False
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}
        self._lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_sandbox(self) -> bool:
        return True   # MockBroker is always safe

    @property
    def broker_name(self) -> str:
        return "MockBroker"

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def health(self) -> dict:
        return {
            "connected":          self._connected,
            "sandbox_mode":       True,
            "latency_ms":         0.0,
            "last_heartbeat":     _now(),
            "account_accessible": self._connected,
            "overall":            "OK" if self._connected else "OFFLINE",
        }

    # ── Account ───────────────────────────────────────────────────────────────

    def get_account(self) -> BrokerAccount:
        self._assert_connected()
        return BrokerAccount(
            account_id="MOCK-ACCOUNT-0001",
            name="Mock Sandbox Account",
            account_type="sandbox",
            status="active",
        )

    def get_positions(self) -> list[Position]:
        self._assert_connected()
        with self._lock:
            return list(self._positions.values())

    def get_balance(self) -> list[Balance]:
        self._assert_connected()
        return [Balance(currency="RUB", available=self._balance_rub)]

    # ── Orders ────────────────────────────────────────────────────────────────

    def place_order(self, request: OrderRequest) -> Order:
        self._assert_connected()

        fill_price = (
            request.price if request.order_type == OrderType.LIMIT and request.price > 0
            else self._market_price
        )
        commission = round(fill_price * request.quantity * 0.001, 4)  # 0.1% mock commission
        now = _now()
        oid = _order_id()

        order = Order(
            order_id=oid,
            instrument=request.instrument,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            order_type=request.order_type,
            status=OrderStatus.FILLED,     # immediate fill
            created_at=now,
            updated_at=now,
            filled_quantity=request.quantity,
            avg_price=fill_price,
            commission=commission,
            strategy_id=request.strategy_id,
            cycle_id=request.cycle_id,
            broker_response={"mock": True, "fill_price": fill_price},
        )

        cost = fill_price * request.quantity
        with self._lock:
            self._orders[oid] = order
            # Update balance
            if request.side == OrderSide.BUY:
                self._balance_rub -= (cost + commission)
                pos = self._positions.get(request.instrument)
                if pos:
                    # Average up
                    total_qty = pos.quantity + request.quantity
                    pos.avg_price = (pos.avg_price * pos.quantity + fill_price * request.quantity) / total_qty
                    pos.quantity = total_qty
                else:
                    self._positions[request.instrument] = Position(
                        instrument=request.instrument,
                        quantity=request.quantity,
                        avg_price=fill_price,
                        current_price=fill_price,
                    )
            else:  # SELL
                self._balance_rub += (cost - commission)
                pos = self._positions.get(request.instrument)
                if pos:
                    pos.quantity -= request.quantity
                    if pos.quantity <= 0:
                        del self._positions[request.instrument]

        return order

    def cancel_order(self, order_id: str) -> bool:
        self._assert_connected()
        with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                return False
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                return False
            order.status = OrderStatus.CANCELLED
            order.updated_at = _now()
            return True

    def get_order(self, order_id: str) -> Order | None:
        self._assert_connected()
        return self._orders.get(order_id)

    def get_orders(self) -> list[Order]:
        self._assert_connected()
        with self._lock:
            return list(self._orders.values())

    def get_trades(self) -> list[Order]:
        self._assert_connected()
        with self._lock:
            return [o for o in self._orders.values() if o.status == OrderStatus.FILLED]

    # ── Test helpers ──────────────────────────────────────────────────────────

    def set_balance(self, amount: float) -> None:
        self._balance_rub = amount

    def clear(self) -> None:
        """Reset all state (for test isolation)."""
        with self._lock:
            self._orders.clear()
            self._positions.clear()
            self._balance_rub = 1_000_000.0

    # ── Internal ──────────────────────────────────────────────────────────────

    def _assert_connected(self) -> None:
        from ..broker_models import BrokerNotConnectedError
        if not self._connected:
            raise BrokerNotConnectedError("MockBroker: call connect() first")
