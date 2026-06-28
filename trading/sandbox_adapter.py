"""TInvestSandboxAdapter — dry-run bridge to T-Invest Sandbox API.

Safety contract (non-negotiable):
  - NEVER calls production T-Invest API (invest-public-api.tinkoff.ru).
  - ONLY uses sandbox endpoint: sandbox-invest-public-api.tinkoff.ru.
  - NEVER reveals the actual T_INVEST_TOKEN in any payload or log.
  - Does NOT send HTTP requests unless execute=True is explicitly passed.
  - execute=True is reserved for future implementation; currently raises
    NotImplementedError to prevent accidental use.
  - MOEX_ENABLE_LIVE_TRADING must be false; construction blocked otherwise.
  - NEVER sends real orders to any endpoint.

Usage (dry-run, default):
    adapter = TInvestSandboxAdapter()           # execute=False by default
    result = adapter.dry_run_open_account()     # prints payload, no HTTP
    result = adapter.dry_run_pay_in("acc_123", 1_000_000.0)
    result = adapter.dry_run_post_order(signal, quantity=10, account_id="acc_123")

Usage (future sandbox execution — not yet implemented):
    adapter = TInvestSandboxAdapter(execute=True)  # requires --execute-sandbox
    # All dry_run_* methods raise NotImplementedError until HTTP layer is built.
"""

from __future__ import annotations

import json
import os

from trading.models import TradeDirection, TradeSignal


# Known FIGI codes for P1 instruments on MOEX.
# Used to populate sandbox order payloads. Not hardcoded for production use
# since sandbox orders do not route to real exchange.
_FIGI_MAP: dict[str, str] = {
    "SBER": "BBG004730N88",
    "VTBR": "BBG004730ZJ9",
    "LKOH": "BBG004731032",
    "GAZP": "BBG004730RP0",
    "ROSN": "BBG004731354",
    "NVTK": "BBG00475KKY8",
    "TATN": "BBG004RVFFC0",
    "GMKN": "BBG004731489",
    "CHMF": "BBG00475K6C3",
    "MAGN": "BBG004731BB2",
    "NLMK": "BBG004S681B4",
    "PLZL": "BBG000QJW156",
    "ALRS": "BBG004S68614",
    "MGNT": "BBG004ZVJLT5",
}

# Placeholder used in all payload Authorization headers to avoid token leakage.
_AUTH_PLACEHOLDER = "Bearer <REDACTED>"


