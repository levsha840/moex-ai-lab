"""Tests for trading.models domain objects."""

from __future__ import annotations

import pytest

from trading.models import (
    ExecutionReport,
    PaperOrderRecord,
    PaperPortfolio,
    PositionSizingRule,
    RiskLimit,
    SizingMethod,
    StrategyCandidate,
    StrategyCandidateStatus,
    TradeDirection,
    TradeSignal,
    TradeSignalStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_candidate(
    status: StrategyCandidateStatus = StrategyCandidateStatus.APPROVED_FOR_PAPER,
    pass_rate: float = 0.40,
    confidence: float = 0.75,
) -> StrategyCandidate:
    return StrategyCandidate(
        candidate_id="cand_001",
        hypothesis_id="H-REV-VOL-REG",
        instrument="SBER",
        period="2023",
        timeframe="1H",
        pass_rate=pass_rate,
        confidence=confidence,
        regime_label="RANGING",
        source_ref="night_001/sber_2023",
        status=status,
        approved_by="research_team",
    )


def make_signal(
    instrument: str = "SBER",
    direction: TradeDirection = TradeDirection.LONG,
    entry_price: float = 260.0,
    ts: str = "2023-01-10T10:00:00Z",
) -> TradeSignal:
    return TradeSignal(
        signal_id="sig_001",
        candidate_id="cand_001",
        instrument=instrument,
        direction=direction,
        entry_price=entry_price,
        timeframe="1H",
        regime_label="RANGING",
        confidence=0.70,
        ts=ts,
        stop_loss=250.0,
        take_profit=275.0,
        reason="RSI oversold + RANGING regime",
    )


# ---------------------------------------------------------------------------
# StrategyCandidate
# ---------------------------------------------------------------------------

class TestStrategyCandidate:
    def test_valid_approved_candidate(self) -> None:
        cand = make_candidate(status=StrategyCandidateStatus.APPROVED_FOR_PAPER)
        assert cand.is_approved is True
        assert cand.candidate_id == "cand_001"

    def test_proposed_candidate_not_approved(self) -> None:
        cand = make_candidate(status=StrategyCandidateStatus.PROPOSED)
        assert cand.is_approved is False

    def test_rejected_candidate_not_approved(self) -> None:
        cand = make_candidate(status=StrategyCandidateStatus.REJECTED)
        assert cand.is_approved is False

    def test_invalid_pass_rate_below_zero(self) -> None:
        with pytest.raises(ValueError, match="pass_rate"):
            make_candidate(pass_rate=-0.01)

    def test_invalid_pass_rate_above_one(self) -> None:
        with pytest.raises(ValueError, match="pass_rate"):
            make_candidate(pass_rate=1.01)

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            make_candidate(confidence=1.5)

    def test_empty_candidate_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="candidate_id"):
            StrategyCandidate(
                candidate_id="",
                hypothesis_id="H-X",
                instrument="SBER",
                period="2023",
                timeframe="1H",
                pass_rate=0.40,
                confidence=0.75,
                regime_label="RANGING",
                source_ref="ref",
            )

    def test_empty_instrument_rejected(self) -> None:
        with pytest.raises(ValueError, match="instrument"):
            StrategyCandidate(
                candidate_id="c1",
                hypothesis_id="H-X",
                instrument="",
                period="2023",
                timeframe="1H",
                pass_rate=0.40,
                confidence=0.75,
                regime_label="RANGING",
                source_ref="ref",
            )

    def test_frozen(self) -> None:
        cand = make_candidate()
        with pytest.raises((TypeError, AttributeError)):
            cand.pass_rate = 0.99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TradeSignal
# ---------------------------------------------------------------------------

