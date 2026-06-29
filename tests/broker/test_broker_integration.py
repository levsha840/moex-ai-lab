"""M12.5 — End-to-end broker integration tests using MockBroker (14 tests).

Tests the full chain:
  MockBroker → RiskGuard → place_order → TradeJournal → BrokerHealth
"""
import sys
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.broker.adapters.mock_broker import MockBroker
from services.broker.broker_risk_guard import RiskGuard, RiskConfig
from services.broker.trade_journal import TradeJournal
from services.broker.broker_health import BrokerHealth
from services.broker.broker_models import (
    OrderRequest, OrderSide, OrderType, OrderStatus,
    BrokerNotConnectedError, RiskViolationError,
)


def _req(instrument="SBER", quantity=5, price=258.0,
         strategy_id="BB_SQUEEZE", cycle_id="cycle_0001",
         side=OrderSide.BUY):
    return OrderRequest(
        instrument=instrument,
        side=side,
        quantity=quantity,
        price=price,
        strategy_id=strategy_id,
        cycle_id=cycle_id,
    )


class TestBrokerInterfaceContract:
    """Verify MockBroker fulfils the BrokerInterface contract."""

    def test_connect_before_order(self):
        b = MockBroker()
        with pytest.raises(BrokerNotConnectedError):
            b.place_order(_req())

    def test_full_buy_flow(self):
        b = MockBroker()
        b.connect()
        order = b.place_order(_req())
        assert order.status == OrderStatus.FILLED
        assert len(b.get_positions()) == 1

    def test_full_sell_flow(self):
        b = MockBroker()
        b.connect()
        b.place_order(_req())   # buy
        sell_req = _req(side=OrderSide.SELL)
        sell_order = b.place_order(sell_req)
        assert sell_order.status == OrderStatus.FILLED
        assert len(b.get_positions()) == 0


class TestRiskGuardIntegration:
    def test_kill_switch_blocks_order(self):
        b = MockBroker()
        b.connect()
        guard = RiskGuard(RiskConfig(kill_switch=True))
        req = _req()
        result = guard.check(req, open_positions=0, broker_is_sandbox=b.is_sandbox)
        assert not result
        # Do NOT place the order
        assert len(b.get_orders()) == 0

    def test_position_size_limit(self):
        b = MockBroker()
        b.connect()
        guard = RiskGuard(RiskConfig(max_position_size=3))
        req = _req(quantity=10)
        result = guard.check(req, broker_is_sandbox=b.is_sandbox)
        assert not result
        assert result.rule == "max_position_size"

    def test_daily_limit_after_orders(self):
        b = MockBroker()
        b.connect()
        guard = RiskGuard(RiskConfig(daily_order_limit=2))
        for _ in range(2):
            r = _req()
            check = guard.check(r, broker_is_sandbox=b.is_sandbox)
            assert check.allowed
            b.place_order(r)
            guard.record_order()
        # Third order blocked
        result = guard.check(_req(), broker_is_sandbox=b.is_sandbox)
        assert not result
        assert result.rule == "daily_limit"

    def test_allowed_instruments_whitelist(self):
        b = MockBroker()
        b.connect()
        guard = RiskGuard(RiskConfig(allowed_instruments=["GAZP"]))
        result = guard.check(_req(instrument="SBER"), broker_is_sandbox=b.is_sandbox)
        assert not result
        result2 = guard.check(_req(instrument="GAZP"), broker_is_sandbox=b.is_sandbox)
        assert result2.allowed


class TestTradeJournalIntegration:
    def test_journal_records_placed_order(self):
        with tempfile.TemporaryDirectory() as td:
            journal = TradeJournal(Path(td) / "j.jsonl")
            b = MockBroker()
            b.connect()
            order = b.place_order(_req())
            journal.record_order(order, event="ORDER_PLACED", reason="integration test")
            entries = journal.read_all()
            assert len(entries) == 1
            assert entries[0]["order_id"] == order.order_id
            assert entries[0]["strategy_id"] == "BB_SQUEEZE"

    def test_journal_records_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            journal = TradeJournal(Path(td) / "j.jsonl")
            guard = RiskGuard(RiskConfig(kill_switch=True))
            req = _req()
            check = guard.check(req)
            assert not check
            journal.record_rejection(
                "none", check.rule, check.reason,
                req.strategy_id, req.cycle_id,
            )
            entries = journal.read_all()
            assert entries[0]["event"] == "ORDER_REJECTED"

    def test_daily_count_from_journal(self):
        with tempfile.TemporaryDirectory() as td:
            journal = TradeJournal(Path(td) / "j.jsonl")
            b = MockBroker()
            b.connect()
            for _ in range(3):
                order = b.place_order(_req())
                journal.record_order(order, event="ORDER_PLACED")
            assert journal.daily_count() == 3


class TestHealthIntegration:
    def test_health_ok_after_connect(self):
        b = MockBroker()
        b.connect()
        health = BrokerHealth(b)
        report = health.check()
        assert report.is_ok()

    def test_health_offline_before_connect(self):
        b = MockBroker()
        health = BrokerHealth(b)
        report = health.check()
        assert report.is_critical()

    def test_full_broker_check_all(self):
        b = MockBroker()
        b.connect()
        account   = b.get_account()
        positions = b.get_positions()
        balance   = b.get_balance()
        health    = BrokerHealth(b).check()
        assert account.account_type == "sandbox"
        assert isinstance(positions, list)
        assert balance[0].currency == "RUB"
        assert health.overall == "OK"


class TestTInvestSandboxAdapterImport:
    def test_importable_without_sdk(self):
        """Adapter must be importable even when gRPC is not available."""
        from services.broker.adapters.tinvest_sandbox import TInvestSandboxAdapter
        assert TInvestSandboxAdapter is not None

    def test_is_sandbox_true(self):
        from services.broker.adapters.tinvest_sandbox import TInvestSandboxAdapter
        adapter = TInvestSandboxAdapter(token="fake_token")
        assert adapter.is_sandbox is True

    def test_connect_raises_unavailable_without_sdk(self):
        from services.broker.adapters.tinvest_sandbox import TInvestSandboxAdapter, _SDK_AVAILABLE
        from services.broker.broker_models import BrokerUnavailableError
        if _SDK_AVAILABLE:
            pytest.skip("SDK is available — connect will attempt real gRPC call")
        adapter = TInvestSandboxAdapter(token="fake_token")
        with pytest.raises(BrokerUnavailableError):
            adapter.connect()
