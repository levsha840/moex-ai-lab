"""Tests for MarketAgent — Layer 1 Data Agent.

All tests use FixtureSource — no HTTP calls, no real MOEX data.
Integration test (DatasetLoader compatibility) uses tmp_path fixture.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from agents.data.market import (
    FixtureSource,
    MarketAgent,
    _build_dataset_id,
    _filter_session,
    _resample_bars,
    _resample_daily,
)
from agents.models import AgentResult, ConfidenceScore, DatasetManifest, EvidenceRef
from agents.protocols import AgentProtocol, CandleSource
from services.research.dataset import DatasetLoader, OhlcvDataset


# ---------------------------------------------------------------------------
# Fixture factories
# ---------------------------------------------------------------------------

def _make_candles(
    ticker: str = "SBER",
    days: int = 3,
    hours: tuple[int, ...] = (9, 10, 11, 12, 13, 14, 15, 16, 17, 18),
) -> list[dict]:
    """Synthetic 1-H candles across `days` days at the given hours."""
    candles: list[dict] = []
    base_dates = ["2023-01-10", "2023-01-11", "2023-01-12", "2023-01-13"]
    base_price = 100.0
    i = 0
    for d in range(days):
        date = base_dates[d]
        for h in hours:
            price = base_price + i * 0.5
            candles.append(
                {
                    "ticker": ticker,
                    "ts": f"{date} {h:02d}:00:00",
                    "open": price,
                    "high": price + 0.5,
                    "low": price - 0.5,
                    "close": price + 0.2,
                    "volume": 1000 + i * 10,
                }
            )
            i += 1
    return candles


def _mixed_candles() -> list[dict]:
    """Main + evening session candles for 2 days (2×12 = 24 bars total)."""
    return _make_candles(days=2, hours=(9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20))


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 27, 12, 0, 0)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestAgentProtocolConformance:
    def test_market_agent_satisfies_agent_protocol(self, tmp_path: Path) -> None:
        agent = MarketAgent(data_dir=tmp_path)
        # structural check — AgentProtocol attributes and run() must exist
        assert isinstance(agent.agent_id, str)
        assert isinstance(agent.agent_type, str)
        assert isinstance(agent.version, str)
        assert callable(agent.run)

    def test_agent_id_is_stable(self, tmp_path: Path) -> None:
        agent = MarketAgent(data_dir=tmp_path)
        assert agent.agent_id == "market-agent"

    def test_agent_type_is_data(self, tmp_path: Path) -> None:
        agent = MarketAgent(data_dir=tmp_path)
        assert agent.agent_type == "DATA"

    def test_version_is_string(self, tmp_path: Path) -> None:
        agent = MarketAgent(data_dir=tmp_path)
        assert agent.version == "1.0"

    def test_fixture_source_satisfies_candle_source_protocol(self) -> None:
        src = FixtureSource(candles=[])
        assert callable(src.fetch)
        result = src.fetch("SBER", "1h", "2023-01-10", "2023-12-29")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Session filtering
# ---------------------------------------------------------------------------

class TestSessionFilter:
    def test_main_filter_removes_evening_bars(self) -> None:
        candles = _mixed_candles()
        filtered = _filter_session(candles, "main")
        hours = {int(c["ts"][11:13]) for c in filtered}
        assert 19 not in hours
        assert 20 not in hours

    def test_main_filter_keeps_all_main_hours(self) -> None:
        candles = _mixed_candles()
        filtered = _filter_session(candles, "main")
        hours = sorted({int(c["ts"][11:13]) for c in filtered})
        assert hours == list(range(9, 19))

    def test_full_filter_keeps_all_bars(self) -> None:
        candles = _mixed_candles()
        filtered = _filter_session(candles, "full")
        assert len(filtered) == len(candles)

    def test_main_filter_bar_count(self) -> None:
        candles = _make_candles(days=2, hours=(9, 10, 18, 19, 20))
        filtered = _filter_session(candles, "main")
        # 2 days × 3 main-session hours (9, 10, 18) = 6
        assert len(filtered) == 6

    def test_hour_9_included_in_main(self) -> None:
        candles = [{"ticker": "X", "ts": "2023-01-10 09:00:00",
                    "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}]
        filtered = _filter_session(candles, "main")
        assert len(filtered) == 1

    def test_hour_18_included_in_main(self) -> None:
        candles = [{"ticker": "X", "ts": "2023-01-10 18:00:00",
                    "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}]
        filtered = _filter_session(candles, "main")
        assert len(filtered) == 1

    def test_hour_19_excluded_from_main(self) -> None:
        candles = [{"ticker": "X", "ts": "2023-01-10 19:00:00",
                    "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}]
        filtered = _filter_session(candles, "main")
        assert len(filtered) == 0


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------

class TestResampleBars:
    def test_2h_halves_bar_count(self) -> None:
        candles = _make_candles(days=1, hours=(9, 10, 11, 12, 13, 14, 15, 16, 17, 18))
        resampled = _resample_bars(candles, 2)
        assert len(resampled) == 5

    def test_4h_quarters_bar_count(self) -> None:
        candles = _make_candles(days=1, hours=(9, 10, 11, 12, 13, 14, 15, 16, 17, 18))
        resampled = _resample_bars(candles, 4)
        # 10 / 4 = 2 full chunks + 1 partial → 3 bars
        assert len(resampled) == 3

    def test_open_is_first_bar(self) -> None:
        candles = _make_candles(days=1, hours=(9, 10))
        resampled = _resample_bars(candles, 2)
        assert resampled[0]["open"] == candles[0]["open"]

    def test_close_is_last_bar(self) -> None:
        candles = _make_candles(days=1, hours=(9, 10))
        resampled = _resample_bars(candles, 2)
        assert resampled[0]["close"] == candles[1]["close"]

    def test_high_is_max(self) -> None:
        candles = [
            {"ticker": "X", "ts": "2023-01-10 09:00:00",
             "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1000},
            {"ticker": "X", "ts": "2023-01-10 10:00:00",
             "open": 101.0, "high": 105.0, "low": 100.0, "close": 104.0, "volume": 2000},
        ]
        r = _resample_bars(candles, 2)
        assert r[0]["high"] == 105.0

    def test_low_is_min(self) -> None:
        candles = [
            {"ticker": "X", "ts": "2023-01-10 09:00:00",
             "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1000},
            {"ticker": "X", "ts": "2023-01-10 10:00:00",
             "open": 101.0, "high": 105.0, "low": 100.0, "close": 104.0, "volume": 2000},
        ]
        r = _resample_bars(candles, 2)
        assert r[0]["low"] == 99.0

    def test_volume_is_sum(self) -> None:
        candles = [
            {"ticker": "X", "ts": "2023-01-10 09:00:00",
             "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000},
            {"ticker": "X", "ts": "2023-01-10 10:00:00",
             "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 2000},
        ]
        r = _resample_bars(candles, 2)
        assert r[0]["volume"] == 3000

    def test_ts_is_first_bar_ts(self) -> None:
        candles = _make_candles(days=1, hours=(9, 10))
        resampled = _resample_bars(candles, 2)
        assert resampled[0]["ts"] == candles[0]["ts"]


class TestResampleDaily:
    def test_one_bar_per_day(self) -> None:
        candles = _make_candles(days=3, hours=(9, 10, 11))
        resampled = _resample_daily(candles)
        assert len(resampled) == 3

    def test_daily_ts_format(self) -> None:
        candles = _make_candles(days=1, hours=(9, 10))
        resampled = _resample_daily(candles)
        assert resampled[0]["ts"] == "2023-01-10 00:00:00"

    def test_daily_open_is_first_hour(self) -> None:
        candles = _make_candles(days=1, hours=(9, 10, 11))
        resampled = _resample_daily(candles)
        assert resampled[0]["open"] == candles[0]["open"]

    def test_daily_close_is_last_hour(self) -> None:
        candles = _make_candles(days=1, hours=(9, 10, 11))
        resampled = _resample_daily(candles)
        assert resampled[0]["close"] == candles[2]["close"]

    def test_daily_volume_is_sum(self) -> None:
        candles = _make_candles(days=1, hours=(9, 10, 11))
        total_volume = sum(c["volume"] for c in candles)
        resampled = _resample_daily(candles)
        assert resampled[0]["volume"] == total_volume


# ---------------------------------------------------------------------------
# Dataset ID generation
# ---------------------------------------------------------------------------

class TestBuildDatasetId:
    def test_lowercase_ticker(self) -> None:
        ds_id = _build_dataset_id("SBER", "1h", "2023-01-10", "main")
        assert ds_id.startswith("sber_")

    def test_includes_timeframe(self) -> None:
        ds_id = _build_dataset_id("SBER", "4h", "2023-01-10", "main")
        assert "4h" in ds_id

    def test_includes_year(self) -> None:
        ds_id = _build_dataset_id("SBER", "1h", "2023-01-10", "main")
        assert "2023" in ds_id

    def test_includes_session_filter(self) -> None:
        main_id = _build_dataset_id("SBER", "1h", "2023-01-10", "main")
        full_id = _build_dataset_id("SBER", "1h", "2023-01-10", "full")
        assert "main" in main_id
        assert "full" in full_id
        assert main_id != full_id


# ---------------------------------------------------------------------------
# MarketAgent — fixture mode run
# ---------------------------------------------------------------------------

class TestMarketAgentFixtureRun:
    def _agent(self, tmp_path: Path, candles: list[dict]) -> MarketAgent:
        return MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))

    def test_returns_agent_result(self, tmp_path: Path) -> None:
        candles = _make_candles(days=3)
        agent = self._agent(tmp_path, candles)
        result = agent.run("SBER", "1h", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        assert isinstance(result, AgentResult)

    def test_agent_id_in_result(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29", _clock=_fixed_clock
        )
        assert result.agent_id == "market-agent"

    def test_agent_type_in_result(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29", _clock=_fixed_clock
        )
        assert result.agent_type == "DATA"

    def test_output_is_dataset_manifest(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29", _clock=_fixed_clock
        )
        assert isinstance(result.output, DatasetManifest)

    def test_created_at_uses_injected_clock(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29", _clock=_fixed_clock
        )
        assert result.created_at == "2026-06-27T12:00:00"

    def test_confidence_is_high_when_bars_returned(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29", _clock=_fixed_clock
        )
        assert result.confidence.value == 1.0

    def test_confidence_is_zero_when_no_bars(self, tmp_path: Path) -> None:
        result = self._agent(tmp_path, candles=[]).run(
            "SBER", "1h", "2023-01-10", "2023-12-29", _clock=_fixed_clock
        )
        assert result.confidence.value == 0.0

    def test_evidence_tuple_not_empty(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29", _clock=_fixed_clock
        )
        assert len(result.evidence) >= 1
        assert isinstance(result.evidence[0], EvidenceRef)

    def test_evidence_source_is_moex_iss(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29", _clock=_fixed_clock
        )
        assert result.evidence[0].source == "MOEX ISS API"

    def test_custom_dataset_id(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29",
            dataset_id="my_custom_dataset", _clock=_fixed_clock
        )
        manifest: DatasetManifest = result.output  # type: ignore[assignment]
        assert manifest.dataset_id == "my_custom_dataset"

    def test_session_filter_applied(self, tmp_path: Path) -> None:
        candles = _mixed_candles()  # 12 hours/day including evening
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29",
            session_filter="main", _clock=_fixed_clock
        )
        manifest: DatasetManifest = result.output  # type: ignore[assignment]
        # 2 days × 10 main session hours = 20 bars
        assert manifest.bar_count == 20

    def test_full_session_keeps_all_bars(self, tmp_path: Path) -> None:
        candles = _mixed_candles()  # 12 hours/day × 2 days = 24
        result = self._agent(tmp_path, candles).run(
            "SBER", "1h", "2023-01-10", "2023-12-29",
            session_filter="full", _clock=_fixed_clock
        )
        manifest: DatasetManifest = result.output  # type: ignore[assignment]
        assert manifest.bar_count == 24


# ---------------------------------------------------------------------------
# DatasetManifest — content validation
# ---------------------------------------------------------------------------

class TestDatasetManifestContent:
    def _run(self, tmp_path: Path, session: str = "main") -> DatasetManifest:
        candles = _make_candles(days=3)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("SBER", "1h", "2023-01-10", "2023-12-29",
                           session_filter=session, _clock=_fixed_clock)
        return result.output  # type: ignore[return-value]

    def test_ticker_matches(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        assert m.ticker == "SBER"

    def test_timeframe_matches(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        assert m.timeframe == "1h"

    def test_source_is_moex_iss(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        assert m.source == "MOEX ISS API"

    def test_session_filter_recorded(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        assert m.session_filter == "main"

    def test_date_from_populated(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        assert m.date_from.startswith("2023-01-10")

    def test_bar_count_positive(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        assert m.bar_count > 0

    def test_ohlcv_path_exists_after_run(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        assert Path(m.ohlcv_path).exists()

    def test_metadata_path_exists_after_run(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        assert Path(m.metadata_path).exists()

    def test_dataset_path_is_directory(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        assert Path(m.dataset_path).is_dir()


# ---------------------------------------------------------------------------
# On-disk file content
# ---------------------------------------------------------------------------

class TestOnDiskFiles:
    def _run(self, tmp_path: Path) -> DatasetManifest:
        candles = _make_candles(days=2)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("SBER", "1h", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        return result.output  # type: ignore[return-value]

    def test_metadata_json_has_required_fields(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        with open(m.metadata_path, encoding="utf-8") as f:
            meta = json.load(f)
        for field in ("dataset_id", "ticker", "timeframe", "bar_count"):
            assert field in meta, f"Missing field: {field}"

    def test_metadata_ticker_correct(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        with open(m.metadata_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["ticker"] == "SBER"

    def test_metadata_bar_count_matches_manifest(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        with open(m.metadata_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["bar_count"] == m.bar_count

    def test_ohlcv_csv_has_correct_header(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        with open(m.ohlcv_path, encoding="utf-8") as f:
            header = f.readline().strip()
        assert header == "datetime,open,high,low,close,volume"

    def test_ohlcv_row_count_matches_bar_count(self, tmp_path: Path) -> None:
        m = self._run(tmp_path)
        with open(m.ohlcv_path, encoding="utf-8") as f:
            lines = f.readlines()
        data_rows = len(lines) - 1  # subtract header
        assert data_rows == m.bar_count


# ---------------------------------------------------------------------------
# DatasetLoader compatibility — integration
# ---------------------------------------------------------------------------

class TestDatasetLoaderCompatibility:
    def test_dataset_loader_loads_market_agent_output(self, tmp_path: Path) -> None:
        candles = _make_candles(days=3)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("SBER", "1h", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        manifest: DatasetManifest = result.output  # type: ignore[assignment]

        loaded: OhlcvDataset = DatasetLoader().load(manifest.dataset_id, tmp_path)

        assert loaded.dataset_id == manifest.dataset_id
        assert loaded.ticker == "SBER"
        assert loaded.timeframe == "1h"
        assert loaded.bar_count == manifest.bar_count

    def test_loaded_candle_keys_match_h13_provider_format(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("SBER", "1h", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        manifest: DatasetManifest = result.output  # type: ignore[assignment]

        loaded = DatasetLoader().load(manifest.dataset_id, tmp_path)
        expected_keys = {"ticker", "ts", "open", "high", "low", "close", "volume"}
        for candle in loaded.candles[:5]:
            assert set(candle.keys()) == expected_keys

    def test_loaded_ohlc_types_are_float(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("SBER", "1h", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        manifest: DatasetManifest = result.output  # type: ignore[assignment]

        loaded = DatasetLoader().load(manifest.dataset_id, tmp_path)
        for candle in loaded.candles[:10]:
            assert isinstance(candle["open"], float)
            assert isinstance(candle["high"], float)
            assert isinstance(candle["low"], float)
            assert isinstance(candle["close"], float)

    def test_loaded_volume_is_int(self, tmp_path: Path) -> None:
        candles = _make_candles(days=2)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("SBER", "1h", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        manifest: DatasetManifest = result.output  # type: ignore[assignment]

        loaded = DatasetLoader().load(manifest.dataset_id, tmp_path)
        for candle in loaded.candles[:10]:
            assert isinstance(candle["volume"], int)

    def test_loaded_candles_in_chronological_order(self, tmp_path: Path) -> None:
        candles = _make_candles(days=3)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("SBER", "1h", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        manifest: DatasetManifest = result.output  # type: ignore[assignment]

        loaded = DatasetLoader().load(manifest.dataset_id, tmp_path)
        timestamps = [c["ts"] for c in loaded.candles]
        assert timestamps == sorted(timestamps)

    def test_loaded_ticker_matches_agent_input(self, tmp_path: Path) -> None:
        candles = _make_candles(ticker="GAZP", days=2)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("GAZP", "1h", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        manifest: DatasetManifest = result.output  # type: ignore[assignment]

        loaded = DatasetLoader().load(manifest.dataset_id, tmp_path)
        assert loaded.ticker == "GAZP"
        for candle in loaded.candles:
            assert candle["ticker"] == "GAZP"

    def test_2h_timeframe_dataset_loads_successfully(self, tmp_path: Path) -> None:
        candles = _make_candles(days=3)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("SBER", "2h", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        manifest: DatasetManifest = result.output  # type: ignore[assignment]

        loaded = DatasetLoader().load(manifest.dataset_id, tmp_path)
        assert loaded.timeframe == "2h"
        # 3 days × 10 bars → filtered → resampled ×2 = 15 bars
        assert loaded.bar_count == 15

    def test_1d_timeframe_dataset_loads_successfully(self, tmp_path: Path) -> None:
        candles = _make_candles(days=3)
        agent = MarketAgent(data_dir=tmp_path, source=FixtureSource(candles))
        result = agent.run("SBER", "1d", "2023-01-10", "2023-12-29",
                           _clock=_fixed_clock)
        manifest: DatasetManifest = result.output  # type: ignore[assignment]

        loaded = DatasetLoader().load(manifest.dataset_id, tmp_path)
        assert loaded.timeframe == "1d"
        assert loaded.bar_count == 3  # one bar per day