class TestTradeSignal:
    def test_valid_long_signal(self) -> None:
        sig = make_signal()
        assert sig.direction == TradeDirection.LONG
        assert sig.entry_price == 260.0
        assert sig.status == TradeSignalStatus.PENDING

    def test_invalid_entry_price_zero(self) -> None:
        with pytest.raises(ValueError, match="entry_price"):
            make_signal(entry_price=0.0)

    def test_invalid_entry_price_negative(self) -> None:
        with pytest.raises(ValueError, match="entry_price"):
            make_signal(entry_price=-10.0)

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            TradeSignal(
                signal_id="s1",
                candidate_id="c1",
                instrument="SBER",
                direction=TradeDirection.LONG,
                entry_price=260.0,
                timeframe="1H",
                regime_label="RANGING",
                confidence=1.5,
                ts="2023-01-10",
            )

    def test_invalid_stop_loss_zero(self) -> None:
        with pytest.raises(ValueError, match="stop_loss"):
            TradeSignal(
                signal_id="s1",
                candidate_id="c1",
                instrument="SBER",
                direction=TradeDirection.LONG,
                entry_price=260.0,
                timeframe="1H",
                regime_label="RANGING",
                confidence=0.7,
                ts="2023-01-10",
                stop_loss=0.0,
            )

    def test_optional_stop_loss_and_take_profit(self) -> None:
        sig = TradeSignal(
            signal_id="s1",
            candidate_id="c1",
            instrument="SBER",
            direction=TradeDirection.SHORT,
            entry_price=260.0,
            timeframe="1H",
            regime_label="RANGING",
            confidence=0.7,
            ts="2023-01-10",
        )
        assert sig.stop_loss is None
        assert sig.take_profit is None
        assert sig.direction == TradeDirection.SHORT

    def test_frozen(self) -> None:
        sig = make_signal()
        with pytest.raises((TypeError, AttributeError)):
            sig.entry_price = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PositionSizingRule
# ---------------------------------------------------------------------------

class TestPositionSizingRule:
    def test_fixed_lots_returns_exact_value(self) -> None:
        rule = PositionSizingRule(method=SizingMethod.FIXED_LOTS, value=10)
        assert rule.compute_lots(equity=100_000, price=200.0) == 10

    def test_fixed_lots_clamped_by_max(self) -> None:
        rule = PositionSizingRule(method=SizingMethod.FIXED_LOTS, value=5000, max_lots=100)
        assert rule.compute_lots(equity=100_000, price=200.0) == 100

    def test_fixed_lots_clamped_by_min(self) -> None:
        rule = PositionSizingRule(method=SizingMethod.FIXED_LOTS, value=0.1, min_lots=1)
        # int(0.1) = 0, clamped to min_lots=1
        assert rule.compute_lots(equity=100_000, price=200.0) == 1

    def test_fixed_pct_basic(self) -> None:
        rule = PositionSizingRule(method=SizingMethod.FIXED_PCT, value=0.10)
        # 10% of 100_000 = 10_000; 10_000 / 100 = 100 lots
        assert rule.compute_lots(equity=100_000, price=100.0) == 100

    def test_fixed_pct_half_equity(self) -> None:
        rule = PositionSizingRule(method=SizingMethod.FIXED_PCT, value=0.50)
        # 50% of 50_000 = 25_000; 25_000 / 250 = 100 lots
        assert rule.compute_lots(equity=50_000, price=250.0) == 100

    def test_fixed_pct_zero_equity_returns_min(self) -> None:
        rule = PositionSizingRule(method=SizingMethod.FIXED_PCT, value=0.10, min_lots=2)
        assert rule.compute_lots(equity=0, price=100.0) == 2

    def test_volatility_scaled_basic(self) -> None:
        rule = PositionSizingRule(method=SizingMethod.VOLATILITY_SCALED, value=0.01)
        # lots = (100_000 * 0.01) / (100.0 * 0.02) = 1000 / 2 = 500
        lots = rule.compute_lots(equity=100_000, price=100.0, volatility=0.02)
        assert lots == 500

    def test_volatility_scaled_no_vol_returns_min(self) -> None:
        rule = PositionSizingRule(method=SizingMethod.VOLATILITY_SCALED, value=0.01, min_lots=3)
        assert rule.compute_lots(equity=100_000, price=100.0, volatility=None) == 3

    def test_volatility_scaled_capped_by_max(self) -> None:
        rule = PositionSizingRule(
            method=SizingMethod.VOLATILITY_SCALED,
            value=0.50,
            max_lots=50,
        )
        lots = rule.compute_lots(equity=1_000_000, price=10.0, volatility=0.001)
        assert lots == 50

    def test_invalid_value_zero(self) -> None:
        with pytest.raises(ValueError, match="value"):
            PositionSizingRule(method=SizingMethod.FIXED_LOTS, value=0)

    def test_invalid_pct_above_one(self) -> None:
        with pytest.raises(ValueError, match="value"):
            PositionSizingRule(method=SizingMethod.FIXED_PCT, value=1.5)

    def test_invalid_max_less_than_min(self) -> None:
        with pytest.raises(ValueError, match="max_lots"):
            PositionSizingRule(method=SizingMethod.FIXED_LOTS, value=5, min_lots=10, max_lots=5)

    def test_price_zero_raises(self) -> None:
        rule = PositionSizingRule(method=SizingMethod.FIXED_LOTS, value=10)
        with pytest.raises(ValueError, match="price"):
            rule.compute_lots(equity=100_000, price=0.0)


