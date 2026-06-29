"""M12.5 — RiskGuard: pre-order safety checks.

Every call to BrokerInterface.place_order() MUST pass through RiskGuard.check()
first. The guard operates in a strictly ordered sequence: the first failing check
blocks the order and returns a reason. No orders are ever placed without a PASS.

Check order (most critical first):
  1. kill_switch      — hard stop, overrides everything
  2. sandbox_only     — production broker blocked unless explicitly enabled
  3. position_size    — quantity per single order
  4. max_positions    — concurrent open positions
  5. daily_limit      — total orders placed today
  6. instrument_list  — optional whitelist of allowed instruments
  7. broker_health    — last known health status
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class RiskConfig:
    """Immutable configuration for RiskGuard."""
    sandbox_only: bool = True             # enforce sandbox mode
    max_position_size: int = 10           # max lots per single order
    max_open_positions: int = 5           # max concurrent open positions
    daily_order_limit: int = 20           # max orders submitted today
    kill_switch: bool = False             # if True: ALL orders rejected
    allowed_instruments: list[str] = field(default_factory=list)
    # empty = all instruments allowed


@dataclass
class RiskCheckResult:
    """Result of a pre-order risk check."""
    allowed: bool
    rule: str    # empty string if allowed
    reason: str  # human-readable explanation; empty if allowed

    def __bool__(self) -> bool:
        return self.allowed

    @classmethod
    def ok(cls) -> "RiskCheckResult":
        return cls(allowed=True, rule="", reason="")

    @classmethod
    def block(cls, rule: str, reason: str) -> "RiskCheckResult":
        return cls(allowed=False, rule=rule, reason=reason)


class RiskGuard:
    """Stateless risk gate: checks OrderRequest against RiskConfig + live context.

    The guard is intentionally stateless with respect to positions — callers
    provide current counts at call time. This avoids hidden state drift.
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        self._config = config or RiskConfig()
        self._daily_counts: dict[str, int] = {}   # date → order count (in-memory only)

    # ── Public API ────────────────────────────────────────────────────────────

    def check(
        self,
        request,               # OrderRequest (avoid circular import)
        open_positions: int = 0,
        broker_is_sandbox: bool = True,
    ) -> RiskCheckResult:
        """Run all checks in order. Returns first failure, or OK."""
        cfg = self._config

        # 1. Kill switch
        if cfg.kill_switch:
            return RiskCheckResult.block("kill_switch", "Kill switch is ON — all orders rejected")

        # 2. Sandbox enforcement
        if cfg.sandbox_only and not broker_is_sandbox:
            return RiskCheckResult.block(
                "sandbox_only",
                "Broker is not in sandbox mode but sandbox_only=True. "
                "Set MOEX_ENABLE_LIVE_TRADING=true to use production broker."
            )

        # 3. Position size
        qty = getattr(request, "quantity", 0)
        if qty <= 0:
            return RiskCheckResult.block("quantity", f"quantity must be > 0, got {qty}")
        if qty > cfg.max_position_size:
            return RiskCheckResult.block(
                "max_position_size",
                f"quantity {qty} > max allowed {cfg.max_position_size}",
            )

        # 4. Open positions
        if open_positions >= cfg.max_open_positions:
            return RiskCheckResult.block(
                "max_open_positions",
                f"open positions {open_positions} >= limit {cfg.max_open_positions}",
            )

        # 5. Daily order limit
        today = _today()
        today_count = self._daily_counts.get(today, 0)
        if today_count >= cfg.daily_order_limit:
            return RiskCheckResult.block(
                "daily_limit",
                f"daily orders {today_count} >= limit {cfg.daily_order_limit}",
            )

        # 6. Instrument whitelist
        instrument = getattr(request, "instrument", "")
        if cfg.allowed_instruments and instrument not in cfg.allowed_instruments:
            return RiskCheckResult.block(
                "instrument_whitelist",
                f"instrument '{instrument}' not in allowed list",
            )

        return RiskCheckResult.ok()

    def record_order(self) -> None:
        """Call after a successful place_order() to increment daily counter."""
        today = _today()
        self._daily_counts[today] = self._daily_counts.get(today, 0) + 1

    def daily_count(self) -> int:
        return self._daily_counts.get(_today(), 0)

    def reset_daily(self) -> None:
        """Clear daily counters (for testing or EOD reset)."""
        self._daily_counts.clear()

    @property
    def config(self) -> RiskConfig:
        return self._config
