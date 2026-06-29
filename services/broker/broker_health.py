"""M12.5 — BrokerHealth: connection and account health checks.

Checks performed:
  1. broker.is_connected       — was connect() called and successful?
  2. broker.is_sandbox         — safety: confirm sandbox mode
  3. latency_ms                — round-trip time for get_account()
  4. account_accessible        — can we read account info?
  5. last_heartbeat            — ISO timestamp of last successful check

Overall status:
  OK        — all checks pass
  DEGRADED  — connected but latency > threshold or account unavailable
  OFFLINE   — not connected
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


LATENCY_WARN_MS  = 500.0   # > 500ms → DEGRADED
LATENCY_CRIT_MS  = 2000.0  # > 2s    → OFFLINE-equivalent


@dataclass
class BrokerHealthReport:
    connected: bool
    sandbox_mode: bool
    latency_ms: float
    last_heartbeat: str
    account_accessible: bool
    overall: str                   # "OK", "DEGRADED", "OFFLINE"
    details: dict[str, Any] = field(default_factory=dict)

    def is_ok(self) -> bool:
        return self.overall == "OK"

    def is_critical(self) -> bool:
        return self.overall == "OFFLINE"

    def to_dict(self) -> dict:
        return {
            "connected":          self.connected,
            "sandbox_mode":       self.sandbox_mode,
            "latency_ms":         round(self.latency_ms, 1),
            "last_heartbeat":     self.last_heartbeat,
            "account_accessible": self.account_accessible,
            "overall":            self.overall,
            "details":            self.details,
        }


class BrokerHealth:
    """Run health checks against a live BrokerInterface connection."""

    def __init__(self, broker) -> None:  # BrokerInterface (avoid circular import)
        self._broker = broker
        self._last_report: BrokerHealthReport | None = None

    def check(self) -> BrokerHealthReport:
        broker = self._broker
        ts = _now()
        details: dict[str, Any] = {}

        # 1. Connection
        if not broker.is_connected:
            report = BrokerHealthReport(
                connected=False,
                sandbox_mode=broker.is_sandbox,
                latency_ms=0.0,
                last_heartbeat=ts,
                account_accessible=False,
                overall="OFFLINE",
                details={"reason": "not connected"},
            )
            self._last_report = report
            return report

        # 2. Sandbox mode
        sandbox = broker.is_sandbox
        if not sandbox:
            details["warning"] = "broker is NOT in sandbox mode"

        # 3. Latency — call get_account() and time it
        latency_ms = 0.0
        account_ok = False
        try:
            t0 = time.monotonic()
            account = broker.get_account()
            latency_ms = (time.monotonic() - t0) * 1000.0
            account_ok = True
            details["account_id"] = account.account_id
            details["account_type"] = account.account_type
        except Exception as exc:
            latency_ms = LATENCY_CRIT_MS + 1
            details["account_error"] = str(exc)

        # 4. Determine overall status
        if not account_ok or latency_ms > LATENCY_CRIT_MS:
            overall = "OFFLINE"
        elif latency_ms > LATENCY_WARN_MS:
            overall = "DEGRADED"
        else:
            overall = "OK"

        report = BrokerHealthReport(
            connected=True,
            sandbox_mode=sandbox,
            latency_ms=round(latency_ms, 1),
            last_heartbeat=ts,
            account_accessible=account_ok,
            overall=overall,
            details=details,
        )
        self._last_report = report
        return report

    @property
    def last_report(self) -> BrokerHealthReport | None:
        return self._last_report
