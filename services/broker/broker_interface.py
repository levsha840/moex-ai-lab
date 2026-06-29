"""M12.5 — BrokerInterface abstract base class.

The Runtime, RiskGuard, and all trading components talk ONLY to this interface.
Concrete implementations (TInvestSandboxAdapter, MockBroker, etc.) provide the
actual SDK calls — and are fully swappable without touching Runtime code.

Contract rules enforced by the ABC:
- connect() must be called before any trading method
- is_sandbox must return True for any non-live implementation
- All trading methods must go through RiskGuard externally before calling place_order()
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .broker_models import (
    Order,
    OrderRequest,
    Position,
    Balance,
    BrokerAccount,
)


class BrokerInterface(ABC):
    """Abstract broker interface.

    All methods return domain models from broker_models — never SDK types.
    Implementations must be importable without the SDK installed; SDK imports
    must be lazy (inside methods or guarded at module level).
    """

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection. Returns True on success.

        Raises BrokerUnavailableError if SDK is missing.
        Raises BrokerError on authentication failure.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection gracefully."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True after a successful connect()."""

    @property
    @abstractmethod
    def is_sandbox(self) -> bool:
        """MUST return True for all non-production implementations.

        Any implementation with is_sandbox=False requires explicit
        MOEX_ENABLE_LIVE_TRADING=true to be used by Runtime.
        """

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Human-readable name, e.g. 'T-Invest Sandbox', 'MockBroker'."""

    # ── Diagnostics ───────────────────────────────────────────────────────────

    @abstractmethod
    def health(self) -> dict:
        """Return a dict with at minimum: connected, sandbox_mode, latency_ms."""

    # ── Account ───────────────────────────────────────────────────────────────

    @abstractmethod
    def get_account(self) -> BrokerAccount:
        """Return the primary trading account for this connection."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Return all open positions."""

    @abstractmethod
    def get_balance(self) -> list[Balance]:
        """Return balances per currency."""

    # ── Orders ────────────────────────────────────────────────────────────────

    @abstractmethod
    def place_order(self, request: OrderRequest) -> Order:
        """Submit a new order.

        This is the primary execution entry point. The caller is responsible
        for running RiskGuard.check() BEFORE calling this method.
        """

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order. Returns True if cancellation was accepted."""

    @abstractmethod
    def get_order(self, order_id: str) -> Order | None:
        """Return order by ID, or None if not found."""

    @abstractmethod
    def get_orders(self) -> list[Order]:
        """Return all orders (open + historical)."""

    @abstractmethod
    def get_trades(self) -> list[Order]:
        """Return filled/executed trades."""
