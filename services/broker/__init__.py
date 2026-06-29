"""M12.5 — Broker Sandbox Integration layer.

Architecture:
  BrokerInterface (ABC)
    ↑ implements
  TInvestSandboxAdapter   — real T-Invest Sandbox via gRPC SDK
  MockBroker              — in-memory, no SDK, for tests

Supporting:
  RiskGuard       — pre-order safety checks
  TradeJournal    — append-only order log
  BrokerHealth    — connection + latency checks
  broker_events   — LabEvent subclasses for broker lifecycle
"""
from .broker_interface import BrokerInterface
from .broker_models import (
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Balance,
    BrokerAccount,
    BrokerError,
    BrokerUnavailableError,
    BrokerNotConnectedError,
    RiskViolationError,
)
from .broker_risk_guard import RiskGuard, RiskConfig, RiskCheckResult
from .trade_journal import TradeJournal
from .broker_health import BrokerHealth, BrokerHealthReport
from .adapters.mock_broker import MockBroker
from .adapters.tinvest_sandbox import TInvestSandboxAdapter

__all__ = [
    "BrokerInterface",
    "Order", "OrderRequest", "OrderSide", "OrderStatus", "OrderType",
    "Position", "Balance", "BrokerAccount",
    "BrokerError", "BrokerUnavailableError", "BrokerNotConnectedError",
    "RiskViolationError",
    "RiskGuard", "RiskConfig", "RiskCheckResult",
    "TradeJournal",
    "BrokerHealth", "BrokerHealthReport",
    "MockBroker",
    "TInvestSandboxAdapter",
]
