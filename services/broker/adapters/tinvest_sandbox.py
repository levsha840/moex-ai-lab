"""M12.5 — T-Invest Sandbox Adapter.

Uses the t_tech.invest SDK (gRPC-based, installed as t_tech_investments).

SDK availability:
  The SDK requires grpcio with compiled C extensions. On Python 3.14+ the
  pre-built grpcio wheel may not have native binaries. If gRPC cannot be
  imported, this module is still importable but all methods raise
  BrokerUnavailableError with an actionable message.

Environment:
  T_INVEST_TOKEN      — sandbox token (required for real sandbox calls)
  T_INVEST_ACCOUNT_ID — sandbox account ID (optional; auto-created if empty)

SAFETY: is_sandbox always returns True. Live trading is never enabled here.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..broker_interface import BrokerInterface
from ..broker_models import (
    Balance,
    BrokerAccount,
    BrokerUnavailableError,
    BrokerNotConnectedError,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)

# ── SDK probe (lazy, at import time) ─────────────────────────────────────────

_SDK_AVAILABLE = False
_SDK_ERROR: str = ""

def _probe_sdk() -> bool:
    global _SDK_AVAILABLE, _SDK_ERROR
    # Add venv site-packages to path if needed
    _venv = Path(__file__).resolve().parents[4] / ".venv" / "Lib" / "site-packages"
    if _venv.exists() and str(_venv) not in sys.path:
        sys.path.insert(0, str(_venv))
    try:
        import grpc  # noqa: F401
        from t_tech.invest import Client  # noqa: F401
        _SDK_AVAILABLE = True
    except Exception as exc:
        _SDK_ERROR = str(exc)
        _SDK_AVAILABLE = False
    return _SDK_AVAILABLE

_probe_sdk()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TInvestSandboxAdapter(BrokerInterface):
    """T-Invest Sandbox via t_tech.invest gRPC SDK.

    Usage:
        adapter = TInvestSandboxAdapter(token=os.getenv("T_INVEST_TOKEN"))
        adapter.connect()   # opens gRPC channel, gets/creates sandbox account
        order = adapter.place_order(OrderRequest(...))
        adapter.disconnect()

    All methods raise BrokerUnavailableError if SDK is not compiled for this
    Python version. See INSTALL note in docs for how to fix.
    """

    SANDBOX_GRPC_TARGET = "sandbox-invest.tinkoff.ru:443"

    def __init__(
        self,
        token: str = "",
        account_id: str = "",
    ) -> None:
        self._token      = token or os.getenv("T_INVEST_TOKEN", "")
        self._account_id = account_id or os.getenv("T_INVEST_ACCOUNT_ID", "")
        self._connected  = False
        self._client_ctx = None    # context manager from SandboxClient
        self._services   = None    # Services object (from __enter__)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Open gRPC channel and ensure sandbox account exists.

        Raises:
            BrokerUnavailableError  — SDK gRPC not available
            BrokerError             — authentication failure or network error
        """
        if not _SDK_AVAILABLE:
            raise BrokerUnavailableError(
                f"t_tech.invest SDK unavailable: {_SDK_ERROR}\n"
                "Fix: install grpcio from source for Python 3.14, or use Python ≤3.12."
            )
        if not self._token:
            raise BrokerUnavailableError(
                "T_INVEST_TOKEN is not set. "
                "Export T_INVEST_TOKEN=<sandbox token> and retry."
            )
        try:
            venv = Path(__file__).resolve().parents[4] / ".venv" / "Lib" / "site-packages"
            if str(venv) not in sys.path:
                sys.path.insert(0, str(venv))
            from t_tech.invest import Client
            from t_tech.invest.constants import INVEST_GRPC_API_SANDBOX

            self._client_ctx = Client(
                token=self._token,
                target=INVEST_GRPC_API_SANDBOX,
            )
            self._services = self._client_ctx.__enter__()

            # Ensure sandbox account exists
            if not self._account_id:
                accounts = self._services.sandbox.get_sandbox_accounts().accounts
                if accounts:
                    self._account_id = accounts[0].id
                else:
                    resp = self._services.sandbox.open_sandbox_account()
                    self._account_id = resp.account_id

            self._connected = True
            return True
        except BrokerUnavailableError:
            raise
        except Exception as exc:
            from ..broker_models import BrokerError
            raise BrokerError(f"T-Invest sandbox connect failed: {exc}") from exc

    def disconnect(self) -> None:
        if self._client_ctx is not None:
            try:
                self._client_ctx.__exit__(None, None, None)
            except Exception:
                pass
        self._services = None
        self._client_ctx = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_sandbox(self) -> bool:
        return True   # T-Invest Sandbox is always safe

    @property
    def broker_name(self) -> str:
        return "T-Invest Sandbox"

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def health(self) -> dict:
        if not self._connected:
            return {
                "connected": False, "sandbox_mode": True, "latency_ms": 0.0,
                "last_heartbeat": _now(), "account_accessible": False,
                "overall": "OFFLINE", "sdk_available": _SDK_AVAILABLE,
            }
        try:
            t0 = time.monotonic()
            self._services.sandbox.get_sandbox_accounts()
            latency_ms = (time.monotonic() - t0) * 1000.0
            return {
                "connected": True, "sandbox_mode": True,
                "latency_ms": round(latency_ms, 1),
                "last_heartbeat": _now(),
                "account_accessible": True,
                "account_id": self._account_id,
                "overall": "OK",
            }
        except Exception as exc:
            return {
                "connected": True, "sandbox_mode": True,
                "latency_ms": 0.0, "last_heartbeat": _now(),
                "account_accessible": False,
                "overall": "DEGRADED", "error": str(exc),
            }

    # ── Account ───────────────────────────────────────────────────────────────

    def get_account(self) -> BrokerAccount:
        self._assert_sdk_and_connected()
        return BrokerAccount(
            account_id=self._account_id,
            name="T-Invest Sandbox Account",
            account_type="sandbox",
            status="active",
        )

    def get_positions(self) -> list[Position]:
        self._assert_sdk_and_connected()
        try:
            portfolio = self._services.sandbox.get_sandbox_portfolio(
                account_id=self._account_id
            )
            positions = []
            for pos in portfolio.positions:
                qty = _quotation_to_float(pos.quantity)
                avg = _money_to_float(pos.average_position_price)
                cur = _money_to_float(pos.current_price)
                pnl = _money_to_float(pos.expected_yield)
                positions.append(Position(
                    instrument=pos.figi,
                    quantity=int(qty),
                    avg_price=avg,
                    current_price=cur,
                    pnl=pnl,
                    pnl_pct=(pnl / (avg * qty) if avg * qty else 0.0),
                ))
            return positions
        except Exception as exc:
            from ..broker_models import BrokerError
            raise BrokerError(f"get_positions failed: {exc}") from exc

    def get_balance(self) -> list[Balance]:
        self._assert_sdk_and_connected()
        try:
            portfolio = self._services.sandbox.get_sandbox_portfolio(
                account_id=self._account_id
            )
            balances = []
            for b in portfolio.total_amount_currencies.__class__.__mro__:
                pass  # not available in all SDK versions
            # Fallback: use positions.total_amount_currencies if available
            total = portfolio.total_amount_portfolio
            balances.append(Balance(
                currency=getattr(total, "currency", "RUB"),
                available=_money_to_float(total),
            ))
            return balances
        except Exception as exc:
            from ..broker_models import BrokerError
            raise BrokerError(f"get_balance failed: {exc}") from exc

    # ── Orders ────────────────────────────────────────────────────────────────

    def place_order(self, request: OrderRequest) -> Order:
        self._assert_sdk_and_connected()
        try:
            venv = Path(__file__).resolve().parents[4] / ".venv" / "Lib" / "site-packages"
            if str(venv) not in sys.path:
                sys.path.insert(0, str(venv))
            from t_tech.invest import (
                PostOrderRequest,
                OrderDirection,
                OrderType as TOrderType,
                Quotation,
            )

            direction = (
                OrderDirection.ORDER_DIRECTION_BUY
                if request.side == OrderSide.BUY
                else OrderDirection.ORDER_DIRECTION_SELL
            )
            order_type = (
                TOrderType.ORDER_TYPE_LIMIT
                if request.order_type == OrderType.LIMIT
                else TOrderType.ORDER_TYPE_MARKET
            )
            price_q = _float_to_quotation(request.price)

            resp = self._services.sandbox.post_sandbox_order(
                PostOrderRequest(
                    figi=request.instrument,
                    quantity=request.quantity,
                    price=price_q,
                    direction=direction,
                    account_id=self._account_id,
                    order_type=order_type,
                    order_id=str(uuid.uuid4()),
                )
            )

            status = _map_status(getattr(resp, "execution_report_status", None))
            now = _now()
            return Order(
                order_id=resp.order_id,
                instrument=request.instrument,
                side=request.side,
                quantity=request.quantity,
                price=request.price,
                order_type=request.order_type,
                status=status,
                created_at=now,
                updated_at=now,
                filled_quantity=int(getattr(resp, "lots_executed", 0)),
                avg_price=_money_to_float(getattr(resp, "executed_order_price", None)),
                commission=_money_to_float(getattr(resp, "initial_commission", None)),
                strategy_id=request.strategy_id,
                cycle_id=request.cycle_id,
                broker_response={
                    "order_id": resp.order_id,
                    "status": str(getattr(resp, "execution_report_status", "")),
                },
            )
        except (BrokerUnavailableError, BrokerNotConnectedError):
            raise
        except Exception as exc:
            from ..broker_models import BrokerError
            raise BrokerError(f"place_order failed: {exc}") from exc

    def cancel_order(self, order_id: str) -> bool:
        self._assert_sdk_and_connected()
        try:
            self._services.sandbox.cancel_sandbox_order(
                account_id=self._account_id,
                order_id=order_id,
            )
            return True
        except Exception:
            return False

    def get_order(self, order_id: str) -> Order | None:
        self._assert_sdk_and_connected()
        try:
            resp = self._services.sandbox.get_sandbox_order_state(
                account_id=self._account_id,
                order_id=order_id,
            )
            return self._map_order_state(resp)
        except Exception:
            return None

    def get_orders(self) -> list[Order]:
        self._assert_sdk_and_connected()
        try:
            resp = self._services.sandbox.get_sandbox_orders(
                account_id=self._account_id
            )
            return [self._map_order_state(o) for o in resp.orders]
        except Exception:
            return []

    def get_trades(self) -> list[Order]:
        return [o for o in self.get_orders() if o.status == OrderStatus.FILLED]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _assert_sdk_and_connected(self) -> None:
        if not _SDK_AVAILABLE:
            raise BrokerUnavailableError(
                f"t_tech.invest SDK unavailable: {_SDK_ERROR}"
            )
        if not self._connected:
            raise BrokerNotConnectedError("call connect() before using TInvestSandboxAdapter")

    def _map_order_state(self, resp) -> Order:
        now = _now()
        status = _map_status(getattr(resp, "execution_report_status", None))
        figi = getattr(resp, "figi", "")
        direction_raw = getattr(resp, "direction", None)
        direction_val = str(direction_raw) if direction_raw else ""
        side = OrderSide.BUY if "BUY" in direction_val.upper() else OrderSide.SELL
        return Order(
            order_id=getattr(resp, "order_id", ""),
            instrument=figi,
            side=side,
            quantity=int(getattr(resp, "lots_requested", 0)),
            price=_money_to_float(getattr(resp, "initial_order_price", None)),
            order_type=OrderType.LIMIT,
            status=status,
            created_at=now,
            updated_at=now,
            filled_quantity=int(getattr(resp, "lots_executed", 0)),
            avg_price=_money_to_float(getattr(resp, "average_position_price", None)),
            broker_response={"raw_status": str(getattr(resp, "execution_report_status", ""))},
        )


