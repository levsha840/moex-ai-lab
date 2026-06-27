"""Tests for CorrelationAgent — Layer 2 Analysis Agent.

All tests use FixtureCorrelationSource — no HTTP calls, no real disk data.
Covers: protocol compliance, math helpers, date alignment, lag correlation,
missing data handling, persistence, and determinism.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from agents.analysis.correlation import (
    DEFAULT_LAGS,
    CorrelationAgent,
    FileCorrelationSource,
    FixtureCorrelationSource,
    _align_returns,
    _compute_returns,
    _lagged_pearson,
    _pearson,
    _to_daily_series,
    _write_snapshot,
)
from agents.models import (
    AgentResult,
    ConfidenceScore,
    CorrelationPair,
    CorrelationSnapshot,
    EvidenceRef,
)


# ---------------------------------------------------------------------------
# Fixture factories
# ---------------------------------------------------------------------------

_DATES_SHORT = [
    "2023-01-03", "2023-01-04", "2023-01-05",
    "2023-01-09", "2023-01-10", "2023-01-11", "2023-01-12",
]  # 7 dates → 6 return observations

_DATES_LONG = [
    "2023-01-03", "2023-01-04", "2023-01-05", "2023-01-09", "2023-01-10",
    "2023-01-11", "2023-01-12", "2023-01-13", "2023-01-16", "2023-01-17",
    "2023-01-18", "2023-01-19",
]  # 12 dates → 11 return observations (lag ±5 gives n=6 ≥ 3)


def _make_rows(dates: list[str], closes: list[float]) -> list[dict]:
    return [{"date": d, "close": c} for d, c in zip(dates, closes)]


def _sber_rows(dates: list[str] = _DATES_SHORT) -> list[dict]:
    closes = [100.0 + i * 0.5 for i in range(len(dates))]
    return _make_rows(dates, closes)


def _imoex_rows(dates: list[str] = _DATES_SHORT) -> list[dict]:
    closes = [2200.0 + i * 5.0 for i in range(len(dates))]
    return _make_rows(dates, closes)


def _usdrub_rows(dates: list[str] = _DATES_SHORT) -> list[dict]:
    closes = [70.0 + i * 0.1 for i in range(len(dates))]
    return _make_rows(dates, closes)


def _rgbi_rows(dates: list[str] = _DATES_SHORT) -> list[dict]:
    closes = [110.0 - i * 0.2 for i in range(len(dates))]
    return _make_rows(dates, closes)


def _full_source(dates: list[str] = _DATES_SHORT) -> FixtureCorrelationSource:
    return FixtureCorrelationSource(
        instrument_data={"SBER": _sber_rows(dates)},
        macro_data={
            "IMOEX": _imoex_rows(dates),
            "USDRUB": _usdrub_rows(dates),
            "RGBI": _rgbi_rows(dates),
        },
    )


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 27, 12, 0, 0)


# ---------------------------------------------------------------------------
# CorrelationAgent protocol compliance
# ---------------------------------------------------------------------------

class TestCorrelationAgentProtocol:
    def test_agent_id(self, tmp_path: Path) -> None:
        assert CorrelationAgent(tmp_path).agent_id == "correlation-agent"

    def test_agent_type_is_analysis(self, tmp_path: Path) -> None:
        assert CorrelationAgent(tmp_path).agent_type == "ANALYSIS"

    def test_version_is_string(self, tmp_path: Path) -> None:
        assert isinstance(CorrelationAgent(tmp_path).version, str)

    def test_run_is_callable(self, tmp_path: Path) -> None:
        assert callable(CorrelationAgent(tmp_path).run)

    def test_fixture_source_satisfies_protocol(self) -> None:
        src = FixtureCorrelationSource({}, {})
        assert callable(src.load_instrument)
        assert callable(src.load_macro_symbol)
        assert src.load_instrument("SBER", "2023") == []
        assert src.load_macro_symbol("IMOEX", "2023") == []


# ---------------------------------------------------------------------------
# FixtureCorrelationSource
# ---------------------------------------------------------------------------

class TestFixtureCorrelationSource:
    def test_load_instrument_returns_correct_data(self) -> None:
        rows = _sber_rows()
        src = FixtureCorrelationSource({"SBER": rows}, {})
        result = src.load_instrument("SBER", "2023")
        assert len(result) == len(rows)
        assert result[0]["date"] == _DATES_SHORT[0]

    def test_load_instrument_empty_for_unknown(self) -> None:
        src = FixtureCorrelationSource({"SBER": _sber_rows()}, {})
        assert src.load_instrument("GAZP", "2023") == []

    def test_load_macro_returns_correct_data(self) -> None:
        rows = _imoex_rows()
        src = FixtureCorrelationSource({}, {"IMOEX": rows})
        result = src.load_macro_symbol("IMOEX", "2023")
        assert len(result) == len(rows)
        assert result[0]["close"] == rows[0]["close"]

    def test_load_macro_empty_for_unknown_symbol(self) -> None:
        src = FixtureCorrelationSource({}, {"IMOEX": _imoex_rows()})
        assert src.load_macro_symbol("BRENT", "2023") == []

    def test_does_not_mutate_source_list(self) -> None:
        rows = _sber_rows()
        src = FixtureCorrelationSource({"SBER": rows}, {})
        fetched = src.load_instrument("SBER", "2023")
        fetched.clear()
        assert len(src.load_instrument("SBER", "2023")) == len(rows)


# ---------------------------------------------------------------------------
# _to_daily_series
# ---------------------------------------------------------------------------

class TestToDailySeries:
    def test_sorted_by_date(self) -> None:
        rows = [{"date": "2023-01-05", "close": 3.0}, {"date": "2023-01-03", "close": 1.0}]
        result = _to_daily_series(rows)
        assert result[0][0] == "2023-01-03"
        assert result[1][0] == "2023-01-05"

    def test_float_conversion(self) -> None:
        rows = [{"date": "2023-01-03", "close": "100.5"}]
        result = _to_daily_series(rows)
        assert isinstance(result[0][1], float)

    def test_empty_input(self) -> None:
        assert _to_daily_series([]) == []


# ---------------------------------------------------------------------------
# _compute_returns
# ---------------------------------------------------------------------------

class TestComputeReturns:
    def test_return_count_is_n_minus_one(self) -> None:
        daily = [("2023-01-03", 100.0), ("2023-01-04", 102.0), ("2023-01-05", 101.0)]
        rets = _compute_returns(daily)
        assert len(rets) == 2

    def test_return_formula(self) -> None:
        daily = [("d1", 100.0), ("d2", 102.0)]
        rets = _compute_returns(daily)
        assert abs(rets[0][1] - 0.02) < 1e-10

    def test_negative_return(self) -> None:
        daily = [("d1", 100.0), ("d2", 90.0)]
        rets = _compute_returns(daily)
        assert abs(rets[0][1] - (-0.10)) < 1e-10

    def test_zero_previous_close_skipped(self) -> None:
        daily = [("d1", 0.0), ("d2", 100.0), ("d3", 105.0)]
        rets = _compute_returns(daily)
        assert len(rets) == 1  # d1→d2 skipped, d2→d3 kept

    def test_single_bar_returns_empty(self) -> None:
        assert _compute_returns([("d1", 100.0)]) == []

    def test_empty_returns_empty(self) -> None:
        assert _compute_returns([]) == []

    def test_date_label_is_to_date(self) -> None:
        daily = [("2023-01-03", 100.0), ("2023-01-04", 101.0)]
        rets = _compute_returns(daily)
        assert rets[0][0] == "2023-01-04"


# ---------------------------------------------------------------------------
# _align_returns
# ---------------------------------------------------------------------------

class TestAlignReturns:
    def _rets(self, dates: list[str]) -> list[tuple[str, float]]:
        return [(d, float(i)) for i, d in enumerate(dates)]

    def test_full_alignment(self) -> None:
        dates = ["d1", "d2", "d3"]
        x, y = _align_returns(self._rets(dates), self._rets(dates))
        assert len(x) == 3
        assert len(y) == 3

    def test_partial_overlap(self) -> None:
        instr = [("d1", 1.0), ("d2", 2.0), ("d3", 3.0)]
        macro = [("d2", 0.5), ("d3", 0.6), ("d4", 0.7)]
        x, y = _align_returns(instr, macro)
        assert len(x) == 2
        assert len(y) == 2

    def test_no_overlap_returns_empty(self) -> None:
        instr = [("d1", 1.0), ("d2", 2.0)]
        macro = [("d3", 0.5), ("d4", 0.6)]
        x, y = _align_returns(instr, macro)
        assert x == []
        assert y == []

    def test_preserves_values(self) -> None:
        instr = [("d1", 0.02), ("d2", -0.01)]
        macro = [("d1", 0.015)]
        x, y = _align_returns(instr, macro)
        assert x == [0.02]
        assert y == [0.015]


# ---------------------------------------------------------------------------
# _pearson
# ---------------------------------------------------------------------------

class TestPearson:
    def test_perfect_positive_correlation(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert abs(_pearson(x, x) - 1.0) < 1e-10

    def test_perfect_negative_correlation(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [-1.0, -2.0, -3.0, -4.0, -5.0]
        assert abs(_pearson(x, y) - (-1.0)) < 1e-10

    def test_result_in_minus_one_to_one(self) -> None:
        x = [0.01, -0.02, 0.03, -0.01, 0.005]
        y = [0.02, 0.01, -0.01, 0.03, -0.005]
        r = _pearson(x, y)
        assert -1.0 <= r <= 1.0

    def test_below_min_obs_returns_nan(self) -> None:
        x = [1.0, 2.0]  # only 2 < _MIN_OBS=3
        assert math.isnan(_pearson(x, x))

    def test_zero_variance_returns_nan(self) -> None:
        x = [1.0, 1.0, 1.0]
        y = [1.0, 2.0, 3.0]
        assert math.isnan(_pearson(x, y))

    def test_known_value(self) -> None:
        # Two series whose correlation can be computed analytically
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]  # r = -1.0
        assert abs(_pearson(x, y) - (-1.0)) < 1e-10


# ---------------------------------------------------------------------------
# _lagged_pearson
# ---------------------------------------------------------------------------

class TestLaggedPearson:
    def _same_series(self, n: int = 10) -> list[float]:
        return [float(i) for i in range(1, n + 1)]

    def test_lag_zero_same_as_pearson(self) -> None:
        x = [0.01, -0.02, 0.03, -0.01, 0.005, 0.02, -0.01, 0.03, 0.01, -0.02]
        y = [0.02, 0.01, -0.01, 0.03, 0.01, -0.01, 0.02, -0.03, 0.01, 0.02]
        r0, n0 = _lagged_pearson(x, y, lag=0)
        assert abs(r0 - _pearson(x, y)) < 1e-12
        assert n0 == len(x)

    def test_lag_positive_reduces_n(self) -> None:
        x = self._same_series(10)
        y = self._same_series(10)
        _, n0 = _lagged_pearson(x, y, lag=0)
        _, n1 = _lagged_pearson(x, y, lag=1)
        assert n1 == n0 - 1

    def test_lag_negative_reduces_n(self) -> None:
        x = self._same_series(10)
        y = self._same_series(10)
        _, n0 = _lagged_pearson(x, y, lag=0)
        _, nm1 = _lagged_pearson(x, y, lag=-1)
        assert nm1 == n0 - 1

    def test_lag_plus5_reduces_by_5(self) -> None:
        x = self._same_series(11)
        y = self._same_series(11)
        _, n5 = _lagged_pearson(x, y, lag=5)
        assert n5 == 6

    def test_lag_minus5_reduces_by_5(self) -> None:
        x = self._same_series(11)
        y = self._same_series(11)
        _, nm5 = _lagged_pearson(x, y, lag=-5)
        assert nm5 == 6

    def test_insufficient_obs_returns_nan(self) -> None:
        x = [1.0, 2.0, 3.0]  # lag+5 → 0 obs
        r, n = _lagged_pearson(x, x, lag=5)
        assert math.isnan(r)
        assert n == 0

    def test_lag_plus1_macro_leads(self) -> None:
        # If x = [1, 2, 3, 4, 5] and y = [0, 1, 2, 3, 4] (y lags x by 1):
        # lag+1: instr[1:] vs macro[:-1] → [2,3,4,5] vs [0,1,2,3] — not identical
        # With lag+1: instr[1:] vs macro[:-1], both = ascending → perfect positive
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [0.0, 1.0, 2.0, 3.0, 4.0]   # shifted x by 1
        r_lag1, n = _lagged_pearson(x, y, lag=1)
        # instr[1:] = [2,3,4,5] vs macro[:-1] = [0,1,2,3] → perfect correlation
        assert abs(r_lag1 - 1.0) < 1e-10
        assert n == 4

    def test_lag_minus1_instrument_leads(self) -> None:
        x = [0.0, 1.0, 2.0, 3.0, 4.0]   # instrument shifted by 1
        y = [1.0, 2.0, 3.0, 4.0, 5.0]   # macro (x leads y)
        r, n = _lagged_pearson(x, y, lag=-1)
        # instr[:-1] = [0,1,2,3] vs macro[1:] = [2,3,4,5] → perfect
        assert abs(r - 1.0) < 1e-10
        assert n == 4


# ---------------------------------------------------------------------------
# CorrelationAgent — fixture run
# ---------------------------------------------------------------------------

class TestCorrelationAgentFixtureRun:
    def _run(
        self,
        tmp_path: Path,
        dates: list[str] = _DATES_SHORT,
        macro_symbols: tuple[str, ...] = ("IMOEX", "USDRUB", "RGBI"),
    ) -> AgentResult:
        agent = CorrelationAgent(tmp_path, source=_full_source(dates))
        return agent.run("SBER", "2023", macro_symbols=macro_symbols, _clock=_fixed_clock)

    def test_returns_agent_result(self, tmp_path: Path) -> None:
        assert isinstance(self._run(tmp_path), AgentResult)

    def test_agent_id_in_result(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_id == "correlation-agent"

    def test_agent_type_is_analysis(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_type == "ANALYSIS"

    def test_output_is_correlation_snapshot(self, tmp_path: Path) -> None:
        assert isinstance(self._run(tmp_path).output, CorrelationSnapshot)

    def test_created_at_uses_injected_clock(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).created_at == "2026-06-27T12:00:00"

    def test_snapshot_instrument(self, tmp_path: Path) -> None:
        snap: CorrelationSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.instrument == "SBER"

    def test_snapshot_period(self, tmp_path: Path) -> None:
        snap: CorrelationSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.period == "2023"

    def test_snapshot_id_format(self, tmp_path: Path) -> None:
        snap: CorrelationSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.snapshot_id == "corr_SBER_2023"

    def test_pairs_count(self, tmp_path: Path) -> None:
        snap: CorrelationSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        # 3 macro symbols × 5 default lags = 15 pairs
        assert len(snap.pairs) == 3 * len(DEFAULT_LAGS)

    def test_all_lags_present_for_imoex(self, tmp_path: Path) -> None:
        snap: CorrelationSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        imoex_lags = {p.lag for p in snap.pairs if p.macro_symbol == "IMOEX"}
        assert imoex_lags == set(DEFAULT_LAGS)

    def test_lag_zero_correlation_is_valid_float(self, tmp_path: Path) -> None:
        snap: CorrelationSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        lag0 = next(p for p in snap.pairs if p.macro_symbol == "IMOEX" and p.lag == 0)
        assert not math.isnan(lag0.correlation)
        assert -1.0 <= lag0.correlation <= 1.0

    def test_confidence_positive_when_data_available(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        assert result.confidence.value > 0.0

    def test_evidence_includes_instrument_and_macros(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        sources = {e.source for e in result.evidence}
        assert any("instrument" in s for s in sources)
        assert any("macro" in s for s in sources)

    def test_single_macro_symbol_run(self, tmp_path: Path) -> None:
        result = self._run(tmp_path, macro_symbols=("IMOEX",))
        snap: CorrelationSnapshot = result.output  # type: ignore[assignment]
        assert len(snap.pairs) == len(DEFAULT_LAGS)
        assert all(p.macro_symbol == "IMOEX" for p in snap.pairs)


# ---------------------------------------------------------------------------
# Missing data handling
# ---------------------------------------------------------------------------

class TestMissingDataHandling:
    def test_missing_macro_symbol_not_in_pairs(self, tmp_path: Path) -> None:
        src = FixtureCorrelationSource(
            {"SBER": _sber_rows()},
            {"IMOEX": _imoex_rows()},  # USDRUB and RGBI absent
        )
        agent = CorrelationAgent(tmp_path, source=src)
        snap: CorrelationSnapshot = agent.run(
            "SBER", "2023", _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        symbols_in_pairs = {p.macro_symbol for p in snap.pairs}
        assert "USDRUB" not in symbols_in_pairs
        assert "RGBI" not in symbols_in_pairs
        assert "IMOEX" in symbols_in_pairs

    def test_partial_macro_reduces_pair_count(self, tmp_path: Path) -> None:
        src = FixtureCorrelationSource(
            {"SBER": _sber_rows()},
            {"IMOEX": _imoex_rows()},
        )
        agent = CorrelationAgent(tmp_path, source=src)
        snap: CorrelationSnapshot = agent.run(
            "SBER", "2023", _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        assert len(snap.pairs) == len(DEFAULT_LAGS)  # only IMOEX

    def test_all_macro_missing_gives_empty_pairs(self, tmp_path: Path) -> None:
        src = FixtureCorrelationSource({"SBER": _sber_rows()}, {})
        agent = CorrelationAgent(tmp_path, source=src)
        snap: CorrelationSnapshot = agent.run(
            "SBER", "2023", _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        assert snap.pairs == ()

    def test_all_macro_missing_gives_confidence_zero(self, tmp_path: Path) -> None:
        src = FixtureCorrelationSource({"SBER": _sber_rows()}, {})
        agent = CorrelationAgent(tmp_path, source=src)
        result = agent.run("SBER", "2023", _clock=_fixed_clock)
        assert result.confidence.value == 0.0

    def test_missing_instrument_gives_zero_bars(self, tmp_path: Path) -> None:
        src = FixtureCorrelationSource({}, {"IMOEX": _imoex_rows()})
        agent = CorrelationAgent(tmp_path, source=src)
        snap: CorrelationSnapshot = agent.run(
            "SBER", "2023", _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        assert snap.total_instrument_bars == 0


# ---------------------------------------------------------------------------
# Date alignment
# ---------------------------------------------------------------------------

class TestDateAlignment:
    def test_full_alignment_missing_is_zero(self, tmp_path: Path) -> None:
        src = FixtureCorrelationSource(
            {"SBER": _sber_rows()},
            {"IMOEX": _imoex_rows()},
        )
        agent = CorrelationAgent(tmp_path, source=src)
        snap: CorrelationSnapshot = agent.run(
            "SBER", "2023", macro_symbols=("IMOEX",), _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        assert snap.missing_alignment == 0
        assert snap.aligned_dates == snap.total_instrument_bars

    def test_partial_alignment_missing_nonzero(self, tmp_path: Path) -> None:
        extra_dates = _DATES_SHORT + ["2023-01-13", "2023-01-16"]
        sber_extra = _make_rows(
            extra_dates, [100.0 + i * 0.5 for i in range(len(extra_dates))]
        )
        src = FixtureCorrelationSource(
            {"SBER": sber_extra},
            {"IMOEX": _imoex_rows(_DATES_SHORT)},  # only original 7 dates
        )
        agent = CorrelationAgent(tmp_path, source=src)
        snap: CorrelationSnapshot = agent.run(
            "SBER", "2023", macro_symbols=("IMOEX",), _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        assert snap.total_instrument_bars == len(extra_dates)
        assert snap.aligned_dates == len(_DATES_SHORT)
        assert snap.missing_alignment == 2

    def test_alignment_invariant(self, tmp_path: Path) -> None:
        src = _full_source()
        agent = CorrelationAgent(tmp_path, source=src)
        snap: CorrelationSnapshot = agent.run(
            "SBER", "2023", _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        assert snap.aligned_dates + snap.missing_alignment == snap.total_instrument_bars


# ---------------------------------------------------------------------------
# Lag correlation with sufficient data (long dates)
# ---------------------------------------------------------------------------

class TestLagCorrelationWithLongData:
    """Tests that require enough observations for lag ±5 (need n ≥ 8 for n-5 ≥ 3)."""

    def _run_long(self, tmp_path: Path) -> CorrelationSnapshot:
        src = FixtureCorrelationSource(
            {"SBER": _sber_rows(_DATES_LONG)},
            {"IMOEX": _imoex_rows(_DATES_LONG)},
        )
        agent = CorrelationAgent(tmp_path, source=src)
        return agent.run(
            "SBER", "2023", macro_symbols=("IMOEX",), _clock=_fixed_clock
        ).output  # type: ignore[assignment]

    def test_lag_plus5_valid_with_long_data(self, tmp_path: Path) -> None:
        snap = self._run_long(tmp_path)
        p5 = next(p for p in snap.pairs if p.lag == 5)
        # 11 returns, lag+5: n=6 ≥ 3 → valid
        assert not math.isnan(p5.correlation)
        assert p5.observation_count == 6

    def test_lag_minus5_valid_with_long_data(self, tmp_path: Path) -> None:
        snap = self._run_long(tmp_path)
        pm5 = next(p for p in snap.pairs if p.lag == -5)
        assert not math.isnan(pm5.correlation)
        assert pm5.observation_count == 6

    def test_lag_zero_has_most_observations(self, tmp_path: Path) -> None:
        snap = self._run_long(tmp_path)
        lag0 = next(p for p in snap.pairs if p.lag == 0)
        lag5 = next(p for p in snap.pairs if p.lag == 5)
        assert lag0.observation_count > lag5.observation_count

    def test_monotone_series_gives_r_near_one(self, tmp_path: Path) -> None:
        # Both SBER and IMOEX increase monotonically → r ≈ 1
        snap = self._run_long(tmp_path)
        lag0 = next(p for p in snap.pairs if p.lag == 0)
        assert lag0.correlation > 0.95


# ---------------------------------------------------------------------------
# Short data — lag ±5 returns nan
# ---------------------------------------------------------------------------

class TestLagNanWithShortData:
    def test_lag_plus5_nan_with_short_data(self, tmp_path: Path) -> None:
        src = _full_source(_DATES_SHORT)  # 6 returns → lag+5 gives n=1
        agent = CorrelationAgent(tmp_path, source=src)
        snap: CorrelationSnapshot = agent.run(
            "SBER", "2023", macro_symbols=("IMOEX",), _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        p5 = next(p for p in snap.pairs if p.lag == 5)
        assert math.isnan(p5.correlation)

    def test_lag_minus5_nan_with_short_data(self, tmp_path: Path) -> None:
        src = _full_source(_DATES_SHORT)
        agent = CorrelationAgent(tmp_path, source=src)
        snap: CorrelationSnapshot = agent.run(
            "SBER", "2023", macro_symbols=("IMOEX",), _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        pm5 = next(p for p in snap.pairs if p.lag == -5)
        assert math.isnan(pm5.correlation)


# ---------------------------------------------------------------------------
# Persistence — JSON file
# ---------------------------------------------------------------------------

class TestPersistence:
    def _run(self, tmp_path: Path) -> tuple[CorrelationSnapshot, Path]:
        agent = CorrelationAgent(tmp_path, source=_full_source())
        result = agent.run("SBER", "2023", _clock=_fixed_clock)
        snap: CorrelationSnapshot = result.output  # type: ignore[assignment]
        json_path = tmp_path / "context" / "correlation" / "sber_2023.json"
        return snap, json_path

    def test_json_file_created(self, tmp_path: Path) -> None:
        _, path = self._run(tmp_path)
        assert path.exists()

    def test_json_is_in_context_correlation_dir(self, tmp_path: Path) -> None:
        _, path = self._run(tmp_path)
        assert "context" in str(path)
        assert "correlation" in str(path)

    def test_json_contains_snapshot_id(self, tmp_path: Path) -> None:
        _, path = self._run(tmp_path)
        with open(path) as f:
            data = json.load(f)
        assert data["snapshot_id"] == "corr_SBER_2023"

    def test_json_contains_pairs(self, tmp_path: Path) -> None:
        _, path = self._run(tmp_path)
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data["pairs"], list)
        assert len(data["pairs"]) > 0

    def test_json_nan_serialized_as_null(self, tmp_path: Path) -> None:
        _, path = self._run(tmp_path)
        with open(path) as f:
            data = json.load(f)
        nan_pairs = [p for p in data["pairs"] if p["correlation"] is None]
        # lag ±5 with 7 short dates → null
        assert len(nan_pairs) > 0

    def test_second_run_overwrites(self, tmp_path: Path) -> None:
        agent = CorrelationAgent(tmp_path, source=_full_source())
        agent.run("SBER", "2023", _clock=_fixed_clock)
        agent.run("SBER", "2023", _clock=_fixed_clock)
        path = tmp_path / "context" / "correlation" / "sber_2023.json"
        assert path.exists()

    def test_json_alignment_fields(self, tmp_path: Path) -> None:
        _, path = self._run(tmp_path)
        with open(path) as f:
            data = json.load(f)
        assert "total_instrument_bars" in data
        assert "aligned_dates" in data
        assert "missing_alignment" in data

    def test_separate_from_datasets_dir(self, tmp_path: Path) -> None:
        _, path = self._run(tmp_path)
        expected_root = str((tmp_path / "context" / "correlation").resolve())
        assert str(path.resolve()).startswith(expected_root)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_clock_same_created_at(self, tmp_path: Path) -> None:
        agent = CorrelationAgent(tmp_path, source=_full_source())
        r1 = agent.run("SBER", "2023", _clock=lambda: datetime(2026, 1, 1, 0, 0, 0))
        r2 = agent.run("SBER", "2023", _clock=lambda: datetime(2026, 1, 1, 0, 0, 0))
        assert r1.created_at == r2.created_at

    def test_different_instruments_different_snapshot_ids(self, tmp_path: Path) -> None:
        src = FixtureCorrelationSource(
            {"SBER": _sber_rows(), "GAZP": _sber_rows()},
            {"IMOEX": _imoex_rows()},
        )
        agent = CorrelationAgent(tmp_path, source=src)
        s1: CorrelationSnapshot = agent.run("SBER", "2023", _clock=_fixed_clock).output  # type: ignore[assignment]
        s2: CorrelationSnapshot = agent.run("GAZP", "2023", _clock=_fixed_clock).output  # type: ignore[assignment]
        assert s1.snapshot_id != s2.snapshot_id
