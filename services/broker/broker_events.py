"""M12.5 — Broker-domain lab events.

These events extend the LabEvent base for broker-specific milestones.
They are designed to be emitted via the shared EventBus (or a separate
broker-scoped bus) — the broker package itself does not wire them.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.event_pipeline.events import LabEvent


# ── Broker lifecycle ──────────────────────────────────────────────────────────

@dataclass
class BrokerConnected(LabEvent):
    event_type: str = "BrokerConnected"
    broker_name: str = ""
    account_id: str = ""
    sandbox_mode: bool = True


@dataclass
class BrokerDisconnected(LabEvent):
    event_type: str = "BrokerDisconnected"
    broker_name: str = ""
    reason: str = ""


# ── Order lifecycle ───────────────────────────────────────────────────────────

@dataclass
class OrderPlaced(LabEvent):
    event_type: str = "OrderPlaced"
    order_id: str = ""
    instrument: str = ""
    side: str = ""
    quantity: int = 0
    price: float = 0.0
    strategy_id: str = ""
    cycle_id: str = ""


@dataclass
class OrderFilled(LabEvent):
    event_type: str = "OrderFilled"
    order_id: str = ""
    instrument: str = ""
    fill_price: float = 0.0
    fill_quantity: int = 0
    commission: float = 0.0


@dataclass
class OrderCancelled(LabEvent):
    event_type: str = "OrderCancelled"
    order_id: str = ""
    instrument: str = ""
    reason: str = ""


@dataclass
class OrderRejected(LabEvent):
    """Emitted when RiskGuard or broker rejects an order."""
    event_type: str = "OrderRejected"
    order_id: str = ""
    instrument: str = ""
    side: str = ""
    quantity: int = 0
    reason: str = ""
    risk_rule: str = ""


# ── Health ────────────────────────────────────────────────────────────────────

@dataclass
class BrokerHealthChecked(LabEvent):
    event_type: str = "BrokerHealthChecked"
    overall: str = "UNKNOWN"       # "OK", "DEGRADED", "OFFLINE"
    latency_ms: float = 0.0
    sandbox_mode: bool = True
