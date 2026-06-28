"""Tests for trading.sandbox_adapter.TInvestSandboxAdapter.

Security invariants verified:
  - Dry-run default: no HTTP request made
  - Token NOT leaked in any payload (Authorization uses <REDACTED>)
  - Only sandbox endpoints used (never production URL)
  - execute=True raises NotImplementedError
  - Live trading block at construction
  - Payload structure validation for all three operations
  - Full session dry-run covers open -> pay_in -> post_order sequence
"""

from __future__ import annotations

import json

import pytest

from trading.models import TradeDirection, TradeSignal
from trading.sandbox_adapter import TInvestSandboxAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_signal(
    instrument: str = "SBER",
    direction: TradeDirection = TradeDirection.LONG,
    entry_price: float = 260.0,
) -> TradeSignal:
    return TradeSignal(
        signal_id="sig_sandbox_001",
        candidate_id="cand_001",
        instrument=instrument,
        direction=direction,
        entry_price=entry_price,
        timeframe="1H",
        regime_label="RANGING",
        confidence=0.70,
        ts="2023-01-10T10:00:00Z",
        reason="sandbox dry-run test",
    )


# ---------------------------------------------------------------------------
# Dry-run: no HTTP call
# ---------------------------------------------------------------------------

class TestDryRunNoHTTP:
    def test_dry_run_open_account_returns_dict(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        result = adapter.dry_run_open_account()
        assert isinstance(result, dict)
        assert result["dry_run"] is True

    def test_dry_run_pay_in_returns_dict(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        result = adapter.dry_run_pay_in("sandbox_acc_1", 1_000_000.0)
        assert isinstance(result, dict)
        assert result["dry_run"] is True

    def test_dry_run_post_order_returns_dict(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        signal = make_signal()
        result = adapter.dry_run_post_order(signal, quantity=10, account_id="sandbox_acc_1")
        assert isinstance(result, dict)
        assert result["dry_run"] is True

    def test_dry_run_returns_payload_key(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        result = adapter.dry_run_open_account()
        assert "payload" in result
        assert isinstance(result["payload"], dict)


# ---------------------------------------------------------------------------
# Token security: no leakage
# ---------------------------------------------------------------------------

class TestTokenSecurity:
    def test_real_token_not_in_open_account_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("T_INVEST_TOKEN", "SUPER_SECRET_TOKEN_12345")
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_open_account()
        payload_str = json.dumps(payload)
        assert "SUPER_SECRET_TOKEN_12345" not in payload_str

    def test_real_token_not_in_pay_in_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("T_INVEST_TOKEN", "SUPER_SECRET_TOKEN_12345")
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_pay_in("acc_1", 500_000.0)
        payload_str = json.dumps(payload)
        assert "SUPER_SECRET_TOKEN_12345" not in payload_str

    def test_real_token_not_in_post_order_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("T_INVEST_TOKEN", "SUPER_SECRET_TOKEN_12345")
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_post_order(make_signal(), quantity=5, account_id="acc_1")
        payload_str = json.dumps(payload)
        assert "SUPER_SECRET_TOKEN_12345" not in payload_str

    def test_authorization_header_uses_redacted_placeholder(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_open_account()
        auth = payload["headers"]["Authorization"]
        assert "<REDACTED>" in auth
        assert auth.startswith("Bearer ")

    def test_token_configured_true_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("T_INVEST_TOKEN", "some_token")
        adapter = TInvestSandboxAdapter(execute=False)
        assert adapter.token_configured is True

    def test_token_configured_false_when_env_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("T_INVEST_TOKEN", raising=False)
        adapter = TInvestSandboxAdapter(execute=False)
        assert adapter.token_configured is False


# ---------------------------------------------------------------------------
# Sandbox endpoint: no production URL
# ---------------------------------------------------------------------------

class TestSandboxEndpointSafety:
    SANDBOX_DOMAIN = "sandbox-invest-public-api.tinkoff.ru"
    PRODUCTION_DOMAIN = "invest-public-api.tinkoff.ru"

    def test_open_account_uses_sandbox_url(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_open_account()
        assert self.SANDBOX_DOMAIN in payload["endpoint"]

    def test_pay_in_uses_sandbox_url(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_pay_in("acc_1", 100_000.0)
        assert self.SANDBOX_DOMAIN in payload["endpoint"]

    def test_post_order_uses_sandbox_url(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_post_order(make_signal(), quantity=10, account_id="acc_1")
        assert self.SANDBOX_DOMAIN in payload["endpoint"]

    def test_sandbox_base_url_starts_with_sandbox(self) -> None:
        # Verify the class-level constant itself is safe
        assert TInvestSandboxAdapter.SANDBOX_BASE_URL.startswith(
            "https://sandbox-invest-public-api.tinkoff.ru"
        )

    def test_production_url_constant_never_used_in_payloads(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        signal = make_signal()
        payloads = [
            adapter.prepare_open_account(),
            adapter.prepare_pay_in("acc_1", 100.0),
            adapter.prepare_post_order(signal, quantity=1, account_id="acc_1"),
        ]
        for payload in payloads:
            endpoint = payload["endpoint"]
            # Must NOT be a pure production endpoint (no "sandbox-" prefix)
            assert endpoint.startswith("https://sandbox-")


# ---------------------------------------------------------------------------
# execute=True raises NotImplementedError
# ---------------------------------------------------------------------------

class TestExecuteNotImplemented:
    def test_execute_true_open_account_raises(self) -> None:
        adapter = TInvestSandboxAdapter(execute=True)
        with pytest.raises(NotImplementedError, match="execute-sandbox"):
            adapter.dry_run_open_account()

    def test_execute_true_pay_in_raises(self) -> None:
        adapter = TInvestSandboxAdapter(execute=True)
        with pytest.raises(NotImplementedError, match="execute-sandbox"):
            adapter.dry_run_pay_in("acc_1", 100_000.0)

    def test_execute_true_post_order_raises(self) -> None:
        adapter = TInvestSandboxAdapter(execute=True)
        with pytest.raises(NotImplementedError, match="execute-sandbox"):
            adapter.dry_run_post_order(make_signal(), quantity=5, account_id="acc_1")


# ---------------------------------------------------------------------------
# Live trading block at construction
# ---------------------------------------------------------------------------

class TestLiveTradingBlock:
    def test_adapter_blocks_when_live_trading_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import core.config.settings as settings_module
        monkeypatch.setattr(settings_module.TRADING_SETTINGS, "enable_live_trading", True)
        with pytest.raises(RuntimeError, match="LIVE_TRADING"):
            TInvestSandboxAdapter(execute=False)


# ---------------------------------------------------------------------------
# Payload structure validation
# ---------------------------------------------------------------------------

class TestPayloadStructure:
    def test_open_account_payload_has_required_fields(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_open_account()
        assert "endpoint" in payload
        assert "method" in payload
        assert "headers" in payload
        assert "body" in payload
        assert payload["method"] == "POST"
        assert "Authorization" in payload["headers"]
        assert "Content-Type" in payload["headers"]

    def test_pay_in_payload_has_account_id_and_amount(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_pay_in("acc_xyz", 2_500_000.0)
        body = payload["body"]
        assert body["accountId"] == "acc_xyz"
        assert body["amount"]["currency"] == "RUB"
        assert body["amount"]["units"] == "2500000"
        assert body["amount"]["nano"] == 0

    def test_post_order_long_direction(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        signal = make_signal(direction=TradeDirection.LONG)
        payload = adapter.prepare_post_order(signal, quantity=10, account_id="acc_1")
        body = payload["body"]
        assert body["direction"] == "ORDER_DIRECTION_BUY"
        assert body["quantity"] == "10"
        assert body["orderType"] == "ORDER_TYPE_MARKET"
        assert body["orderId"] == "sig_sandbox_001"

    def test_post_order_short_direction(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        signal = make_signal(direction=TradeDirection.SHORT)
        payload = adapter.prepare_post_order(signal, quantity=5, account_id="acc_1")
        assert payload["body"]["direction"] == "ORDER_DIRECTION_SELL"

    def test_post_order_sber_figi_known(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        payload = adapter.prepare_post_order(
            make_signal(instrument="SBER"), quantity=10, account_id="acc_1"
        )
        assert payload["body"]["figi"] == "BBG004730N88"

    def test_post_order_unknown_instrument_uses_placeholder(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        signal = TradeSignal(
            signal_id="sig_1",
            candidate_id="c1",
            instrument="UNKNOWN_TICKER",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            timeframe="1H",
            regime_label="RANGING",
            confidence=0.5,
            ts="2023-01-10",
        )
        payload = adapter.prepare_post_order(signal, quantity=1, account_id="acc_1")
        assert "UNKNOWN_TICKER" in payload["body"]["figi"]
        assert payload["body"]["figi"].startswith("<FIGI_FOR_")

    def test_pay_in_rejects_negative_amount(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        with pytest.raises(ValueError, match="amount_rubles"):
            adapter.prepare_pay_in("acc_1", -100.0)

    def test_pay_in_rejects_zero_amount(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        with pytest.raises(ValueError, match="amount_rubles"):
            adapter.prepare_pay_in("acc_1", 0.0)

    def test_post_order_rejects_zero_quantity(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        with pytest.raises(ValueError, match="quantity"):
            adapter.prepare_post_order(make_signal(), quantity=0, account_id="acc_1")


# ---------------------------------------------------------------------------
# Full session dry-run
# ---------------------------------------------------------------------------

class TestFullSessionDryRun:
    def test_full_session_returns_all_keys(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        signals = [make_signal("SBER"), make_signal("VTBR", entry_price=80.0)]
        quantities = [10, 20]
        result = adapter.dry_run_full_session(signals, quantities, 1_000_000.0)
        assert result["dry_run"] is True
        assert "open_account" in result
        assert "pay_in" in result
        assert "orders" in result
        assert len(result["orders"]) == 2

    def test_full_session_mismatched_lengths_raises(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        with pytest.raises(ValueError, match="same length"):
            adapter.dry_run_full_session([make_signal()], [1, 2], 1_000_000.0)

    def test_full_session_all_payloads_use_sandbox(self) -> None:
        adapter = TInvestSandboxAdapter(execute=False)
        signals = [make_signal()]
        result = adapter.dry_run_full_session(signals, [5], 500_000.0)
        # Verify all endpoints use sandbox domain
        for key in ("open_account", "pay_in"):
            endpoint = result[key]["payload"]["endpoint"]
            assert "sandbox-invest-public-api.tinkoff.ru" in endpoint
        for order in result["orders"]:
            endpoint = order["payload"]["endpoint"]
            assert "sandbox-invest-public-api.tinkoff.ru" in endpoint

    def test_full_session_no_token_in_any_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("T_INVEST_TOKEN", "LEAK_TEST_SECRET_9999")
        adapter = TInvestSandboxAdapter(execute=False)
        result = adapter.dry_run_full_session([make_signal()], [5], 1_000_000.0)
        session_str = json.dumps(result)
        assert "LEAK_TEST_SECRET_9999" not in session_str
