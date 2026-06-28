"""Operational Safety Guard for MOEX AI LAB.

Enforces non-negotiable safety constraints before any operational run:
  - No live trading (env-var and flag check)
  - No sandbox execution
  - No token logging
  - No high-risk strategies without explicit approval
  - Per-session research and paper order budgets
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SafetyConfig:
    max_research_runs: int = 100
    max_paper_orders: int = 0
    real_trading_blocked: bool = True
    sandbox_execute_disabled: bool = True
    allow_high_risk: bool = False


class SafetyViolation(RuntimeError):
    """Raised when a safety constraint is violated."""


class SafetyGuard:
    """Stateless safety checker for Operational Mode.

    Usage:
        guard = SafetyGuard(SafetyConfig())
        guard.check_all()          # call once at startup
        guard.check_budget(runs)   # call before each research run
    """

    def __init__(self, config: SafetyConfig | None = None) -> None:
        self._cfg = config or SafetyConfig()
        self._research_runs: int = 0
        self._paper_orders: int = 0

    @property
    def config(self) -> SafetyConfig:
        return self._cfg

    @property
    def research_runs_used(self) -> int:
        return self._research_runs

    @property
    def paper_orders_used(self) -> int:
        return self._paper_orders

    def check_all(self) -> None:
        """Run all pre-flight safety checks. Raises SafetyViolation on any failure."""
        self._check_live_trading_env()
        self._check_sandbox_env()
        self._check_token_logging()

    def check_research_budget(self, runs_to_add: int = 1) -> None:
        """Verify research budget allows another run. Raises if budget exceeded."""
        if self._research_runs + runs_to_add > self._cfg.max_research_runs:
            raise SafetyViolation(
                f"Research budget exhausted: {self._research_runs} / {self._cfg.max_research_runs} runs used."
            )

    def check_paper_order(self) -> None:
        """Verify paper order budget allows another order."""
        if self._paper_orders + 1 > self._cfg.max_paper_orders:
            raise SafetyViolation(
                f"Paper order budget exhausted: {self._paper_orders} / {self._cfg.max_paper_orders} orders used."
            )

    def check_high_risk(self, strategy_name: str) -> None:
        """Block high-risk strategies unless explicitly approved in config."""
        if not self._cfg.allow_high_risk:
            raise SafetyViolation(
                f"Strategy '{strategy_name}' requires allow_high_risk=True approval."
            )

    def record_research_run(self, count: int = 1) -> None:
        self._research_runs += count

    def record_paper_order(self) -> None:
        self._paper_orders += 1

    def budget_remaining(self) -> int:
        return max(0, self._cfg.max_research_runs - self._research_runs)

    def budget_exhausted(self) -> bool:
        return self._research_runs >= self._cfg.max_research_runs

    # ── Private checks ────────────────────────────────────────────────────────

    def _check_live_trading_env(self) -> None:
        if not self._cfg.real_trading_blocked:
            raise SafetyViolation(
                "SafetyConfig.real_trading_blocked must be True in Operational Mode."
            )
        live_flag = os.environ.get("MOEX_ENABLE_LIVE_TRADING", "false").strip().lower()
        if live_flag in ("1", "true", "yes"):
            raise SafetyViolation(
                "MOEX_ENABLE_LIVE_TRADING env var is enabled — live trading blocked in Operational Mode. "
                "Unset the variable or set it to 'false'."
            )

    def _check_sandbox_env(self) -> None:
        if not self._cfg.sandbox_execute_disabled:
            raise SafetyViolation(
                "SafetyConfig.sandbox_execute_disabled must be True in Operational Mode."
            )
        sandbox_flag = os.environ.get("T_INVEST_EXECUTE", "false").strip().lower()
        if sandbox_flag in ("1", "true", "yes"):
            raise SafetyViolation(
                "T_INVEST_EXECUTE env var is enabled — sandbox execution blocked in Operational Mode. "
                "Unset the variable or set it to 'false'."
            )

    def _check_token_logging(self) -> None:
        token = os.environ.get("T_INVEST_TOKEN", "")
        if token and len(token) > 8:
            # Token exists — ensure it won't appear in logs by checking log level settings
            # We cannot prevent it from being set, but we can warn if verbose logging is on
            log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
            if log_level == "DEBUG":
                raise SafetyViolation(
                    "LOG_LEVEL=DEBUG with T_INVEST_TOKEN set risks token leakage to logs. "
                    "Set LOG_LEVEL=INFO or unset T_INVEST_TOKEN."
                )