class TInvestSandboxAdapter:
    """Dry-run adapter for T-Invest Sandbox API.

    Prepares and optionally prints the JSON payloads for three Sandbox
    operations: OpenSandboxAccount, SandboxPayIn, and PostSandboxOrder.

    By default (execute=False), all methods print the payload and return it
    as a dict without making any HTTP requests. This is the intended usage
    during the Paper Trading phase.

    Parameters
    ----------
    execute:
        When False (default): print payload, no HTTP. When True: reserved for
        future sandbox HTTP execution; currently raises NotImplementedError.
    """

    SANDBOX_BASE_URL = "https://sandbox-invest-public-api.tinkoff.ru/rest"

    # Production URL — explicitly never used; stored for validation tests.
    _PRODUCTION_BASE_URL = "https://invest-public-api.tinkoff.ru/rest"

    def __init__(self, execute: bool = False) -> None:
        from core.config.settings import TRADING_SETTINGS

        if TRADING_SETTINGS.enable_live_trading:
            raise RuntimeError(
                "SAFETY BLOCK: MOEX_ENABLE_LIVE_TRADING=true detected. "
                "TInvestSandboxAdapter cannot operate while live trading is enabled."
            )

        self._execute = execute
        # Check token presence (bool) without reading its value.
        self._token_configured = bool(os.environ.get("T_INVEST_TOKEN", ""))

    # ------------------------------------------------------------------
    # Token introspection (presence only — never exposes value)
    # ------------------------------------------------------------------

    @property
    def token_configured(self) -> bool:
        """True if T_INVEST_TOKEN is set in the environment."""
        return self._token_configured

    # ------------------------------------------------------------------
    # Payload builders — Authorization header always uses placeholder
    # ------------------------------------------------------------------

    def prepare_open_account(self) -> dict:
        """Build OpenSandboxAccount request payload (no token revealed)."""
        return {
            "endpoint": (
                f"{self.SANDBOX_BASE_URL}/"
                "tinkoff.public.invest.api.contract.v1.SandboxService/OpenSandboxAccount"
            ),
            "method": "POST",
            "headers": {
                "Authorization": _AUTH_PLACEHOLDER,
                "Content-Type": "application/json",
            },
            "body": {},
        }

    def prepare_pay_in(self, account_id: str, amount_rubles: float) -> dict:
        """Build SandboxPayIn request payload.

        Parameters
        ----------
        account_id:
            Sandbox account ID returned by OpenSandboxAccount.
        amount_rubles:
            Amount to credit in Russian rubles (whole rubles only).
        """
        if not account_id:
            raise ValueError("account_id is required")
        if amount_rubles <= 0:
            raise ValueError("amount_rubles must be > 0")

        return {
            "endpoint": (
                f"{self.SANDBOX_BASE_URL}/"
                "tinkoff.public.invest.api.contract.v1.SandboxService/SandboxPayIn"
            ),
            "method": "POST",
            "headers": {
                "Authorization": _AUTH_PLACEHOLDER,
                "Content-Type": "application/json",
            },
            "body": {
                "accountId": account_id,
                "amount": {
                    "currency": "RUB",
                    "units": str(int(amount_rubles)),
                    "nano": 0,
                },
            },
        }

    def prepare_post_order(
        self,
        signal: TradeSignal,
        quantity: int,
        account_id: str,
    ) -> dict:
        """Build PostSandboxOrder request payload.

        Uses the sandbox OrdersService endpoint. Order type is always
        MARKET (ORDER_TYPE_MARKET) in the paper-to-sandbox bridge.
        The FIGI is looked up from the known P1 instrument map; instruments
        not in the map use a placeholder.

        Parameters
        ----------
        signal:
            The trade signal providing instrument, direction, and signal_id.
        quantity:
            Number of lots to order (computed by PositionSizingRule).
        account_id:
            Sandbox account ID.
        """
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if not account_id:
            raise ValueError("account_id is required")

        figi = _FIGI_MAP.get(signal.instrument, f"<FIGI_FOR_{signal.instrument}>")
        direction = (
            "ORDER_DIRECTION_BUY"
            if signal.direction == TradeDirection.LONG
            else "ORDER_DIRECTION_SELL"
        )
        price_units = str(int(signal.entry_price))
        price_nano = int((signal.entry_price - int(signal.entry_price)) * 1_000_000_000)

        return {
            "endpoint": (
                f"{self.SANDBOX_BASE_URL}/"
                "tinkoff.public.invest.api.contract.v1.OrdersService/PostOrder"
            ),
            "method": "POST",
            "headers": {
                "Authorization": _AUTH_PLACEHOLDER,
                "Content-Type": "application/json",
            },
            "body": {
                "figi": figi,
                "quantity": str(quantity),
                "price": {
                    "units": price_units,
                    "nano": price_nano,
                },
                "direction": direction,
                "accountId": account_id,
                "orderType": "ORDER_TYPE_MARKET",
                "orderId": signal.signal_id,
            },
        }

    # ------------------------------------------------------------------
    # Dry-run operations (default mode — no HTTP)
    # ------------------------------------------------------------------

    def dry_run_open_account(self) -> dict:
        """Print OpenSandboxAccount payload; return it without HTTP call."""
        payload = self.prepare_open_account()
        if self._execute:
            raise NotImplementedError(
                "Sandbox HTTP execution is not yet implemented. "
                "Remove execute=True (or --execute-sandbox flag) to use dry-run mode."
            )
        self._print_dry_run("OpenSandboxAccount", payload)
        return {"dry_run": True, "payload": payload}

    def dry_run_pay_in(self, account_id: str, amount_rubles: float) -> dict:
        """Print SandboxPayIn payload; return it without HTTP call."""
        payload = self.prepare_pay_in(account_id, amount_rubles)
        if self._execute:
            raise NotImplementedError(
                "Sandbox HTTP execution is not yet implemented. "
                "Remove execute=True (or --execute-sandbox flag) to use dry-run mode."
            )
        self._print_dry_run("SandboxPayIn", payload)
        return {"dry_run": True, "payload": payload}

    def dry_run_post_order(
        self,
        signal: TradeSignal,
        quantity: int,
        account_id: str,
    ) -> dict:
        """Print PostSandboxOrder payload; return it without HTTP call."""
        payload = self.prepare_post_order(signal, quantity, account_id)
        if self._execute:
            raise NotImplementedError(
                "Sandbox HTTP execution is not yet implemented. "
                "Remove execute=True (or --execute-sandbox flag) to use dry-run mode."
            )
        self._print_dry_run("PostSandboxOrder", payload)
        return {"dry_run": True, "payload": payload}

    # ------------------------------------------------------------------
    # Sandbox session helper — sequences the three operations
    # ------------------------------------------------------------------

    def dry_run_full_session(
        self,
        signals: list[TradeSignal],
        quantities: list[int],
        initial_deposit_rubles: float = 1_000_000.0,
    ) -> dict:
        """Dry-run a full sandbox session: open account -> pay in -> post orders.

        Prints all payloads in order without making any HTTP calls.

        Parameters
        ----------
        signals:
            List of trade signals to submit.
        quantities:
            Corresponding lot counts (len must equal len(signals)).
        initial_deposit_rubles:
            Amount to credit to the sandbox account.
        """
        if len(signals) != len(quantities):
            raise ValueError("signals and quantities must have the same length")

        print("[DRY-RUN] === T-Invest Sandbox Session ===")
        print(f"[DRY-RUN] Instruments: {list({s.instrument for s in signals})}")
        print(f"[DRY-RUN] Signals: {len(signals)}")
        print(f"[DRY-RUN] Deposit: {initial_deposit_rubles:,.0f} RUB")
        print(f"[DRY-RUN] Token configured: {self.token_configured}")
        print()

        account_result = self.dry_run_open_account()
        placeholder_account_id = "sandbox_acc_<ACCOUNT_ID>"

        pay_in_result = self.dry_run_pay_in(placeholder_account_id, initial_deposit_rubles)

        order_results = []
        for sig, qty in zip(signals, quantities):
            order_result = self.dry_run_post_order(sig, qty, placeholder_account_id)
            order_results.append(order_result)

        print("[DRY-RUN] === Session complete — no real orders sent ===")

        return {
            "dry_run": True,
            "open_account": account_result,
            "pay_in": pay_in_result,
            "orders": order_results,
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _print_dry_run(operation: str, payload: dict) -> None:
        print(f"[DRY-RUN] {operation} — no HTTP request made")
        # Print payload but never the real token (already uses placeholder)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print()
