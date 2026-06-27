"""Tests for RegimeDetectionAgent — Layer 2 Analysis Agent.

All tests use FixtureRegimeSource — no HTTP calls, no real disk data.
Covers: protocol compliance, math helpers, classification rules,
segment generation, missing data, persistence, and determinism.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from agents.analysis.regime import (
    DEFAULT_WINDOW,
    FixtureRegimeSource,
    RegimeDetectionAgent,
    _classify_risk,
    _classify_trend,
    _classify_volatility,
    _linear_slope,
    _percentile,
    _realized_vol,
    _returns_from_closes,
    _rolling_rvs,
    _segment_dates,
    _to_daily_series,
)
from agents.models import (
    AgentResult,
    RegimeLabel,
    RegimeSegment,
    RegimeSnapshot,
)


# ---------------------------------------------------------------------------
# Fixture factories
# ---------------------------------------------------------------------------

# 30 trading dates — enough for one full window (21) plus a tail window (9)
_DATES_30 = [
    "2023-01-03", "2023-01-04", "2023-01-05", "2023-01-09", "2023-01-10",
    "2023-01-11", "2023-01-12", "2023-01-13", "2023-01-16", "2023-01-17",
    "2023-01-18", "2023-01-19", "2023-01-20", "2023-01-23", "2023-01-24",
    "2023-01-25", "2023-01-26", "2023-01-27", "2023-01-30", "2023-01-31",
    "2023-02-01", "2023-02-02", "2023-02-03", "2023-02-06", "2023-02-07",
    "2023-02-08", "2023-02-09", "2023-02-10", "2023-02-13", "2023-02-14",
]


def _rows_from(dates: list[str], closes: list[float]) -> list[dict]:
    return [{"date": d, "close": c} for d, c in zip(dates, closes)]


# monotonically increasing — expected TREND_UP (large window)
_TREND_UP_CLOSES = [100.0 + i * 1.0 for i in range(30)]
# monotonically decreasing — expected TREND_DOWN
_TREND_DOWN_CLOSES = [130.0 - i * 1.0 for i in range(30)]
# flat oscillating around 100 — expected RANGE
_RANGE_CLOSES = [100.0 + (0.2 if i % 2 == 0 else -0.2) for i in range(30)]

# macro: IMOEX up, USDRUB down → RISK_ON
_IMOEX_UP = [2200.0 + i * 5.0 for i in range(30)]
_USDRUB_DOWN = [70.0 - i * 0.1 for i in range(30)]
_RGBI_UP = [110.0 + i * 0.1 for i in range(30)]

# macro: IMOEX down, USDRUB up → RISK_OFF
_IMOEX_DOWN = [2350.0 - i * 5.0 for i in range(30)]
_USDRUB_UP = [65.0 + i * 0.2 for i in range(30)]
_RGBI_DOWN = [112.0 - i * 0.1 for i in range(30)]


def _trend_up_source() -> FixtureRegimeSource:
    return FixtureRegimeSource(
        {"SBER": _rows_from(_DATES_30, _TREND_UP_CLOSES)},
        {
            "IMOEX": _rows_from(_DATES_30, _IMOEX_UP),
            "USDRUB": _rows_from(_DATES_30, _USDRUB_DOWN),
            "RGBI": _rows_from(_DATES_30, _RGBI_UP),
        },
    )


def _trend_down_source() -> FixtureRegimeSource:
    return FixtureRegimeSource(
        {"SBER": _rows_from(_DATES_30, _TREND_DOWN_CLOSES)},
        {
            "IMOEX": _rows_from(_DATES_30, _IMOEX_DOWN),
            "USDRUB": _rows_from(_DATES_30, _USDRUB_UP),
            "RGBI": _rows_from(_DATES_30, _RGBI_DOWN),
        },
    )


def _range_source() -> FixtureRegimeSource:
    return FixtureRegimeSource(
        {"SBER": _rows_from(_DATES_30, _RANGE_CLOSES)},
        {
            "IMOEX": _rows_from(_DATES_30, _IMOEX_UP),
            "USDRUB": _rows_from(_DATES_30, _USDRUB_DOWN),
            "RGBI": _rows_from(_DATES_30, _RGBI_UP),
        },
    )


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 27, 12, 0, 0)


# ---------------------------------------------------------------------------
# FixtureRegimeSource
# ---------------------------------------------------------------------------

class TestFixtureRegimeSource:
    def test_load_instrument_returns_data(self) -> None:
        rows = _rows_from(_DATES_30[:5], [100.0] * 5)
        src = FixtureRegimeSource({"SBER": rows}, {})
        assert len(src.load_instrument("SBER", "2023")) == 5

    def test_load_instrument_empty_for_unknown(self) -> None:
        src = FixtureRegimeSource({}, {})
        assert src.load_instrument("GAZP", "2023") == []

    def test_load_macro_returns_data(self) -> None:
        rows = _rows_from(_DATES_30[:5], [2200.0] * 5)
        src = FixtureRegimeSource({}, {"IMOEX": rows})
        assert len(src.load_macro_symbol("IMOEX", "2023")) == 5

    def test_load_macro_empty_for_unknown(self) -> None:
        src = FixtureRegimeSource({}, {})
        assert src.load_macro_symbol("BRENT", "2023") == []

    def test_does_not_mutate_source(self) -> None:
        rows = _rows_from(_DATES_30[:3], [100.0, 101.0, 102.0])
        src = FixtureRegimeSource({"SBER": rows}, {})
        fetched = src.load_instrument("SBER", "2023")
        fetched.clear()
        assert len(src.load_instrument("SBER", "2023")) == 3


# ---------------------------------------------------------------------------
# RegimeDetectionAgent protocol compliance
# ---------------------------------------------------------------------------

class TestRegimeAgentProtocol:
    def test_agent_id(self, tmp_path: Path) -> None:
        assert RegimeDetectionAgent(tmp_path).agent_id == "regime-detection-agent"

    def test_agent_type_is_analysis(self, tmp_path: Path) -> None:
        assert RegimeDetectionAgent(tmp_path).agent_type == "ANALYSIS"

    def test_version_is_string(self, tmp_path: Path) -> None:
        assert isinstance(RegimeDetectionAgent(tmp_path).version, str)

    def test_run_is_callable(self, tmp_path: Path) -> None:
        assert callable(RegimeDetectionAgent(tmp_path).run)


# ---------------------------------------------------------------------------
# _linear_slope
# ---------------------------------------------------------------------------

class TestLinearSlope:
    def test_flat_series_zero_slope(self) -> None:
        assert _linear_slope([5.0, 5.0, 5.0, 5.0]) == pytest.approx(0.0)

    def test_ascending_positive(self) -> None:
        slope = _linear_slope([1.0, 2.0, 3.0, 4.0, 5.0])
        assert slope == pytest.approx(1.0)

    def test_descending_negative(self) -> None:
        slope = _linear_slope([5.0, 4.0, 3.0, 2.0, 1.0])
        assert slope == pytest.approx(-1.0)

    def test_single_element_zero(self) -> None:
        assert _linear_slope([42.0]) == 0.0

    def test_two_elements_exact(self) -> None:
        slope = _linear_slope([10.0, 20.0])
        assert slope == pytest.approx(10.0)

    def test_large_values_normalized_ok(self) -> None:
        closes = [2200.0 + i * 5.0 for i in range(10)]
        slope = _linear_slope(closes)
        assert slope == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# _realized_vol
# ---------------------------------------------------------------------------

class TestRealizedVol:
    def test_empty_returns_zero(self) -> None:
        assert _realized_vol([]) == 0.0

    def test_single_return_zero(self) -> None:
        assert _realized_vol([0.01]) == 0.0

    def test_constant_returns_zero(self) -> None:
        assert _realized_vol([0.01, 0.01, 0.01, 0.01]) == 0.0

    def test_positive_result(self) -> None:
        rets = [0.01, -0.02, 0.03, -0.01, 0.02]
        rv = _realized_vol(rets)
        assert rv > 0.0

    def test_annualization_scales(self) -> None:
        rets = [0.01, -0.01, 0.01, -0.01, 0.01, -0.01]
        rv252 = _realized_vol(rets, ann=252.0)
        rv1 = _realized_vol(rets, ann=1.0)
        assert abs(rv252 - rv1 * math.sqrt(252.0)) < 1e-10


# ---------------------------------------------------------------------------
# _percentile
# ---------------------------------------------------------------------------

class TestPercentile:
    def test_single_value(self) -> None:
        assert _percentile([5.0], 50) == 5.0

    def test_p0_is_min(self) -> None:
        assert _percentile([1.0, 2.0, 3.0], 0) == pytest.approx(1.0)

    def test_p100_is_max(self) -> None:
        assert _percentile([1.0, 2.0, 3.0], 100) == pytest.approx(3.0)

    def test_p50_is_median(self) -> None:
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == pytest.approx(3.0)

    def test_p25_p75_bracket(self) -> None:
        values = list(range(1, 101))  # 1..100
        p25 = _percentile([float(v) for v in values], 25)
        p75 = _percentile([float(v) for v in values], 75)
        assert p25 < p75

    def test_empty_returns_zero(self) -> None:
        assert _percentile([], 50) == 0.0


# ---------------------------------------------------------------------------
# _returns_from_closes
# ---------------------------------------------------------------------------

class TestReturnsFromCloses:
    def test_basic(self) -> None:
        rets = _returns_from_closes([100.0, 102.0])
        assert rets == pytest.approx([0.02])

    def test_count_is_n_minus_one(self) -> None:
        assert len(_returns_from_closes([1.0, 2.0, 3.0, 4.0])) == 3

    def test_zero_close_skipped(self) -> None:
        rets = _returns_from_closes([0.0, 100.0, 102.0])
        assert len(rets) == 1

    def test_empty_input(self) -> None:
        assert _returns_from_closes([]) == []


# ---------------------------------------------------------------------------
# _classify_trend
# ---------------------------------------------------------------------------

class TestClassifyTrend:
    def test_monotone_up_gives_trend_up(self) -> None:
        closes = [100.0 + i * 2.0 for i in range(21)]
        label, conf, _ = _classify_trend(closes)
        assert label == RegimeLabel.TREND_UP
        assert conf > 0.0

    def test_monotone_down_gives_trend_down(self) -> None:
        closes = [140.0 - i * 2.0 for i in range(21)]
        label, conf, _ = _classify_trend(closes)
        assert label == RegimeLabel.TREND_DOWN
        assert conf > 0.0

    def test_flat_oscillation_gives_range(self) -> None:
        closes = [100.0 + (0.1 if i % 2 == 0 else -0.1) for i in range(21)]
        label, _, _ = _classify_trend(closes)
        assert label == RegimeLabel.RANGE

    def test_single_value_gives_range(self) -> None:
        label, conf, _ = _classify_trend([100.0])
        assert label == RegimeLabel.RANGE
        assert conf == 0.0

    def test_metrics_contains_slope_and_sma_position(self) -> None:
        _, _, metrics = _classify_trend([100.0 + i for i in range(10)])
        names = {m[0] for m in metrics}
        assert "slope_normalized" in names
        assert "sma_position" in names

    def test_confidence_in_range(self) -> None:
        for closes in [
            [100.0 + i for i in range(21)],
            [100.0 - i * 0.5 for i in range(21)],
            [100.0] * 21,
        ]:
            _, conf, _ = _classify_trend(closes)
            assert 0.0 <= conf <= 1.0

    def test_strong_trend_higher_confidence_than_weak(self) -> None:
        strong = [100.0 + i * 5.0 for i in range(21)]  # large slope
        weak = [100.0 + i * 0.15 for i in range(21)]   # barely above threshold
        _, conf_strong, _ = _classify_trend(strong)
        _, conf_weak, _ = _classify_trend(weak)
        assert conf_strong >= conf_weak


# ---------------------------------------------------------------------------
# _classify_volatility
# ---------------------------------------------------------------------------

class TestClassifyVolatility:
    def _rets_low(self, n: int = 20) -> list[float]:
        """Very small alternating returns → low realised vol."""
        return [0.001 * (1 if i % 2 == 0 else -1) for i in range(n)]

    def _rets_high(self, n: int = 20) -> list[float]:
        """Large alternating returns → high realised vol."""
        return [0.05 * (1 if i % 2 == 0 else -1) for i in range(n)]

    def test_low_rv_below_p25_gives_low_vol(self) -> None:
        rets = self._rets_low()
        rv = _realized_vol(rets)
        p25 = rv * 1.5   # make p25 clearly above rv
        p75 = rv * 3.0
        label, _, _ = _classify_volatility(rets, p25, p75)
        assert label == RegimeLabel.LOW_VOL

    def test_high_rv_above_p75_gives_high_vol(self) -> None:
        rets = self._rets_high()
        rv = _realized_vol(rets)
        p25 = rv * 0.3
        p75 = rv * 0.7  # p75 clearly below rv
        label, _, _ = _classify_volatility(rets, p25, p75)
        assert label == RegimeLabel.HIGH_VOL

    def test_between_percentiles_gives_normal_vol(self) -> None:
        rets = [0.01 * (1 if i % 2 == 0 else -1) for i in range(20)]
        rv = _realized_vol(rets)
        p25 = rv * 0.5
        p75 = rv * 1.5  # rv is between p25 and p75
        label, _, _ = _classify_volatility(rets, p25, p75)
        assert label == RegimeLabel.NORMAL_VOL

    def test_zero_percentiles_gives_normal_vol(self) -> None:
        label, conf, _ = _classify_volatility([0.01], 0.0, 0.0)
        assert label == RegimeLabel.NORMAL_VOL
        assert conf == 0.0

    def test_confidence_in_range(self) -> None:
        for rets, p25, p75 in [
            (self._rets_low(), 0.5, 0.9),
            (self._rets_high(), 0.1, 0.3),
            ([0.01, -0.01] * 5, 0.05, 0.3),
        ]:
            _, conf, _ = _classify_volatility(rets, p25, p75)
            assert 0.0 <= conf <= 1.0

    def test_metrics_contains_rv_p25_p75(self) -> None:
        _, _, metrics = _classify_volatility([0.01] * 10, 0.1, 0.5)
        names = {m[0] for m in metrics}
        assert "realized_vol" in names
        assert "p25" in names
        assert "p75" in names


# ---------------------------------------------------------------------------
# _classify_risk
# ---------------------------------------------------------------------------

class TestClassifyRisk:
    def _up(self, base: float = 100.0, n: int = 10) -> list[float]:
        return [base + i * 1.0 for i in range(n)]

    def _down(self, base: float = 110.0, n: int = 10) -> list[float]:
        return [base - i * 1.0 for i in range(n)]

    def _flat(self, val: float = 100.0, n: int = 10) -> list[float]:
        return [val] * n

    def test_imoex_up_usdrub_down_gives_risk_on(self) -> None:
        label, _, _ = _classify_risk(self._up(2200), self._down(70))
        assert label == RegimeLabel.RISK_ON

    def test_imoex_down_usdrub_up_gives_risk_off(self) -> None:
        label, _, _ = _classify_risk(self._down(2300), self._up(65))
        assert label == RegimeLabel.RISK_OFF

    def test_empty_imoex_gives_neutral(self) -> None:
        label, conf, _ = _classify_risk([], self._up())
        assert label == RegimeLabel.NEUTRAL
        assert conf == 0.0

    def test_mixed_signals_give_neutral(self) -> None:
        # imoex up → risk_on vote; usdrub up → risk_off vote → tie → NEUTRAL
        label, _, _ = _classify_risk(self._up(2200), self._up(65))
        assert label == RegimeLabel.NEUTRAL

    def test_risk_on_confidence_proportion(self) -> None:
        # No RGBI: 2 signals, both risk_on → confidence = 2/2 = 1.0
        label, conf, _ = _classify_risk(self._up(2200), self._down(70))
        assert label == RegimeLabel.RISK_ON
        assert conf == pytest.approx(1.0)

    def test_risk_off_with_rgbi(self) -> None:
        # IMOEX down, USDRUB up, RGBI down → 3/3 risk_off votes → confidence = 1.0
        label, conf, _ = _classify_risk(
            self._down(2300), self._up(65), self._down(112)
        )
        assert label == RegimeLabel.RISK_OFF
        assert conf == pytest.approx(1.0)

    def test_metrics_present(self) -> None:
        _, _, metrics = _classify_risk(self._up(2200), self._down(70))
        names = {m[0] for m in metrics}
        assert "imoex_slope_norm" in names
        assert "usdrub_slope_norm" in names

    def test_confidence_in_range(self) -> None:
        for imoex, usdrub in [
            (self._up(), self._down()),
            (self._down(), self._up()),
            (self._flat(), self._flat()),
        ]:
            _, conf, _ = _classify_risk(imoex, usdrub)
            assert 0.0 <= conf <= 1.0


# ---------------------------------------------------------------------------
# _segment_dates
# ---------------------------------------------------------------------------

class TestSegmentDates:
    def test_exact_multiple_produces_equal_windows(self) -> None:
        dates = [f"d{i}" for i in range(21)]
        segs = _segment_dates(dates, 21)
        assert len(segs) == 1
        assert segs[0] == (0, 21)

    def test_tail_segment_smaller(self) -> None:
        dates = [f"d{i}" for i in range(25)]
        segs = _segment_dates(dates, 21)
        assert len(segs) == 2
        assert segs[0] == (0, 21)
        assert segs[1] == (21, 25)

    def test_empty_dates(self) -> None:
        assert _segment_dates([], 21) == []

    def test_window_larger_than_data(self) -> None:
        dates = [f"d{i}" for i in range(5)]
        segs = _segment_dates(dates, 21)
        assert len(segs) == 1
        assert segs[0] == (0, 5)


# ---------------------------------------------------------------------------
# RegimeDetectionAgent — fixture run (trend up)
# ---------------------------------------------------------------------------

class TestRegimeAgentFixtureRun:
    def _run(self, tmp_path: Path, src=None) -> AgentResult:
        src = src or _trend_up_source()
        agent = RegimeDetectionAgent(tmp_path, source=src)
        return agent.run("SBER", "2023", window=21, _clock=_fixed_clock)

    def test_returns_agent_result(self, tmp_path: Path) -> None:
        assert isinstance(self._run(tmp_path), AgentResult)

    def test_agent_id(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_id == "regime-detection-agent"

    def test_agent_type_is_analysis(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_type == "ANALYSIS"

    def test_output_is_regime_snapshot(self, tmp_path: Path) -> None:
        assert isinstance(self._run(tmp_path).output, RegimeSnapshot)

    def test_created_at_uses_injected_clock(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).created_at == "2026-06-27T12:00:00"

    def test_snapshot_id_format(self, tmp_path: Path) -> None:
        snap: RegimeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.snapshot_id == "regime_SBER_2023"

    def test_segments_count(self, tmp_path: Path) -> None:
        # 30 dates / window=21 → 2 date-windows → 2 × 3 regime types = 6 segments
        snap: RegimeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert len(snap.segments) == 6

    def test_three_regime_types_present(self, tmp_path: Path) -> None:
        snap: RegimeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        types = {s.regime_type for s in snap.segments}
        assert types == {"trend", "volatility", "risk"}

    def test_trend_up_detected_in_first_window(self, tmp_path: Path) -> None:
        snap: RegimeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        trend_segs = [s for s in snap.segments if s.regime_type == "trend"]
        # first window: prices monotonically increasing → TREND_UP
        assert trend_segs[0].label == RegimeLabel.TREND_UP

    def test_risk_on_detected_with_imoex_up_usdrub_down(self, tmp_path: Path) -> None:
        snap: RegimeSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        risk_segs = [s for s in snap.segments if s.regime_type == "risk"]
        # IMOEX up, USDRUB down → RISK_ON
        assert all(s.label == RegimeLabel.RISK_ON for s in risk_segs)

    def test_trend_down_detected_in_down_source(self, tmp_path: Path) -> None:
        agent = RegimeDetectionAgent(tmp_path, source=_trend_down_source())
        snap: RegimeSnapshot = agent.run(
            "SBER", "2023", window=21, _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        trend_segs = [s for s in snap.segments if s.regime_type == "trend"]
        assert trend_segs[0].label == RegimeLabel.TREND_DOWN

    def test_risk_off_detected_in_down_source(self, tmp_path: Path) -> None:
        agent = RegimeDetectionAgent(tmp_path, source=_trend_down_source())
        snap: RegimeSnapshot = agent.run(
            "SBER", "2023", window=21, _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        risk_segs = [s for s in snap.segments if s.regime_type == "risk"]
        assert all(s.label == RegimeLabel.RISK_OFF for s in risk_segs)

    def test_range_detected_in_flat_source(self, tmp_path: Path) -> None:
        agent = RegimeDetectionAgent(tmp_path, source=_range_source())
        snap: RegimeSnapshot = agent.run(
            "SBER", "2023", window=21, _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        trend_segs = [s for s in snap.segments if s.regime_type == "trend"]
        assert trend_segs[0].label == RegimeLabel.RANGE

    def test_confidence_positive(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        assert result.confidence.value > 0.0

    def test_evidence_includes_instrument(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        sources = {e.source for e in result.evidence}
        assert any("instrument" in s for s in sources)


# ---------------------------------------------------------------------------
# Segment structure
# ---------------------------------------------------------------------------

class TestSegmentStructure:
    def _segments(self, tmp_path: Path, src=None) -> list[RegimeSegment]:
        src = src or _trend_up_source()
        agent = RegimeDetectionAgent(tmp_path, source=src)
        snap: RegimeSnapshot = agent.run(
            "SBER", "2023", window=21, _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        return list(snap.segments)

    def test_each_segment_has_date_from_and_to(self, tmp_path: Path) -> None:
        for s in self._segments(tmp_path):
            assert isinstance(s.date_from, str)
            assert isinstance(s.date_to, str)
            assert s.date_from <= s.date_to

    def test_each_segment_confidence_in_range(self, tmp_path: Path) -> None:
        for s in self._segments(tmp_path):
            assert 0.0 <= s.confidence <= 1.0

    def test_each_segment_has_metrics(self, tmp_path: Path) -> None:
        for s in self._segments(tmp_path):
            assert isinstance(s.metrics, tuple)

    def test_each_segment_label_is_known(self, tmp_path: Path) -> None:
        all_labels = RegimeLabel._TREND | RegimeLabel._VOLATILITY | RegimeLabel._RISK
        for s in self._segments(tmp_path):
            assert s.label in all_labels

    def test_first_window_date_from_is_first_date(self, tmp_path: Path) -> None:
        segs = self._segments(tmp_path)
        first_trend = next(s for s in segs if s.regime_type == "trend")
        assert first_trend.date_from == _DATES_30[0]


# ---------------------------------------------------------------------------
# Missing data handling
# ---------------------------------------------------------------------------

class TestMissingDataHandling:
    def test_no_instrument_gives_empty_segments(self, tmp_path: Path) -> None:
        src = FixtureRegimeSource({}, {"IMOEX": _rows_from(_DATES_30, _IMOEX_UP)})
        agent = RegimeDetectionAgent(tmp_path, source=src)
        snap: RegimeSnapshot = agent.run(
            "SBER", "2023", _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        assert snap.segments == ()

    def test_no_macro_gives_neutral_risk(self, tmp_path: Path) -> None:
        src = FixtureRegimeSource(
            {"SBER": _rows_from(_DATES_30, _TREND_UP_CLOSES)},
            {},   # no macro
        )
        agent = RegimeDetectionAgent(tmp_path, source=src)
        snap: RegimeSnapshot = agent.run(
            "SBER", "2023", window=21, _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        risk_segs = [s for s in snap.segments if s.regime_type == "risk"]
        assert all(s.label == RegimeLabel.NEUTRAL for s in risk_segs)

    def test_partial_macro_still_runs(self, tmp_path: Path) -> None:
        src = FixtureRegimeSource(
            {"SBER": _rows_from(_DATES_30, _TREND_UP_CLOSES)},
            {"IMOEX": _rows_from(_DATES_30, _IMOEX_UP)},  # only IMOEX
        )
        agent = RegimeDetectionAgent(tmp_path, source=src)
        result = agent.run("SBER", "2023", window=21, _clock=_fixed_clock)
        assert isinstance(result.output, RegimeSnapshot)

    def test_single_bar_instrument(self, tmp_path: Path) -> None:
        src = FixtureRegimeSource(
            {"SBER": [{"date": "2023-01-03", "close": 100.0}]},
            {"IMOEX": _rows_from(_DATES_30, _IMOEX_UP)},
        )
        agent = RegimeDetectionAgent(tmp_path, source=src)
        result = agent.run("SBER", "2023", window=21, _clock=_fixed_clock)
        snap: RegimeSnapshot = result.output  # type: ignore[assignment]
        # one window → 3 segments
        assert len(snap.segments) == 3


# ---------------------------------------------------------------------------
# Volatility — mixed high/low series
# ---------------------------------------------------------------------------

class TestVolatilityRegime:
    """Build a series with clearly different vol regimes in two windows."""

    def _mixed_vol_source(self, n_low: int = 21, n_high: int = 21) -> FixtureRegimeSource:
        """First n_low bars: ±0.1% (low vol). Next n_high bars: ±5% (high vol)."""
        n_total = n_low + n_high
        dates = _DATES_30[:n_total] if n_total <= len(_DATES_30) else _DATES_30
        base = 100.0
        closes = [base]
        for i in range(len(dates) - 1):
            if i < n_low:
                factor = 1.001 if i % 2 == 0 else 0.999
            else:
                factor = 1.05 if i % 2 == 0 else 0.95
            closes.append(closes[-1] * factor)
        # trim to dates length
        closes = closes[:len(dates)]
        return FixtureRegimeSource(
            {"SBER": _rows_from(dates, closes)},
            {
                "IMOEX": _rows_from(dates, [2200.0 + i for i in range(len(dates))]),
                "USDRUB": _rows_from(dates, [70.0 - i * 0.05 for i in range(len(dates))]),
            },
        )

    def test_first_window_lower_vol_than_second(self, tmp_path: Path) -> None:
        src = self._mixed_vol_source(n_low=21, n_high=9)
        agent = RegimeDetectionAgent(tmp_path, source=src)
        snap: RegimeSnapshot = agent.run(
            "SBER", "2023", window=21, _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        vol_segs = [s for s in snap.segments if s.regime_type == "volatility"]
        # First window: low vol → first RV metric should be smaller
        rv1 = dict(vol_segs[0].metrics).get("realized_vol", 0.0)
        rv2 = dict(vol_segs[1].metrics).get("realized_vol", 0.0)
        assert rv1 < rv2


# ---------------------------------------------------------------------------
# Persistence — JSON
# ---------------------------------------------------------------------------

class TestPersistence:
    def _run_and_get_path(self, tmp_path: Path) -> tuple[RegimeSnapshot, Path]:
        agent = RegimeDetectionAgent(tmp_path, source=_trend_up_source())
        snap: RegimeSnapshot = agent.run(
            "SBER", "2023", window=21, _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        json_path = tmp_path / "context" / "regime" / "sber_2023.json"
        return snap, json_path

    def test_json_file_created(self, tmp_path: Path) -> None:
        _, path = self._run_and_get_path(tmp_path)
        assert path.exists()

    def test_json_in_context_regime_dir(self, tmp_path: Path) -> None:
        _, path = self._run_and_get_path(tmp_path)
        assert "context" in str(path)
        assert "regime" in str(path)

    def test_json_contains_snapshot_id(self, tmp_path: Path) -> None:
        _, path = self._run_and_get_path(tmp_path)
        with open(path) as f:
            data = json.load(f)
        assert data["snapshot_id"] == "regime_SBER_2023"

    def test_json_contains_segments(self, tmp_path: Path) -> None:
        _, path = self._run_and_get_path(tmp_path)
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data["segments"], list)
        assert len(data["segments"]) == 6

    def test_segment_has_required_keys(self, tmp_path: Path) -> None:
        _, path = self._run_and_get_path(tmp_path)
        with open(path) as f:
            data = json.load(f)
        seg = data["segments"][0]
        for key in ("regime_type", "label", "date_from", "date_to", "confidence", "metrics"):
            assert key in seg

    def test_second_run_overwrites(self, tmp_path: Path) -> None:
        agent = RegimeDetectionAgent(tmp_path, source=_trend_up_source())
        agent.run("SBER", "2023", window=21, _clock=_fixed_clock)
        agent.run("SBER", "2023", window=21, _clock=_fixed_clock)  # no error
        path = tmp_path / "context" / "regime" / "sber_2023.json"
        assert path.exists()

    def test_separate_from_datasets_dir(self, tmp_path: Path) -> None:
        _, path = self._run_and_get_path(tmp_path)
        expected_root = str((tmp_path / "context" / "regime").resolve())
        assert str(path.resolve()).startswith(expected_root)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_clock_same_created_at(self, tmp_path: Path) -> None:
        agent = RegimeDetectionAgent(tmp_path, source=_trend_up_source())
        r1 = agent.run("SBER", "2023", window=21, _clock=lambda: datetime(2026, 1, 1))
        r2 = agent.run("SBER", "2023", window=21, _clock=lambda: datetime(2026, 1, 1))
        assert r1.created_at == r2.created_at

    def test_same_data_same_labels(self, tmp_path: Path) -> None:
        agent = RegimeDetectionAgent(tmp_path, source=_trend_up_source())
        s1: RegimeSnapshot = agent.run("SBER", "2023", window=21, _clock=_fixed_clock).output  # type: ignore[assignment]
        s2: RegimeSnapshot = agent.run("SBER", "2023", window=21, _clock=_fixed_clock).output  # type: ignore[assignment]
        assert [seg.label for seg in s1.segments] == [seg.label for seg in s2.segments]

    def test_different_instruments_different_snapshot_ids(self, tmp_path: Path) -> None:
        src1 = _trend_up_source()
        src2 = FixtureRegimeSource(
            {"GAZP": _rows_from(_DATES_30, _TREND_UP_CLOSES)},
            {"IMOEX": _rows_from(_DATES_30, _IMOEX_UP), "USDRUB": _rows_from(_DATES_30, _USDRUB_DOWN)},
        )
        s1: RegimeSnapshot = RegimeDetectionAgent(tmp_path, source=src1).run(
            "SBER", "2023", window=21, _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        s2: RegimeSnapshot = RegimeDetectionAgent(tmp_path, source=src2).run(
            "GAZP", "2023", window=21, _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        assert s1.snapshot_id != s2.snapshot_id
