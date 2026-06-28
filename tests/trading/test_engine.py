"""Tests for trading.engine.ApprovedCandidatePaperEngine.

Covers:
  - Approval gate (status != APPROVED_FOR_PAPER raises ValueError)
  - Live trading safety block (MOEX_ENABLE_LIVE_TRADING=true blocks construction)
  - Paper portfolio accounting (BUY/SELL PnL, cash tracking)
  - Risk limit blocks (max_position_pct exceeded -> trade REJECTED)
  - Position sizing (all three methods reflected in trade quantity)
  - ExecutionReport generation (PnL, win_rate, drawdown, exposure)
  - Drawdown stop (engine halts signals after drawdown limit)
  - Journal file written on run completion
"""

from __future__ import annotations

from pathlib import Path

import pytest

from trading.engine import ApprovedCandidatePaperEngine
from trading.models import (
    ExecutionReport,
    PositionSizingRule,
    RiskLimit,
    SizingMethod,
    StrategyCandidate,
    StrategyCandidateStatus,
    TradeDirection,
    TradeSignal,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

def make_candidate(
    instrument: str = "SBER",
    status: StrategyCandidateStatus = StrategyCandidateStatus.APPROVED_FOR_PAPER,
) -> StrategyCandidate:
    return StrategyCandidate(
        candidate_id=f"cand_{instrument}",
        hypothesis_id="H-REV-VOL-REG",
        instrument=instrument,
        period="2023",
        timeframe="1H",
        pass_rate=0.40,
        confidence=0.75,
        regime_label="RANGING",
        source_ref=f"night_001/{instrument.lower()}_2023",
        status=status,
    )


def make_signal(
    instrument: str = "SBER",
    direction: TradeDirection = TradeDirection.LONG,
    entry_price: float = 260.0,
    ts: str = "2023-01-10T10:00:00Z",
    signal_id: str = "sig_001",
) -> TradeSignal:
    return TradeSignal(
        signal_id=signal_id,
        candidate_id=f"cand_{instrument}",
        instrument=instrument,
        direction=direction,
        entry_price=entry_price,
        timeframe="1H",
        regime_label="RANGING",
        confidence=0.70,
        ts=ts,
        reason="test signal",
    )


def make_engine(
    sizing_method: SizingMethod = SizingMethod.FIXED_LOTS,
    sizing_value: float = 10,
    max_position_pct: float = 0.50,
    max_drawdown_pct: float = 0.10,
    max_open_positions: int = 10,
    initial_equity: float = 1_000_000.0,
    journal_dir: Path | None = None,
) -> ApprovedCandidatePaperEngine:
    return ApprovedCandidatePaperEngine(
        sizing_rule=PositionSizingRule(method=sizing_method, value=sizing_value),
        risk_limit=RiskLimit(
            max_position_pct=max_position_pct,
            max_drawdown_pct=max_drawdown_pct,
            max_open_positions=max_open_positions,
        ),
        initial_equity=initial_equity,
        journal_dir=journal_dir,
    )


# ---------------------------------------------------------------------------
# Safety: approval gate
# ---------------------------------------------------------------------------

class TestApprovalGate:
    def test_proposed_candidate_raises_value_error(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path)
        candidate = make_candidate(status=StrategyCandidateStatus.PROPOSED)
        with pytest.raises(ValueError, match="APPROVED_FOR_PAPER"):
            engine.run(candidate, [])

    def test_rejected_candidate_raises_value_error(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path)
        candidate = make_candidate(status=StrategyCandidateStatus.REJECTED)
        with pytest.raises(ValueError, match="APPROVED_FOR_PAPER"):
            engine.run(candidate, [])

    def test_retired_candidate_raises_value_error(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path)
        candidate = make_candidate(status=StrategyCandidateStatus.RETIRED)
        with pytest.raises(ValueError, match="APPROVED_FOR_PAPER"):
            engine.run(candidate, [])

    def test_approved_candidate_accepted(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path)
        candidate = make_candidate(status=StrategyCandidateStatus.APPROVED_FOR_PAPER)
        report = engine.run(candidate, [])
        assert isinstance(report, ExecutionReport)


# ---------------------------------------------------------------------------
# Safety: live trading block
# ---------------------------------------------------------------------------

class TestLiveTradingBlock:
    def test_engine_blocks_when_live_trading_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import core.config.settings as settings_module
        monkeypatch.setattr(settings_module.TRADING_SETTINGS, "enable_live_trading", True)
        with pytest.raises(RuntimeError, match="LIVE_TRADING"):
            ApprovedCandidatePaperEngine(
                sizing_rule=PositionSizingRule(method=SizingMethod.FIXED_LOTS, value=1),
                risk_limit=RiskLimit(),
            )

    def test_engine_allowed_when_live_trading_disabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import core.config.settings as settings_module
        monkeypatch.setattr(settings_module.TRADING_SETTINGS, "enable_live_trading", False)
        engine = make_engine(journal_dir=tmp_path)
        assert engine is not None


# ---------------------------------------------------------------------------
# Paper portfolio accounting
# ---------------------------------------------------------------------------

class TestPaperPortfolioAccounting:
    def test_buy_reduces_cash(self, tmp_path: Path) -> None:
        engine = make_engine(
            sizing_value=10,
            initial_equity=100_000.0,
            journal_dir=tmp_path,
        )
        candidate = make_candidate()
        signals = [make_signal(entry_price=100.0)]
        report = engine.run(candidate, signals)
        # BUY 10 lots @ 100 = 1000 rubles; commission 0.05%
        assert report.trades_count == 1
        assert report.final_equity < 100_000.0

    def test_buy_then_sell_profitable_trade(self, tmp_path: Path) -> None:
        engine = make_engine(
            sizing_value=10,
            initial_equity=100_000.0,
            journal_dir=tmp_path,
        )
        candidate = make_candidate()
        signals = [
            make_signal(direction=TradeDirection.LONG, entry_price=100.0, ts="t1", signal_id="s1"),
            make_signal(direction=TradeDirection.SHORT, entry_price=110.0, ts="t2", signal_id="s2"),
        ]
        report = engine.run(candidate, signals)

        assert report.trades_count == 2
        assert report.wins >= 1
        assert report.realized_pnl > 0
        assert report.win_rate == 1.0

    def test_buy_then_sell_losing_trade(self, tmp_path: Path) -> None:
        engine = make_engine(
            sizing_value=10,
            initial_equity=100_000.0,
            journal_dir=tmp_path,
        )
        candidate = make_candidate()
        signals = [
            make_signal(direction=TradeDirection.LONG, entry_price=100.0, ts="t1", signal_id="s1"),
            make_signal(direction=TradeDirection.SHORT, entry_price=90.0, ts="t2", signal_id="s2"),
        ]
        report = engine.run(candidate, signals)

        assert report.trades_count == 2
        assert report.losses >= 1
        assert report.realized_pnl < 0

    def test_no_signals_returns_zero_trades(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path)
        candidate = make_candidate()
        report = engine.run(candidate, [])
        assert report.trades_count == 0
        assert report.final_equity == pytest.approx(1_000_000.0)

    def test_pnl_pct_consistent_with_absolute_pnl(self, tmp_path: Path) -> None:
        initial = 100_000.0
        engine = make_engine(
            sizing_value=10,
            initial_equity=initial,
            journal_dir=tmp_path,
        )
        candidate = make_candidate()
        signals = [
            make_signal(direction=TradeDirection.LONG, entry_price=100.0, ts="t1", signal_id="s1"),
            make_signal(direction=TradeDirection.SHORT, entry_price=120.0, ts="t2", signal_id="s2"),
        ]
        report = engine.run(candidate, signals)
        expected_pct = report.realized_pnl / initial
        assert report.realized_pnl_pct == pytest.approx(expected_pct, abs=1e-6)

    def test_portfolio_snapshot_accessible_after_run(self, tmp_path: Path) -> None:
        engine = make_engine(sizing_value=5, initial_equity=50_000.0, journal_dir=tmp_path)
        candidate = make_candidate()
        engine.run(candidate, [make_signal(entry_price=100.0)])
        portfolio = engine.portfolio()
        assert portfolio.initial_equity == 50_000.0
        assert portfolio.cash < 50_000.0  # cash spent on BUY

    def test_multiple_instruments_in_sequence(self, tmp_path: Path) -> None:
        engine = make_engine(sizing_value=5, initial_equity=500_000.0, journal_dir=tmp_path)

        for instrument in ["SBER", "VTBR", "LKOH"]:
            candidate = make_candidate(instrument=instrument)
            signals = [
                make_signal(instrument=instrument, direction=TradeDirection.LONG, entry_price=100.0, ts="t1", signal_id=f"s1_{instrument}"),
                make_signal(instrument=instrument, direction=TradeDirection.SHORT, entry_price=105.0, ts="t2", signal_id=f"s2_{instrument}"),
            ]
            report = engine.run(candidate, signals)
            assert report.instrument == instrument
            assert report.trades_count == 2


# ---------------------------------------------------------------------------
# Risk limit enforcement
# ---------------------------------------------------------------------------

class TestRiskLimitEnforcement:
    def test_max_position_pct_blocks_oversized_trade(self, tmp_path: Path) -> None:
        # Max 1% of 100_000 = 1_000 rubles per position
        # FIXED_PCT 50% would try to allocate 50_000 rubles -> rejected
        engine = ApprovedCandidatePaperEngine(
            sizing_rule=PositionSizingRule(method=SizingMethod.FIXED_PCT, value=0.50),
            risk_limit=RiskLimit(max_position_pct=0.01),  # 1% limit
            initial_equity=100_000.0,
            journal_dir=tmp_path,
        )
        candidate = make_candidate()
        signals = [make_signal(entry_price=100.0)]
        report = engine.run(candidate, signals)

        filled_count = sum(1 for r in report.journal if r.status == "FILLED")
        rejected_count = sum(1 for r in report.journal if r.status == "REJECTED")
        assert rejected_count >= 1
        assert filled_count == 0

    def test_drawdown_stop_halts_execution(self, tmp_path: Path) -> None:
        # Set very tight drawdown limit (1%) with lossy trades
        engine = ApprovedCandidatePaperEngine(
            sizing_rule=PositionSizingRule(method=SizingMethod.FIXED_LOTS, value=100),
            risk_limit=RiskLimit(max_drawdown_pct=0.01),  # 1% drawdown stop
            initial_equity=10_000.0,
            journal_dir=tmp_path,
        )
        candidate = make_candidate()
        # BUY at 100 then SELL at 80 = big loss, triggers drawdown stop
        # Subsequent signals should not execute
        signals = [
            make_signal(direction=TradeDirection.LONG, entry_price=100.0, ts="t1", signal_id="s1"),
            make_signal(direction=TradeDirection.SHORT, entry_price=80.0, ts="t2", signal_id="s2"),
            # Below signals should not execute due to drawdown stop
            make_signal(direction=TradeDirection.LONG, entry_price=80.0, ts="t3", signal_id="s3"),
            make_signal(direction=TradeDirection.LONG, entry_price=80.0, ts="t4", signal_id="s4"),
        ]
        report = engine.run(candidate, signals)
        # After the big loss, drawdown stop triggers — not all 4 signals execute
        assert report.trades_count < 4

    def test_insufficient_cash_blocks_buy(self, tmp_path: Path) -> None:
        engine = ApprovedCandidatePaperEngine(
            sizing_rule=PositionSizingRule(
                method=SizingMethod.FIXED_LOTS,
                value=100_000,   # 100k lots at 100 rubles = 10M rubles
                max_lots=100_000,
            ),
            risk_limit=RiskLimit(max_position_pct=0.99),
            initial_equity=1_000.0,   # only 1000 rubles — can't afford 100k lots
            journal_dir=tmp_path,
        )
        candidate = make_candidate()
        signals = [make_signal(entry_price=100.0)]
        report = engine.run(candidate, signals)
        rejected = sum(1 for r in report.journal if r.status == "REJECTED")
        assert rejected >= 1


# ---------------------------------------------------------------------------
# Position sizing integration
# ---------------------------------------------------------------------------

class TestPositionSizingIntegration:
    def test_fixed_lots_quantity_in_journal(self, tmp_path: Path) -> None:
        engine = make_engine(
            sizing_method=SizingMethod.FIXED_LOTS,
            sizing_value=7,
            initial_equity=1_000_000.0,
            journal_dir=tmp_path,
        )
        candidate = make_candidate()
        report = engine.run(candidate, [make_signal(entry_price=100.0)])
        filled = [r for r in report.journal if r.status == "FILLED"]
        assert filled[0].quantity == 7

    def test_fixed_pct_quantity_proportional_to_equity(self, tmp_path: Path) -> None:
        # 10% of 1_000_000 / 100 = 1000 lots
        engine = make_engine(
            sizing_method=SizingMethod.FIXED_PCT,
            sizing_value=0.10,
            initial_equity=1_000_000.0,
            journal_dir=tmp_path,
        )
        candidate = make_candidate()
        report = engine.run(candidate, [make_signal(entry_price=100.0)])
        filled = [r for r in report.journal if r.status == "FILLED"]
        assert filled[0].quantity == 1000


# ---------------------------------------------------------------------------
# Execution report correctness
# ---------------------------------------------------------------------------

class TestExecutionReport:
    def test_report_candidate_id_matches_input(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path)
        candidate = make_candidate(instrument="LKOH")
        report = engine.run(candidate, [])
        assert report.candidate_id == "cand_LKOH"
        assert report.instrument == "LKOH"

    def test_peak_equity_gte_final_equity(self, tmp_path: Path) -> None:
        engine = make_engine(sizing_value=5, journal_dir=tmp_path)
        candidate = make_candidate()
        signals = [
            make_signal(direction=TradeDirection.LONG, entry_price=100.0, ts="t1", signal_id="s1"),
            make_signal(direction=TradeDirection.SHORT, entry_price=90.0, ts="t2", signal_id="s2"),
        ]
        report = engine.run(candidate, signals)
        assert report.peak_equity >= report.final_equity

    def test_max_drawdown_nonnegative(self, tmp_path: Path) -> None:
        engine = make_engine(sizing_value=5, journal_dir=tmp_path)
        candidate = make_candidate()
        report = engine.run(candidate, [make_signal(entry_price=100.0)])
        assert report.max_drawdown >= 0.0
        assert report.max_drawdown_pct >= 0.0

    def test_win_rate_zero_when_no_close_trades(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path)
        candidate = make_candidate()
        # Only BUY signal, no SELL -> no close trade -> win_rate = 0
        report = engine.run(candidate, [make_signal(entry_price=100.0)])
        assert report.win_rate == 0.0

    def test_generated_at_is_non_empty(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path)
        candidate = make_candidate()
        report = engine.run(candidate, [])
        assert len(report.generated_at) > 0

    def test_report_is_frozen(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path)
        candidate = make_candidate()
        report = engine.run(candidate, [])
        with pytest.raises((TypeError, AttributeError)):
            report.realized_pnl = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Journal file
# ---------------------------------------------------------------------------

class TestJournalFile:
    def test_journal_file_created(self, tmp_path: Path) -> None:
        engine = make_engine(journal_dir=tmp_path, sizing_value=5)
        candidate = make_candidate()
        engine.run(candidate, [make_signal(entry_price=100.0)])
        journal_path = tmp_path / "cand_SBER_journal.json"
        assert journal_path.exists()

    def test_journal_file_is_valid_json(self, tmp_path: Path) -> None:
        import json as _json
        engine = make_engine(journal_dir=tmp_path, sizing_value=5)
        candidate = make_candidate()
        engine.run(candidate, [make_signal(entry_price=100.0)])
        journal_path = tmp_path / "cand_SBER_journal.json"
        with open(journal_path, encoding="utf-8") as fh:
            records = _json.load(fh)
        assert isinstance(records, list)
        assert len(records) >= 1
        assert "order_id" in records[0]
        assert "status" in records[0]

    def test_journal_records_filled_status(self, tmp_path: Path) -> None:
        import json as _json
        engine = make_engine(journal_dir=tmp_path, sizing_value=5)
        candidate = make_candidate()
        engine.run(candidate, [make_signal(entry_price=100.0)])
        journal_path = tmp_path / "cand_SBER_journal.json"
        with open(journal_path, encoding="utf-8") as fh:
            records = _json.load(fh)
        statuses = [r["status"] for r in records]
        assert "FILLED" in statuses
