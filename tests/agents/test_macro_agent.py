"""Tests for MacroAgent — Layer 1 Data Agent for macro context.

All tests use FixtureMacroSource — no HTTP calls, no real MOEX data.
Covers: protocol compliance, source evidence, missing data, persistence, determinism.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pytest

from agents.data.macro import (
    DEFAULT_SYMBOLS,
    FixtureMacroSource,
    MacroAgent,
    MoexMacroSource,
    _build_evidence,
    _write_series,
)
from agents.models import (
    AgentResult,
    ConfidenceScore,
    EvidenceRef,
    MacroSeries,
    MacroSnapshot,
)
from agents.protocols import MacroSource


# ---------------------------------------------------------------------------
# Fixture factories
# ---------------------------------------------------------------------------

def _daily_rows(
    symbol: str = "IMOEX",
    n: int = 5,
    base_close: float = 2200.0,
) -> list[dict]:
    """Synthetic daily macro rows starting 2023-01-03."""
    dates = [
        "2023-01-03", "2023-01-04", "2023-01-05",
        "2023-01-09", "2023-01-10", "2023-01-11",
        "2023-01-12", "2023-01-13",
    ]
    return [
        {
            "date": dates[i],
            "open": base_close + i * 0.5,
            "high": base_close + i * 0.5 + 1.0,
            "low": base_close + i * 0.5 - 1.0,
            "close": base_close + i * 0.5,
            "volume": 0,
        }
        for i in range(min(n, len(dates)))
    ]


def _full_fixture_source() -> FixtureMacroSource:
    return FixtureMacroSource(
        {
            "IMOEX": _daily_rows("IMOEX", 5, base_close=2200.0),
            "USDRUB": _daily_rows("USDRUB", 5, base_close=70.0),
            "RGBI": _daily_rows("RGBI", 5, base_close=110.0),
        }
    )


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 27, 12, 0, 0)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestMacroAgentProtocol:
    def test_agent_id_is_string(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path)
        assert isinstance(agent.agent_id, str)
        assert agent.agent_id == "macro-agent"

    def test_agent_type_is_data(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path)
        assert agent.agent_type == "DATA"

    def test_version_is_string(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path)
        assert agent.version == "1.0"

    def test_run_is_callable(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path)
        assert callable(agent.run)

    def test_fixture_source_satisfies_macro_source_protocol(self) -> None:
        src = FixtureMacroSource({})
        assert callable(src.fetch)
        rows = src.fetch("IMOEX", "1d", "2023-01-01", "2023-12-31")
        assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# FixtureMacroSource
# ---------------------------------------------------------------------------

class TestFixtureMacroSource:
    def test_returns_correct_rows_for_symbol(self) -> None:
        rows = _daily_rows("IMOEX", 3)
        src = FixtureMacroSource({"IMOEX": rows})
        result = src.fetch("IMOEX", "1d", "2023-01-01", "2023-12-31")
        assert len(result) == 3
        assert result[0]["date"] == "2023-01-03"

    def test_returns_empty_for_unknown_symbol(self) -> None:
        src = FixtureMacroSource({"IMOEX": _daily_rows("IMOEX")})
        result = src.fetch("UNKNOWN", "1d", "2023-01-01", "2023-12-31")
        assert result == []

    def test_does_not_mutate_source_data(self) -> None:
        rows = _daily_rows("IMOEX", 3)
        src = FixtureMacroSource({"IMOEX": rows})
        fetched = src.fetch("IMOEX", "1d", "2023-01-01", "2023-12-31")
        fetched.clear()
        # second fetch should still return rows
        result2 = src.fetch("IMOEX", "1d", "2023-01-01", "2023-12-31")
        assert len(result2) == 3

    def test_date_range_param_ignored_in_fixture(self) -> None:
        rows = _daily_rows("IMOEX", 5)
        src = FixtureMacroSource({"IMOEX": rows})
        r1 = src.fetch("IMOEX", "1d", "2023-01-01", "2023-06-30")
        r2 = src.fetch("IMOEX", "1d", "2023-07-01", "2023-12-31")
        assert r1 == r2  # fixture ignores range


# ---------------------------------------------------------------------------
# MacroAgent — successful fixture run
# ---------------------------------------------------------------------------

class TestMacroAgentFixtureRun:
    def _run(self, tmp_path: Path, symbols: tuple[str, ...] = DEFAULT_SYMBOLS) -> AgentResult:
        agent = MacroAgent(data_dir=tmp_path, source=_full_fixture_source())
        return agent.run("2023", symbols=symbols, _clock=_fixed_clock)

    def test_returns_agent_result(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        assert isinstance(result, AgentResult)

    def test_agent_id_in_result(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_id == "macro-agent"

    def test_agent_type_in_result(self, tmp_path: Path) -> None:
        assert self._run(tmp_path).agent_type == "DATA"

    def test_output_is_macro_snapshot(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        assert isinstance(result.output, MacroSnapshot)

    def test_created_at_uses_injected_clock(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        assert result.created_at == "2026-06-27T12:00:00"

    def test_snapshot_period(self, tmp_path: Path) -> None:
        snap: MacroSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.period == "2023"

    def test_snapshot_id_format(self, tmp_path: Path) -> None:
        snap: MacroSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.snapshot_id == "macro_2023_1d"

    def test_all_symbols_in_observations(self, tmp_path: Path) -> None:
        snap: MacroSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        fetched = {s.symbol for s in snap.observations}
        assert fetched == set(DEFAULT_SYMBOLS)

    def test_no_missing_values_when_all_fetched(self, tmp_path: Path) -> None:
        snap: MacroSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.missing_values == ()

    def test_confidence_is_one_when_all_fetched(self, tmp_path: Path) -> None:
        snap: MacroSnapshot = self._run(tmp_path).output  # type: ignore[assignment]
        assert snap.confidence.value == 1.0

    def test_evidence_not_empty(self, tmp_path: Path) -> None:
        result = self._run(tmp_path)
        assert len(result.evidence) > 0
        assert all(isinstance(e, EvidenceRef) for e in result.evidence)

    def test_single_symbol_run(self, tmp_path: Path) -> None:
        result = self._run(tmp_path, symbols=("IMOEX",))
        snap: MacroSnapshot = result.output  # type: ignore[assignment]
        assert len(snap.observations) == 1
        assert snap.observations[0].symbol == "IMOEX"


# ---------------------------------------------------------------------------
# MacroAgent — missing data handling
# ---------------------------------------------------------------------------

class TestMacroAgentMissingData:
    def test_missing_symbol_recorded_in_snapshot(self, tmp_path: Path) -> None:
        src = FixtureMacroSource({"IMOEX": _daily_rows("IMOEX", 5)})
        # USDRUB and RGBI not in fixture → will be empty → missing
        agent = MacroAgent(data_dir=tmp_path, source=src)
        result = agent.run("2023", _clock=_fixed_clock)
        snap: MacroSnapshot = result.output  # type: ignore[assignment]

        missing_dict = dict(snap.missing_values)
        assert "USDRUB" in missing_dict
        assert "RGBI" in missing_dict

    def test_partial_fetch_reduces_confidence(self, tmp_path: Path) -> None:
        src = FixtureMacroSource({"IMOEX": _daily_rows("IMOEX", 5)})
        agent = MacroAgent(data_dir=tmp_path, source=src)
        result = agent.run("2023", _clock=_fixed_clock)
        snap: MacroSnapshot = result.output  # type: ignore[assignment]

        # 1/3 symbols fetched → confidence = 1/3
        assert abs(snap.confidence.value - 1 / 3) < 0.01

    def test_all_missing_gives_confidence_zero(self, tmp_path: Path) -> None:
        src = FixtureMacroSource({})  # no data for any symbol
        agent = MacroAgent(data_dir=tmp_path, source=src)
        result = agent.run("2023", _clock=_fixed_clock)
        snap: MacroSnapshot = result.output  # type: ignore[assignment]

        assert snap.confidence.value == 0.0

    def test_all_missing_observations_is_empty(self, tmp_path: Path) -> None:
        src = FixtureMacroSource({})
        agent = MacroAgent(data_dir=tmp_path, source=src)
        snap: MacroSnapshot = agent.run("2023", _clock=_fixed_clock).output  # type: ignore[assignment]
        assert snap.observations == ()

    def test_successful_symbols_still_written(self, tmp_path: Path) -> None:
        src = FixtureMacroSource({"IMOEX": _daily_rows("IMOEX", 3)})
        agent = MacroAgent(data_dir=tmp_path, source=src)
        agent.run("2023", _clock=_fixed_clock)

        imoex_csv = tmp_path / "context" / "macro" / "2023" / "IMOEX_1d.csv"
        assert imoex_csv.exists()


# ---------------------------------------------------------------------------
# MacroSeries content
# ---------------------------------------------------------------------------

class TestMacroSeriesContent:
    def _series(self, tmp_path: Path, symbol: str = "IMOEX") -> MacroSeries:
        src = FixtureMacroSource({symbol: _daily_rows(symbol, 5)})
        agent = MacroAgent(data_dir=tmp_path, source=src)
        snap: MacroSnapshot = agent.run(
            "2023", symbols=(symbol,), _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        return snap.observations[0]

    def test_symbol_matches(self, tmp_path: Path) -> None:
        s = self._series(tmp_path)
        assert s.symbol == "IMOEX"

    def test_timeframe_matches(self, tmp_path: Path) -> None:
        s = self._series(tmp_path)
        assert s.timeframe == "1d"

    def test_value_count_matches_rows(self, tmp_path: Path) -> None:
        s = self._series(tmp_path)
        assert s.value_count == 5

    def test_date_from_is_first_row(self, tmp_path: Path) -> None:
        s = self._series(tmp_path)
        assert s.date_from == "2023-01-03"

    def test_date_to_is_last_row(self, tmp_path: Path) -> None:
        rows = _daily_rows("IMOEX", 5)
        src = FixtureMacroSource({"IMOEX": rows})
        agent = MacroAgent(data_dir=tmp_path, source=src)
        snap: MacroSnapshot = agent.run(
            "2023", symbols=("IMOEX",), _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        s = snap.observations[0]
        assert s.date_to == rows[-1]["date"]

    def test_path_points_to_existing_file(self, tmp_path: Path) -> None:
        s = self._series(tmp_path)
        assert Path(s.path).exists()


# ---------------------------------------------------------------------------
# Persistence — on-disk CSV format
# ---------------------------------------------------------------------------

class TestMacroPersistence:
    def _run_and_get_csv_path(self, tmp_path: Path, symbol: str = "IMOEX") -> Path:
        src = FixtureMacroSource({symbol: _daily_rows(symbol, 5)})
        agent = MacroAgent(data_dir=tmp_path, source=src)
        snap: MacroSnapshot = agent.run(
            "2023", symbols=(symbol,), _clock=_fixed_clock
        ).output  # type: ignore[assignment]
        return Path(snap.observations[0].path)

    def test_csv_exists(self, tmp_path: Path) -> None:
        p = self._run_and_get_csv_path(tmp_path)
        assert p.exists()

    def test_csv_is_in_context_macro_dir(self, tmp_path: Path) -> None:
        p = self._run_and_get_csv_path(tmp_path)
        assert "context" in str(p)
        assert "macro" in str(p)
        assert "2023" in str(p)

    def test_csv_header(self, tmp_path: Path) -> None:
        p = self._run_and_get_csv_path(tmp_path)
        with open(p, encoding="utf-8") as f:
            header = f.readline().strip()
        assert header == "date,open,high,low,close,volume"

    def test_csv_row_count_matches_value_count(self, tmp_path: Path) -> None:
        p = self._run_and_get_csv_path(tmp_path)
        with open(p, encoding="utf-8") as f:
            rows = f.readlines()
        assert len(rows) - 1 == 5  # header + 5 data rows

    def test_csv_date_column_is_date_only(self, tmp_path: Path) -> None:
        p = self._run_and_get_csv_path(tmp_path)
        with open(p, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                assert len(row["date"]) == 10    # "YYYY-MM-DD"
                assert "T" not in row["date"]
                assert " " not in row["date"]

    def test_csv_close_is_numeric(self, tmp_path: Path) -> None:
        p = self._run_and_get_csv_path(tmp_path)
        with open(p, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                assert float(row["close"]) > 0

    def test_all_three_symbols_written_in_separate_files(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path, source=_full_fixture_source())
        agent.run("2023", _clock=_fixed_clock)

        macro_dir = tmp_path / "context" / "macro" / "2023"
        assert (macro_dir / "IMOEX_1d.csv").exists()
        assert (macro_dir / "USDRUB_1d.csv").exists()
        assert (macro_dir / "RGBI_1d.csv").exists()

    def test_separate_from_datasets_directory(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path, source=_full_fixture_source())
        snap: MacroSnapshot = agent.run("2023", _clock=_fixed_clock).output  # type: ignore[assignment]
        expected_root = str((tmp_path / "context" / "macro").resolve())
        for series in snap.observations:
            assert series.path.startswith(expected_root)


# ---------------------------------------------------------------------------
# Source evidence
# ---------------------------------------------------------------------------

class TestMacroAgentEvidence:
    def test_evidence_source_is_moex_iss_for_known_symbol(self, tmp_path: Path) -> None:
        src = FixtureMacroSource({"IMOEX": _daily_rows("IMOEX", 5)})
        agent = MacroAgent(data_dir=tmp_path, source=src)
        result = agent.run("2023", symbols=("IMOEX",), _clock=_fixed_clock)
        assert len(result.evidence) >= 1
        assert result.evidence[0].source == "MOEX ISS API"

    def test_evidence_timestamp_matches_created_at(self, tmp_path: Path) -> None:
        src = FixtureMacroSource({"IMOEX": _daily_rows("IMOEX", 5)})
        agent = MacroAgent(data_dir=tmp_path, source=src)
        result = agent.run("2023", symbols=("IMOEX",), _clock=_fixed_clock)
        for ev in result.evidence:
            assert ev.timestamp == result.created_at

    def test_evidence_count_matches_fetched_symbols(self, tmp_path: Path) -> None:
        src = FixtureMacroSource({"IMOEX": _daily_rows("IMOEX", 5)})
        agent = MacroAgent(data_dir=tmp_path, source=src)
        result = agent.run("2023", _clock=_fixed_clock)
        # Only IMOEX fetched → 1 evidence
        assert len(result.evidence) == 1

    def test_source_refs_in_snapshot_match_evidence(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path, source=_full_fixture_source())
        result = agent.run("2023", _clock=_fixed_clock)
        snap: MacroSnapshot = result.output  # type: ignore[assignment]
        assert len(snap.source_refs) == len(result.evidence)


# ---------------------------------------------------------------------------
# Determinism — clock injection
# ---------------------------------------------------------------------------

class TestMacroAgentDeterminism:
    def test_created_at_uses_injected_clock(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path, source=_full_fixture_source())
        r1 = agent.run("2023", _clock=lambda: datetime(2026, 1, 1, 0, 0, 0))
        r2 = agent.run("2023", _clock=lambda: datetime(2026, 1, 1, 0, 0, 0))
        assert r1.created_at == r2.created_at

    def test_snapshot_id_is_deterministic(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path, source=_full_fixture_source())
        r1 = agent.run("2023", _clock=_fixed_clock)
        r2 = agent.run("2023", _clock=_fixed_clock)
        snap1: MacroSnapshot = r1.output  # type: ignore[assignment]
        snap2: MacroSnapshot = r2.output  # type: ignore[assignment]
        assert snap1.snapshot_id == snap2.snapshot_id

    def test_two_periods_produce_different_snapshot_ids(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path, source=_full_fixture_source())
        r2023 = agent.run("2023", _clock=_fixed_clock)
        r2022 = agent.run("2022", _clock=_fixed_clock)
        snap2023: MacroSnapshot = r2023.output  # type: ignore[assignment]
        snap2022: MacroSnapshot = r2022.output  # type: ignore[assignment]
        assert snap2023.snapshot_id != snap2022.snapshot_id

    def test_rerun_overwrites_csv_file(self, tmp_path: Path) -> None:
        agent = MacroAgent(data_dir=tmp_path, source=_full_fixture_source())
        agent.run("2023", symbols=("IMOEX",), _clock=_fixed_clock)
        agent.run("2023", symbols=("IMOEX",), _clock=_fixed_clock)  # no error
        csv_path = tmp_path / "context" / "macro" / "2023" / "IMOEX_1d.csv"
        assert csv_path.exists()


# ---------------------------------------------------------------------------
# Source evidence build helper
# ---------------------------------------------------------------------------

class TestBuildEvidence:
    def test_evidence_source_name(self) -> None:
        cfg = {"engine": "stock", "market": "index", "board": "SNDX", "security": "IMOEX"}
        ev = _build_evidence("IMOEX", cfg, "2023-01-01", "2023-12-31", "2026-06-27T12:00:00")
        assert ev.source == "MOEX ISS API"

    def test_evidence_reference_contains_symbol(self) -> None:
        cfg = {"engine": "stock", "market": "index", "board": "SNDX", "security": "IMOEX"}
        ev = _build_evidence("IMOEX", cfg, "2023-01-01", "2023-12-31", "2026-06-27T12:00:00")
        assert "IMOEX" in ev.reference

    def test_evidence_timestamp_passed_through(self) -> None:
        cfg = {"engine": "stock", "market": "index", "board": "SNDX", "security": "IMOEX"}
        ev = _build_evidence("IMOEX", cfg, "2023-01-01", "2023-12-31", "2026-06-27T12:00:00")
        assert ev.timestamp == "2026-06-27T12:00:00"