# ---------------------------------------------------------------------------
# RiskLimit
# ---------------------------------------------------------------------------

class TestRiskLimit:
    def test_defaults_are_valid(self) -> None:
        rl = RiskLimit()
        assert rl.max_position_pct == 0.05
        assert rl.max_drawdown_pct == 0.10
        assert rl.max_open_positions == 10
        assert rl.allow_short is False

    def test_custom_values(self) -> None:
        rl = RiskLimit(
            max_position_pct=0.10,
            max_drawdown_pct=0.05,
            max_open_positions=5,
            allow_short=True,
        )
        assert rl.max_position_pct == 0.10
        assert rl.allow_short is True

    def test_invalid_max_position_pct_zero(self) -> None:
        with pytest.raises(ValueError, match="max_position_pct"):
            RiskLimit(max_position_pct=0.0)

    def test_invalid_max_drawdown_pct_above_one(self) -> None:
        with pytest.raises(ValueError, match="max_drawdown_pct"):
            RiskLimit(max_drawdown_pct=1.5)

    def test_invalid_max_open_positions_zero(self) -> None:
        with pytest.raises(ValueError, match="max_open_positions"):
            RiskLimit(max_open_positions=0)

    def test_frozen(self) -> None:
        rl = RiskLimit()
        with pytest.raises((TypeError, AttributeError)):
            rl.max_position_pct = 0.99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ExecutionReport
# ---------------------------------------------------------------------------

class TestExecutionReport:
    def _make_report(self, wins: int = 3, losses: int = 1) -> ExecutionReport:
        close = wins + losses
        return ExecutionReport(
            report_id="exec_abc123",
            candidate_id="cand_001",
            instrument="SBER",
            initial_equity=100_000.0,
            final_equity=102_500.0,
            peak_equity=103_000.0,
            realized_pnl=2_500.0,
            realized_pnl_pct=0.025,
            max_drawdown=500.0,
            max_drawdown_pct=0.005,
            trades_count=4,
            wins=wins,
            losses=losses,
            win_rate=wins / close if close else 0.0,
            exposure_pct=0.60,
            journal=(),
            generated_at="2026-06-28T00:00:00Z",
        )

    def test_is_profitable(self) -> None:
        report = self._make_report()
        assert report.is_profitable is True

    def test_not_profitable_when_pnl_negative(self) -> None:
        report = ExecutionReport(
            report_id="exec_xyz",
            candidate_id="cand_002",
            instrument="VTBR",
            initial_equity=100_000.0,
            final_equity=98_000.0,
            peak_equity=100_000.0,
            realized_pnl=-2_000.0,
            realized_pnl_pct=-0.02,
            max_drawdown=2_000.0,
            max_drawdown_pct=0.02,
            trades_count=2,
            wins=0,
            losses=2,
            win_rate=0.0,
            exposure_pct=0.30,
            journal=(),
            generated_at="2026-06-28T00:00:00Z",
        )
        assert report.is_profitable is False

    def test_close_trades_property(self) -> None:
        report = self._make_report(wins=2, losses=3)
        assert report.close_trades == 5

    def test_win_rate_calculation(self) -> None:
        report = self._make_report(wins=3, losses=1)
        assert report.win_rate == pytest.approx(0.75)

    def test_journal_is_tuple(self) -> None:
        rec = PaperOrderRecord(
            order_id="ord_1",
            signal_id="sig_1",
            instrument="SBER",
            direction="LONG",
            quantity=10,
            price=260.0,
            commission=1.3,
            slippage=0.0,
            realized_pnl=0.0,
            ts="2023-01-10T10:00:00Z",
            status="FILLED",
        )
        report = ExecutionReport(
            report_id="r1",
            candidate_id="c1",
            instrument="SBER",
            initial_equity=100_000.0,
            final_equity=100_000.0,
            peak_equity=100_000.0,
            realized_pnl=0.0,
            realized_pnl_pct=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            trades_count=1,
            wins=0,
            losses=0,
            win_rate=0.0,
            exposure_pct=0.0,
            journal=(rec,),
            generated_at="2026-06-28T00:00:00Z",
        )
        assert isinstance(report.journal, tuple)
        assert len(report.journal) == 1
        assert report.journal[0].instrument == "SBER"
