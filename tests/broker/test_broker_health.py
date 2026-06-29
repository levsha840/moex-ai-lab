"""M12.5 — BrokerHealth tests (8 tests)."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.broker.broker_health import BrokerHealth, BrokerHealthReport
from services.broker.adapters.mock_broker import MockBroker


class TestBrokerHealthImport:
    def test_importable(self):
        from services.broker.broker_health import BrokerHealth, BrokerHealthReport
        assert BrokerHealth is not None


class TestHealthOffline:
    def test_offline_when_not_connected(self):
        broker = MockBroker()
        # not connected
        health = BrokerHealth(broker)
        report = health.check()
        assert report.overall == "OFFLINE"
        assert not report.connected

    def test_report_is_broker_health_report(self):
        broker = MockBroker()
        health = BrokerHealth(broker)
        report = health.check()
        assert isinstance(report, BrokerHealthReport)

    def test_sandbox_mode_true_always(self):
        broker = MockBroker()
        health = BrokerHealth(broker)
        report = health.check()
        assert report.sandbox_mode is True


class TestHealthConnected:
    def test_ok_when_connected(self):
        broker = MockBroker()
        broker.connect()
        health = BrokerHealth(broker)
        report = health.check()
        assert report.overall == "OK"
        assert report.connected is True

    def test_account_accessible_when_connected(self):
        broker = MockBroker()
        broker.connect()
        health = BrokerHealth(broker)
        report = health.check()
        assert report.account_accessible is True

    def test_latency_near_zero_for_mock(self):
        broker = MockBroker()
        broker.connect()
        health = BrokerHealth(broker)
        report = health.check()
        assert report.latency_ms < 100.0  # mock is always fast

    def test_last_report_is_saved(self):
        broker = MockBroker()
        broker.connect()
        health = BrokerHealth(broker)
        assert health.last_report is None
        health.check()
        assert health.last_report is not None

    def test_to_dict_has_all_keys(self):
        broker = MockBroker()
        broker.connect()
        health = BrokerHealth(broker)
        d = health.check().to_dict()
        assert "connected" in d
        assert "sandbox_mode" in d
        assert "latency_ms" in d
        assert "overall" in d
        assert "account_accessible" in d
