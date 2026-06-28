"""Tests for services/research/safety.py — SafetyGuard."""
from __future__ import annotations

import os

import pytest

from services.research.safety import SafetyConfig, SafetyGuard, SafetyViolation


# ─────────────────────────────────────────────────────────────────────────────
# SafetyConfig defaults
# ─────────────────────────────────────────────────────────────────────────────

class TestSafetyConfig:
    def test_defaults(self):
        cfg = SafetyConfig()
        assert cfg.max_research_runs == 100
        assert cfg.max_paper_orders == 0
        assert cfg.real_trading_blocked is True
        assert cfg.sandbox_execute_disabled is True
        assert cfg.allow_high_risk is False

    def test_custom_values(self):
        cfg = SafetyConfig(max_research_runs=50, max_paper_orders=10)
        assert cfg.max_research_runs == 50
        assert cfg.max_paper_orders == 10


# ─────────────────────────────────────────────────────────────────────────────
# SafetyGuard — pre-flight checks
# ─────────────────────────────────────────────────────────────────────────────

class TestSafetyGuardPreFlight:
    def _clean_env(self, monkeypatch):
        monkeypatch.delenv("MOEX_ENABLE_LIVE_TRADING", raising=False)
        monkeypatch.delenv("T_INVEST_EXECUTE", raising=False)
        monkeypatch.delenv("T_INVEST_TOKEN", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)

    def test_check_all_passes_with_clean_env(self, monkeypatch):
        self._clean_env(monkeypatch)
        guard = SafetyGuard()
        guard.check_all()  # should not raise

    def test_blocks_live_trading_env_var_true(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("MOEX_ENABLE_LIVE_TRADING", "true")
        guard = SafetyGuard()
        with pytest.raises(SafetyViolation, match="MOEX_ENABLE_LIVE_TRADING"):
            guard.check_all()

    def test_blocks_live_trading_env_var_1(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("MOEX_ENABLE_LIVE_TRADING", "1")
        guard = SafetyGuard()
        with pytest.raises(SafetyViolation):
            guard.check_all()

    def test_passes_when_live_trading_set_false(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("MOEX_ENABLE_LIVE_TRADING", "false")
        guard = SafetyGuard()
        guard.check_all()  # should not raise

    def test_blocks_sandbox_execute_env_var(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("T_INVEST_EXECUTE", "true")
        guard = SafetyGuard()
        with pytest.raises(SafetyViolation, match="T_INVEST_EXECUTE"):
            guard.check_all()

    def test_blocks_token_logging_when_debug_and_token_set(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("T_INVEST_TOKEN", "a" * 20)
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        guard = SafetyGuard()
        with pytest.raises(SafetyViolation, match="LOG_LEVEL=DEBUG"):
            guard.check_all()

    def test_passes_when_token_set_but_log_level_info(self, monkeypatch):
        self._clean_env(monkeypatch)
        monkeypatch.setenv("T_INVEST_TOKEN", "a" * 20)
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        guard = SafetyGuard()
        guard.check_all()  # should not raise

    def test_real_trading_blocked_flag_required(self):
        cfg = SafetyConfig(real_trading_blocked=False)
        guard = SafetyGuard(cfg)
        with pytest.raises(SafetyViolation, match="real_trading_blocked"):
            guard.check_all()

    def test_sandbox_disabled_flag_required(self):
        cfg = SafetyConfig(sandbox_execute_disabled=False)
        guard = SafetyGuard(cfg)
        with pytest.raises(SafetyViolation, match="sandbox_execute_disabled"):
            guard.check_all()


# ─────────────────────────────────────────────────────────────────────────────
# Budget management
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetManagement:
    def test_initial_state(self):
        guard = SafetyGuard(SafetyConfig(max_research_runs=10))
        assert guard.research_runs_used == 0
        assert guard.budget_remaining() == 10
        assert guard.budget_exhausted() is False

    def test_record_research_run_increments(self):
        guard = SafetyGuard(SafetyConfig(max_research_runs=10))
        guard.record_research_run(5)
        assert guard.research_runs_used == 5
        assert guard.budget_remaining() == 5

    def test_budget_exhausted_when_at_limit(self):
        guard = SafetyGuard(SafetyConfig(max_research_runs=5))
        guard.record_research_run(5)
        assert guard.budget_exhausted() is True
        assert guard.budget_remaining() == 0

    def test_check_research_budget_raises_when_over(self):
        guard = SafetyGuard(SafetyConfig(max_research_runs=5))
        guard.record_research_run(5)
        with pytest.raises(SafetyViolation, match="Research budget exhausted"):
            guard.check_research_budget(1)

    def test_check_research_budget_passes_when_within(self):
        guard = SafetyGuard(SafetyConfig(max_research_runs=10))
        guard.record_research_run(5)
        guard.check_research_budget(3)  # 5+3=8 <= 10, should not raise

    def test_check_paper_order_raises_when_max_zero(self):
        guard = SafetyGuard(SafetyConfig(max_paper_orders=0))
        with pytest.raises(SafetyViolation, match="Paper order budget exhausted"):
            guard.check_paper_order()

    def test_check_paper_order_passes_when_budget_allows(self):
        guard = SafetyGuard(SafetyConfig(max_paper_orders=5))
        guard.check_paper_order()  # 0+1=1 <= 5, should not raise

    def test_check_high_risk_raises_by_default(self):
        guard = SafetyGuard()
        with pytest.raises(SafetyViolation, match="allow_high_risk"):
            guard.check_high_risk("dangerous_strategy")

    def test_check_high_risk_passes_when_allowed(self):
        guard = SafetyGuard(SafetyConfig(allow_high_risk=True))
        guard.check_high_risk("dangerous_strategy")  # should not raise