# ── SDK type conversion helpers ───────────────────────────────────────────────

def _money_to_float(money) -> float:
    if money is None:
        return 0.0
    try:
        units = getattr(money, "units", 0) or 0
        nano  = getattr(money, "nano",  0) or 0
        return float(units) + float(nano) / 1e9
    except Exception:
        return 0.0


def _quotation_to_float(q) -> float:
    if q is None:
        return 0.0
    try:
        return float(getattr(q, "units", 0)) + float(getattr(q, "nano", 0)) / 1e9
    except Exception:
        return 0.0


def _float_to_quotation(value: float):
    """Convert float to t_tech Quotation (lazy import)."""
    venv = Path(__file__).resolve().parents[4] / ".venv" / "Lib" / "site-packages"
    if str(venv) not in sys.path:
        sys.path.insert(0, str(venv))
    from t_tech.invest import Quotation
    units = int(value)
    nano  = round((value - units) * 1_000_000_000)
    return Quotation(units=units, nano=nano)


def _map_status(status_enum) -> OrderStatus:
    """Map t_tech execution_report_status to domain OrderStatus."""
    if status_enum is None:
        return OrderStatus.PENDING
    s = str(status_enum).upper()
    if "FILL" in s:
        return OrderStatus.FILLED
    if "CANCEL" in s:
        return OrderStatus.CANCELLED
    if "REJECT" in s or "INVALID" in s:
        return OrderStatus.REJECTED
    if "PARTIAL" in s:
        return OrderStatus.PARTIAL
    if "NEW" in s or "OPEN" in s or "ACCEPT" in s:
        return OrderStatus.ACCEPTED
    return OrderStatus.PENDING
