"""M12.5 — RiskGuard tests (16 tests)."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.broker.broker_risk_guard import RiskGuard, RiskConfig, RiskCheckResult
from services.broker.broker_models import OrderRequest, OrderSide, OrderType


def _req(instrument="SBER", quantity=1, price=258.0):
    return OrderRequest(
        instrument=instrument,
        side=OrderSide.BUY,
        quantity=quantity,
        price=price,
    )


class TestRiskGuardImport:
    def test_importable(self):
        from services.broker.broker_risk_guard import RiskGuard, RiskConfig
        assert RiskGuard is not None

    def test_risk_check_result_bool(self):
        assert bool(RiskCheckResult.ok()) is True
        assert bool(RiskCheckResult.block("r", "reason")) is False


class TestKillSwitch:
    def test_kill_switch_blocks_all(self):
        guard = RiskGuard(RiskConfig(kill_switch=True))
        result = guard.check(_req())
        assert not result
        assert result.rule == "kill_switch"

    def test_no_kill_switch_passes(self):
        guard = RiskGuard(RiskConfig(kill_switch=False))
        result = guard.check(_req())
        assert result.allowed


class TestSandboxEnforcement:
    def test_sandbox_only_blocks_live_broker(self):
        guard = RiskGuard(RiskConfig(sandbox_only=True))
        result = guard.check(_req(), broker_is_sandbox=False)
        assert not result
        assert result.rule == "sandbox_only"

    def test_sandbox_only_passes_sandbox_broker(self):
        guard = RiskGuard(RiskConfig(sandbox_only=True))
        result = guard.check(_req(), broker_is_sandbox=True)
        assert result.allowed

    def test_sandbox_only_false_allows_live(self):
        guard = RiskGuard(RiskConfig(sandbox_only=False))
        result = guard.check(_req(), broker_is_sandbox=False)
        assert result.allowed


class TestPositionSize:
    def test_quantity_zero_blocked(self):
        guard = RiskGuard(RiskConfig(max_position_size=10))
        result = guard.check(_req(quantity=0))
        assert not result
        assert result.rule == "quantity"

    def test_quantity_at_limit_passes(self):
        guard = RiskGuard(RiskConfig(max_position_size=10))
        assert guard.check(_req(quantity=10)).allowed

    def test_quantity_over_limit_blocked(self):
        guard = RiskGuard(RiskConfig(max_position_size=10))
        result = guard.check(_req(quantity=11))
        assert not result
        assert result.rule == "max_position_size"


class TestOpenPositions:
    def test_at_limit_blocked(self):
        guard = RiskGuard(RiskConfig(max_open_positions=3))
        result = guard.check(_req(), open_positions=3)
        assert not result
        assert result.rule == "max_open_positions"

    def test_under_limit_passes(self):
        guard = RiskGuard(RiskConfig(max_open_positions=3))
        assert guard.check(_req(), open_positions=2).allowed


class TestDailyLimit:
    def test_daily_limit_hit(self):
        guard = RiskGuard(RiskConfig(daily_order_limit=3))
        # Record 3 orders manually
        for _ in range(3):
            guard.record_order()
        result = guard.check(_req())
        assert not result
        assert result.rule == "daily_limit"

    def test_daily_limit_resets(self):
        guard = RiskGuard(RiskConfig(daily_order_limit=3))
        for _ in range(3):
            guard.record_order()
        guard.reset_daily()
        assert guard.check(_req()).allowed


class TestInstrumentWhitelist:
    def test_not_in_whitelist_blocked(self):
        guard = RiskGuard(RiskConfig(allowed_instruments=["GAZP", "LKOH"]))
        result = guard.check(_req(instrument="SBER"))
        assert not result
        assert result.rule == "instrument_whitelist"

    def test_in_whitelist_passes(self):
        guard = RiskGuard(RiskConfig(allowed_instruments=["SBER", "GAZP"]))
        assert guard.check(_req(instrument="SBER")).allowed

    def test_empty_whitelist_allows_all(self):
        guard = RiskGuard(RiskConfig(allowed_instruments=[]))
        assert guard.check(_req(instrument="ANYTHING")).allowed


class TestRecordOrder:
    def test_daily_count_increments(self):
        guard = RiskGuard()
        assert guard.daily_count() == 0
        guard.record_order()
        guard.record_order()
        assert guard.daily_count() == 2
