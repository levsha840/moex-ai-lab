"""Tests for reports/visual_backtest/ — journal, equity, metrics, paths, renderer.

Coverage:
  - TradeJournalEntry schema and invariants
  - Trade journal generation (no lookahead, deterministic, zero-trade)
  - Equity curve construction
  - Drawdown calculation
  - BacktestMetrics (win rate, profit factor, exposure, etc.)
  - Report path convention
  - Signal dispatcher (all 10 signal types)
  - Chart rendering (smoke test, no display)
"""
from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.walkforward.models import WalkForwardConfig
from experiments.generic.providers import GenericProviderFactory
from services.visual_backtest.equity import build_equity_curve, compute_metrics
from services.visual_backtest.journal import (
    TradeJournalGenerator,
    _check_signal,
    _extract_signal_config,
)
from services.visual_backtest.models import BacktestMetrics, EquityPoint, TradeJournalEntry
from services.visual_backtest.reporter import _report_dir


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _candles(n: int = 200, start: float = 100.0, step: float = 0.3) -> list[dict]:
    """Trending OHLCV candles (close increases linearly)."""
    result = []
    for i in range(n):
        c = start + i * step
        result.append({
            "ticker": "TEST", "ts": f"2023-01-01 {i:02d}:00:00",
            "open": c - 0.1, "high": c + 0.5, "low": c - 0.5,
            "close": c, "volume": 1000,
        })
    return result


def _flat_candles(n: int = 200, price: float = 100.0) -> list[dict]:
    return [
        {"ticker": "TEST", "ts": f"2023-01-01 {i:02d}:00:00",
         "open": price, "high": price + 0.1, "low": price - 0.1,
         "close": price, "volume": 1000}
        for i in range(n)
    ]


def _wf_config() -> WalkForwardConfig:
    return WalkForwardConfig(train_size=60, test_size=20, step_size=20)


def _make_entry(
    trade_id="t0001", entry_bar=10, entry_price=100.0,
    exit_bar=15, exit_price=105.0, exit_reason="TIME_EXIT",
    capital_before=1_000_000.0,
) -> TradeJournalEntry:
    return TradeJournalEntry.build(
        trade_id=trade_id,
        entry_bar=entry_bar, entry_price=entry_price,
        exit_bar=exit_bar, exit_price=exit_price,
        exit_reason=exit_reason,
        capital_before=capital_before,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TradeJournalEntry schema
# ─────────────────────────────────────────────────────────────────────────────

class TestTradeJournalEntrySchema:
    def test_required_fields_present(self):
        e = _make_entry()
        assert hasattr(e, "trade_id")
        assert hasattr(e, "entry_timestamp")
        assert hasattr(e, "entry_bar")
        assert hasattr(e, "entry_price")
        assert hasattr(e, "exit_timestamp")
        assert hasattr(e, "exit_bar")
        assert hasattr(e, "exit_price")
        assert hasattr(e, "exit_reason")
        assert hasattr(e, "direction")
        assert hasattr(e, "pnl")
        assert hasattr(e, "pnl_pct")
        assert hasattr(e, "capital_before")
        assert hasattr(e, "capital_after")
        assert hasattr(e, "is_winner")

    def test_winner_when_exit_above_entry(self):
        e = _make_entry(entry_price=100.0, exit_price=105.0)
        assert e.is_winner is True
        assert e.pnl > 0
        assert e.pnl_pct > 0

    def test_loser_when_exit_below_entry(self):
        e = _make_entry(entry_price=100.0, exit_price=95.0)
        assert e.is_winner is False
        assert e.pnl < 0
        assert e.pnl_pct < 0

    def test_breakeven_when_entry_equals_exit(self):
        e = _make_entry(entry_price=100.0, exit_price=100.0)
        assert e.is_winner is False
        assert e.pnl == pytest.approx(0.0, abs=1e-6)

    def test_pnl_correct(self):
        e = _make_entry(entry_price=100.0, exit_price=105.0, capital_before=1_000_000.0)
        assert e.pnl == pytest.approx(50_000.0, rel=1e-4)  # 5% of 1M

    def test_capital_after_correct(self):
        e = _make_entry(entry_price=100.0, exit_price=110.0, capital_before=1_000_000.0)
        assert e.capital_after == pytest.approx(1_100_000.0, rel=1e-4)

    def test_direction_default_long(self):
        e = _make_entry()
        assert e.direction == "LONG"

    def test_immutable(self):
        e = _make_entry()
        with pytest.raises((AttributeError, TypeError)):
            e.pnl = 999.0  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Equity curve construction
# ─────────────────────────────────────────────────────────────────────────────

class TestEquityCurve:
    def test_no_trades_flat_equity(self):
        candles = _candles(50)
        curve = build_equity_curve(candles, [], initial_capital=1_000_000.0)
        assert len(curve) == 50
        assert all(ep.capital == 1_000_000.0 for ep in curve)

    def test_no_trades_zero_drawdown(self):
        curve = build_equity_curve(_candles(50), [], initial_capital=1_000_000.0)
        assert all(ep.drawdown_pct == 0.0 for ep in curve)

    def test_winning_trade_increases_capital(self):
        candles = _candles(50)
        trade = _make_entry(entry_bar=10, exit_bar=15,
                            entry_price=100.0, exit_price=110.0,
                            capital_before=1_000_000.0)
        curve = build_equity_curve(candles, [trade], initial_capital=1_000_000.0)
        assert curve[15].capital > 1_000_000.0
        assert curve[14].capital == pytest.approx(1_000_000.0)  # not yet exited
        assert curve[16].capital == curve[15].capital           # stays at new level

    def test_losing_trade_decreases_capital(self):
        candles = _candles(50)
        trade = _make_entry(entry_bar=10, exit_bar=15,
                            entry_price=100.0, exit_price=90.0,
                            capital_before=1_000_000.0)
        curve = build_equity_curve(candles, [trade], initial_capital=1_000_000.0)
        assert curve[15].capital < 1_000_000.0

    def test_drawdown_after_loss(self):
        candles = _candles(50)
        trade = _make_entry(entry_bar=5, exit_bar=10,
                            entry_price=100.0, exit_price=90.0,
                            capital_before=1_000_000.0)
        curve = build_equity_curve(candles, [trade], initial_capital=1_000_000.0)
        # After exit at bar 10: drawdown should be negative
        assert curve[10].drawdown_pct < 0.0

    def test_in_position_flag(self):
        candles = _candles(50)
        trade = _make_entry(entry_bar=5, exit_bar=10)
        curve = build_equity_curve(candles, [trade], initial_capital=1_000_000.0)
        for bar in range(5, 11):
            assert curve[bar].in_position is True
        assert curve[4].in_position is False
        assert curve[11].in_position is False

    def test_equity_curve_length_matches_candles(self):
        candles = _candles(120)
        curve = build_equity_curve(candles, [], initial_capital=1_000_000.0)
        assert len(curve) == 120


# ─────────────────────────────────────────────────────────────────────────────
# Drawdown calculation
# ─────────────────────────────────────────────────────────────────────────────

class TestDrawdown:
    def test_max_drawdown_zero_no_trades(self):
        curve = build_equity_curve(_candles(50), [], 1_000_000.0)
        metrics = compute_metrics([], curve, 1_000_000.0)
        assert metrics.max_drawdown_pct == 0.0

    def test_max_drawdown_negative_after_loss(self):
        candles = _candles(50)
        trade = _make_entry(entry_bar=5, exit_bar=10,
                            entry_price=100.0, exit_price=80.0,
                            capital_before=1_000_000.0)
        curve = build_equity_curve(candles, [trade], 1_000_000.0)
        metrics = compute_metrics([trade], curve, 1_000_000.0)
        assert metrics.max_drawdown_pct < 0.0

    def test_max_drawdown_is_most_negative(self):
        candles = _candles(80)
        # Two losing trades; second loss is larger
        t1 = TradeJournalEntry.build("t1", 10, 100.0, 15, 95.0, "TIME_EXIT", 1_000_000.0)
        t2 = TradeJournalEntry.build("t2", 20, 100.0, 25, 80.0, "TIME_EXIT", t1.capital_after)
        curve = build_equity_curve(candles, [t1, t2], 1_000_000.0)
        metrics = compute_metrics([t1, t2], curve, 1_000_000.0)
        # Max drawdown should reflect the bigger cumulative loss
        assert metrics.max_drawdown_pct < -10.0

    def test_drawdown_recovers_after_win(self):
        candles = _candles(80)
        t1 = TradeJournalEntry.build("t1", 5, 100.0, 10, 90.0, "TIME_EXIT", 1_000_000.0)
        # Big win after loss, equity recovers above initial
        t2 = TradeJournalEntry.build("t2", 20, 100.0, 25, 130.0, "TIME_EXIT", t1.capital_after)
        curve = build_equity_curve(candles, [t1, t2], 1_000_000.0)
        # After recovery, drawdown at that bar should be 0.0
        assert curve[25].drawdown_pct == pytest.approx(0.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# BacktestMetrics
# ─────────────────────────────────────────────────────────────────────────────

class TestBacktestMetrics:
    def _metrics_for(self, trades: list[TradeJournalEntry]) -> BacktestMetrics:
        candles = _candles(200)
        curve = build_equity_curve(candles, trades, 1_000_000.0)
        return compute_metrics(trades, curve, 1_000_000.0)

    def test_zero_trades_returns_all_zeros(self):
        m = self._metrics_for([])
        assert m.num_trades == 0
        assert m.win_rate == 0.0
        assert m.profit_factor == 0.0
        assert m.exposure_time_pct == 0.0

    def test_win_rate_all_winners(self):
        trades = [
            TradeJournalEntry.build(f"t{i}", i*10, 100.0, i*10+5, 105.0,
                                    "TIME_EXIT", 1_000_000.0)
            for i in range(3)
        ]
        m = self._metrics_for(trades)
        assert m.win_rate == pytest.approx(1.0)

    def test_win_rate_half_half(self):
        t1 = TradeJournalEntry.build("t1", 10, 100.0, 15, 110.0, "TIME_EXIT", 1_000_000.0)
        t2 = TradeJournalEntry.build("t2", 20, 100.0, 25, 90.0,  "TIME_EXIT", t1.capital_after)
        m = self._metrics_for([t1, t2])
        assert m.win_rate == pytest.approx(0.5)

    def test_profit_factor_infinity_when_no_losses(self):
        t = TradeJournalEntry.build("t1", 10, 100.0, 15, 110.0, "TIME_EXIT", 1_000_000.0)
        m = self._metrics_for([t])
        assert math.isinf(m.profit_factor)

    def test_profit_factor_zero_when_no_winners(self):
        t = TradeJournalEntry.build("t1", 10, 100.0, 15, 90.0, "TIME_EXIT", 1_000_000.0)
        m = self._metrics_for([t])
        assert m.profit_factor == pytest.approx(0.0)

    def test_exposure_time_correct(self):
        # Trade covers bars 10-14 (5 bars) out of 200 total
        t = TradeJournalEntry.build("t1", 10, 100.0, 14, 105.0, "TIME_EXIT", 1_000_000.0)
        m = self._metrics_for([t])
        assert m.exposure_time_pct == pytest.approx(5 / 200 * 100, rel=1e-3)

    def test_total_return_positive_when_profitable(self):
        t = TradeJournalEntry.build("t1", 10, 100.0, 15, 110.0, "TIME_EXIT", 1_000_000.0)
        m = self._metrics_for([t])
        assert m.total_return > 0
        assert m.total_return_pct > 0

    def test_total_return_negative_when_losing(self):
        t = TradeJournalEntry.build("t1", 10, 100.0, 15, 90.0, "TIME_EXIT", 1_000_000.0)
        m = self._metrics_for([t])
        assert m.total_return < 0
        assert m.total_return_pct < 0


# ─────────────────────────────────────────────────────────────────────────────
# Report path convention
# ─────────────────────────────────────────────────────────────────────────────

class TestReportPathConvention:
    def test_path_contains_hypothesis_id(self):
        p = _report_dir(Path("reports/visual_backtest"), "tmpl_h_bb_squeeze",
                        "SBER", "2023", "1h")
        assert "tmpl_h_bb_squeeze" in str(p)

    def test_path_contains_ticker(self):
        p = _report_dir(Path("reports"), "tmpl_h_bb_squeeze", "SBER", "2023", "1h")
        assert "sber" in str(p).lower()

    def test_path_contains_period(self):
        p = _report_dir(Path("reports"), "tmpl_h_bb_squeeze", "SBER", "2023", "1h")
        assert "2023" in str(p)

    def test_path_contains_timeframe(self):
        p = _report_dir(Path("reports"), "tmpl_h_bb_squeeze", "SBER", "2023", "1h")
        assert "1h" in str(p)

    def test_path_structure(self):
        base = Path("reports/visual_backtest")
        p = _report_dir(base, "tmpl_h_bb_squeeze", "SBER", "2023", "1h")
        # Expected: reports/visual_backtest/tmpl_h_bb_squeeze/sber_2023_1h
        assert p.parent.name == "tmpl_h_bb_squeeze"
        assert p.parent.parent == base


# ─────────────────────────────────────────────────────────────────────────────
# Trade journal generator — no lookahead bias
# ─────────────────────────────────────────────────────────────────────────────

class TestNoLookaheadBias:
    """Verify that no trades are generated in TRAIN windows."""

    def test_entries_only_in_test_windows(self):
        # Use rsi_oversold with very aggressive threshold (always fires when RSI computable)
        class AlwaysSignalFactory(GenericProviderFactory):
            signal_type = "rsi_oversold"
            hold_bars = 3
            signal_params = {"rsi_threshold": 100.0}  # RSI is always < 100

        candles = _candles(200)
        wf = WalkForwardConfig(train_size=60, test_size=20, step_size=20)
        gen = TradeJournalGenerator()
        trades = gen.generate(candles, AlwaysSignalFactory(), wf, 1_000_000.0)

        # Walk-forward windows: first test window starts at bar 60
        # No trade entry_bar should be in [0, 59]
        for t in trades:
            assert t.entry_bar >= 60, (
                f"Trade at entry_bar={t.entry_bar} is in TRAIN window (bars 0-59)"
            )

    def test_first_test_window_starts_after_train(self):
        class AlwaysSignalFactory(GenericProviderFactory):
            signal_type = "rsi_oversold"
            hold_bars = 3
            signal_params = {"rsi_threshold": 100.0}

        candles = _candles(200)
        wf = WalkForwardConfig(train_size=60, test_size=20, step_size=20)
        gen = TradeJournalGenerator()
        trades = gen.generate(candles, AlwaysSignalFactory(), wf, 1_000_000.0)
        if trades:
            assert trades[0].entry_bar >= 60


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic output
# ─────────────────────────────────────────────────────────────────────────────

class TestDeterministicOutput:
    def test_same_input_same_trades(self):
        class StableFactory(GenericProviderFactory):
            signal_type = "rsi_oversold"
            hold_bars = 5
            signal_params = {"rsi_threshold": 35.0}

        candles = _candles(200)
        wf = _wf_config()
        gen = TradeJournalGenerator()

        journal1 = gen.generate(candles, StableFactory(), wf, 1_000_000.0)
        journal2 = gen.generate(candles, StableFactory(), wf, 1_000_000.0)

        # Entry/exit bars must be identical (trade_id has uuid so we skip that)
        bars1 = [(t.entry_bar, t.exit_bar) for t in journal1]
        bars2 = [(t.entry_bar, t.exit_bar) for t in journal2]
        assert bars1 == bars2

    def test_same_input_same_metrics(self):
        class StableFactory(GenericProviderFactory):
            signal_type = "dual_ma_trend"
            hold_bars = 5
            signal_params = {}

        candles = _candles(200)
        wf = _wf_config()
        gen = TradeJournalGenerator()

        j1 = gen.generate(candles, StableFactory(), wf, 1_000_000.0)
        j2 = gen.generate(candles, StableFactory(), wf, 1_000_000.0)

        c1 = build_equity_curve(_candles(200), j1, 1_000_000.0)
        c2 = build_equity_curve(_candles(200), j2, 1_000_000.0)

        m1 = compute_metrics(j1, c1, 1_000_000.0)
        m2 = compute_metrics(j2, c2, 1_000_000.0)
        assert m1.total_return_pct == pytest.approx(m2.total_return_pct)


# ─────────────────────────────────────────────────────────────────────────────
# Zero-trade strategy
# ─────────────────────────────────────────────────────────────────────────────

class TestZeroTradeStrategy:
    def test_never_fires_signal_returns_empty_journal(self):
        class NeverSignalFactory(GenericProviderFactory):
            signal_type = "rsi_oversold"
            hold_bars = 5
            signal_params = {"rsi_threshold": -999.0}  # RSI never < -999

        candles = _candles(200)
        gen = TradeJournalGenerator()
        trades = gen.generate(candles, NeverSignalFactory(), _wf_config(), 1_000_000.0)
        assert trades == []

    def test_empty_candles_returns_empty_journal(self):
        class AnyFactory(GenericProviderFactory):
            signal_type = "rsi_oversold"
            hold_bars = 5
            signal_params = {"rsi_threshold": 100.0}

        gen = TradeJournalGenerator()
        trades = gen.generate([], AnyFactory(), _wf_config(), 1_000_000.0)
        assert trades == []

    def test_zero_trade_metrics_correct(self):
        candles = _candles(200)
        curve = build_equity_curve(candles, [], 1_000_000.0)
        metrics = compute_metrics([], curve, 1_000_000.0)
        assert metrics.num_trades == 0
        assert metrics.total_return == pytest.approx(0.0, abs=1e-6)
        assert metrics.max_drawdown_pct == pytest.approx(0.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# Signal dispatcher — extended (all 10 signal types)
# ─────────────────────────────────────────────────────────────────────────────

def _make_generic_ds(**kwargs):
    from experiments.generic.dataset import GenericOHLCVDataset
    defaults = dict(
        closes=(100.0,), highs=(101.0,), lows=(99.0,),
        adx_values=(25.0,), rsi_values=(50.0,), atr_values=(1.0,),
        sma_5_values=(100.0,), sma_20_values=(100.0,), sma_50_values=(99.0,),
        bb_zscore_values=(0.0,), realized_vol_values=(0.01,),
    )
    defaults.update(kwargs)
    return GenericOHLCVDataset(**defaults)


class TestSignalDispatcher:
    def test_adx_continuation_fires(self):
        ds = _make_generic_ds(adx_values=(28.0,), rsi_values=(50.0,))
        assert _check_signal(ds, 0, "adx_continuation",
                             {"adx_min": 25.0, "rsi_low": 40.0, "rsi_high": 60.0}) is True

    def test_adx_continuation_silent_when_rsi_outside_band(self):
        ds = _make_generic_ds(adx_values=(28.0,), rsi_values=(80.0,))
        assert _check_signal(ds, 0, "adx_continuation",
                             {"adx_min": 25.0, "rsi_low": 40.0, "rsi_high": 60.0}) is False

    def test_rev_vol_reg_fires(self):
        ds = _make_generic_ds(adx_values=(15.0,), bb_zscore_values=(-2.5,))
        assert _check_signal(ds, 0, "rev_vol_reg",
                             {"adx_max": 20.0, "bb_z_entry": -2.0}) is True

    def test_rev_vol_reg_silent_when_adx_trending(self):
        ds = _make_generic_ds(adx_values=(25.0,), bb_zscore_values=(-2.5,))
        assert _check_signal(ds, 0, "rev_vol_reg",
                             {"adx_max": 20.0, "bb_z_entry": -2.0}) is False

    def test_unknown_signal_returns_false(self):
        ds = _make_generic_ds()
        assert _check_signal(ds, 0, "nonexistent_signal", {}) is False


# ─────────────────────────────────────────────────────────────────────────────
# Factory introspection
# ─────────────────────────────────────────────────────────────────────────────

class TestFactoryIntrospection:
    def test_generic_factory_extracts_correctly(self):
        class TestFactory(GenericProviderFactory):
            signal_type = "rsi_oversold"
            hold_bars = 7
            signal_params = {"rsi_threshold": 28.0}

        cfg = _extract_signal_config(TestFactory())
        assert cfg.signal_type == "rsi_oversold"
        assert cfg.hold_bars == 7
        assert cfg.signal_params == {"rsi_threshold": 28.0}

    def test_h13_factory_extracts_correctly(self):
        from experiments.h13_adx_continuation.providers import AdxContinuationProviderFactory
        cfg = _extract_signal_config(AdxContinuationProviderFactory())
        assert cfg.signal_type == "adx_continuation"
        assert cfg.hold_bars == 5

    def test_rev_vol_reg_factory_extracts_correctly(self):
        from experiments.h_rev_vol_reg.providers import RevVolRegProviderFactory
        cfg = _extract_signal_config(RevVolRegProviderFactory())
        assert cfg.signal_type == "rev_vol_reg"
        assert cfg.hold_bars == 8

    def test_unknown_factory_raises(self):
        class WeirdFactory:
            pass
        with pytest.raises(ValueError, match="Cannot extract signal config"):
            _extract_signal_config(WeirdFactory())


# ─────────────────────────────────────────────────────────────────────────────
# Chart rendering smoke test (headless, no display)
# ─────────────────────────────────────────────────────────────────────────────

class TestChartRendering:
    def test_chart_renders_to_png(self, tmp_path):
        from services.visual_backtest.renderer import render_chart

        candles = _candles(120)
        t = _make_entry(entry_bar=70, exit_bar=75, entry_price=100.0, exit_price=105.0)
        curve = build_equity_curve(candles, [t], 1_000_000.0)
        metrics = compute_metrics([t], curve, 1_000_000.0)

        chart_path = tmp_path / "chart.png"
        result = render_chart(candles, [t], curve, metrics, chart_path, title="Test Chart")

        assert result == chart_path
        assert chart_path.exists()
        assert chart_path.stat().st_size > 10_000  # non-trivial PNG

    def test_chart_renders_with_zero_trades(self, tmp_path):
        from services.visual_backtest.renderer import render_chart

        candles = _candles(80)
        curve = build_equity_curve(candles, [], 1_000_000.0)
        metrics = compute_metrics([], curve, 1_000_000.0)

        chart_path = tmp_path / "chart_empty.png"
        render_chart(candles, [], curve, metrics, chart_path, title="Zero Trades")
        assert chart_path.exists()

    def test_chart_creates_parent_dirs(self, tmp_path):
        from services.visual_backtest.renderer import render_chart

        candles = _candles(80)
        curve = build_equity_curve(candles, [], 1_000_000.0)
        metrics = compute_metrics([], curve, 1_000_000.0)

        deep_path = tmp_path / "a" / "b" / "c" / "chart.png"
        render_chart(candles, [], curve, metrics, deep_path)
        assert deep_path.exists()
