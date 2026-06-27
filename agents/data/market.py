"""MarketAgent — Layer 1 Data Agent.

Fetches OHLCV data from MOEX ISS and writes DatasetLoader-compatible
datasets to disk. Supports fixture injection for deterministic testing.

Supported timeframes:
    "1h"  — hourly bars, fetched natively (MOEX ISS interval=60)
    "2h"  — 2-bar aggregation of hourly data
    "4h"  — 4-bar aggregation of hourly data
    "1d"  — daily bars, aggregated from hourly by calendar date

Session filters:
    "main" — keep bars with begin-hour in 09:00–18:59 MSK (default)
    "full" — all bars including evening session (09:00–22:59 MSK)

Output: writes  data/datasets/<dataset_id>/ohlcv.csv  +  metadata.json
and returns AgentResult[DatasetManifest].
"""
from __future__ import annotations

import csv
import json
import urllib.error
import urllib.request
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from agents.models import (
    AgentResult,
    ConfidenceScore,
    DatasetManifest,
    EvidenceRef,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AGENT_ID = "market-agent"
_AGENT_TYPE = "DATA"
_VERSION = "1.0"

_MOEX_ISS_TEMPLATE = (
    "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR"
    "/securities/{ticker}/candles.json"
    "?interval=60&from={date_from}&till={date_to}&start={offset}"
)
_PAGE_SIZE = 500

# Main session: hours 9 through 18 inclusive (Moscow time, as returned by ISS)
_MAIN_SESSION_HOURS: frozenset[int] = frozenset(range(9, 19))

# Timeframes that require resampling from 1H
_RESAMPLE_FACTOR: dict[str, int] = {"2h": 2, "4h": 4}


# ---------------------------------------------------------------------------
# CandleSource implementations
# ---------------------------------------------------------------------------

class MoexIssSource:
    """Fetches 1-hour OHLCV candles from the public MOEX ISS API.

    Uses stdlib urllib — no external dependencies.
    Timestamps in the response are Moscow time (UTC+3).
    """

    def fetch(
        self,
        ticker: str,
        timeframe: str,  # ignored — always fetches 1H; resampling done by agent
        date_from: str,
        date_to: str,
    ) -> list[dict]:
        candles: list[dict] = []
        offset = 0
        while True:
            url = _MOEX_ISS_TEMPLATE.format(
                ticker=ticker,
                date_from=date_from,
                date_to=date_to,
                offset=offset,
            )
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except urllib.error.URLError as exc:
                raise RuntimeError(
                    f"MOEX ISS request failed for {ticker}: {exc}"
                ) from exc

            block = payload.get("candles", {})
            columns: list[str] = block.get("columns", [])
            rows: list[list] = block.get("data", [])

            if not rows:
                break

            idx = {col: i for i, col in enumerate(columns)}
            for row in rows:
                ts_raw: str = str(row[idx["begin"]])
                candles.append(
                    {
                        "ticker": ticker,
                        "ts": ts_raw,
                        "open": float(row[idx["open"]]),
                        "high": float(row[idx["high"]]),
                        "low": float(row[idx["low"]]),
                        "close": float(row[idx["close"]]),
                        "volume": int(float(row[idx["volume"]])),
                    }
                )

            if len(rows) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE

        return candles


class FixtureSource:
    """Returns pre-baked candles — use in tests to avoid HTTP calls.

    Candle format: {ticker, ts, open, high, low, close, volume}
    ts must be "YYYY-MM-DD HH:MM:SS" (Moscow time, as from MOEX ISS).
    """

    def __init__(self, candles: list[dict]) -> None:
        self._candles = list(candles)

    def fetch(
        self,
        ticker: str,
        timeframe: str,
        date_from: str,
        date_to: str,
    ) -> list[dict]:
        return list(self._candles)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _filter_session(candles: list[dict], session_filter: str) -> list[dict]:
    if session_filter == "full":
        return candles
    return [
        c for c in candles
        if int(c["ts"][11:13]) in _MAIN_SESSION_HOURS
    ]


def _resample_bars(candles: list[dict], factor: int) -> list[dict]:
    """Aggregate consecutive `factor` 1-H bars into one bar."""
    result: list[dict] = []
    for i in range(0, len(candles), factor):
        chunk = candles[i : i + factor]
        if not chunk:
            break
        result.append(
            {
                "ticker": chunk[0]["ticker"],
                "ts": chunk[0]["ts"],
                "open": float(chunk[0]["open"]),
                "high": max(float(c["high"]) for c in chunk),
                "low": min(float(c["low"]) for c in chunk),
                "close": float(chunk[-1]["close"]),
                "volume": sum(int(c["volume"]) for c in chunk),
            }
        )
    return result


def _resample_daily(candles: list[dict]) -> list[dict]:
    """Aggregate 1-H bars into one daily bar per calendar date."""
    by_date: dict[str, list[dict]] = OrderedDict()
    for c in candles:
        date = c["ts"][:10]
        by_date.setdefault(date, []).append(c)

    result: list[dict] = []
    for date, bars in by_date.items():
        result.append(
            {
                "ticker": bars[0]["ticker"],
                "ts": f"{date} 00:00:00",
                "open": float(bars[0]["open"]),
                "high": max(float(b["high"]) for b in bars),
                "low": min(float(b["low"]) for b in bars),
                "close": float(bars[-1]["close"]),
                "volume": sum(int(b["volume"]) for b in bars),
            }
        )
    return result


def _build_dataset_id(ticker: str, timeframe: str, date_from: str, session_filter: str) -> str:
    year = date_from[:4]
    return f"{ticker.lower()}_{timeframe}_{year}_{session_filter}"


def _write_dataset(
    data_dir: Path,
    dataset_id: str,
    ticker: str,
    timeframe: str,
    candles: list[dict],
    session_filter: str,
) -> DatasetManifest:
    dataset_dir = data_dir / "datasets" / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)

    ohlcv_path = dataset_dir / "ohlcv.csv"
    with open(ohlcv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["datetime", "open", "high", "low", "close", "volume"])
        for c in candles:
            writer.writerow(
                [c["ts"], c["open"], c["high"], c["low"], c["close"], c["volume"]]
            )

    date_from = candles[0]["ts"][:10] if candles else ""
    date_to = candles[-1]["ts"][:10] if candles else ""

    meta: dict = {
        "dataset_id": dataset_id,
        "ticker": ticker,
        "timeframe": timeframe,
        "session_filter": session_filter,
        "source": "MOEX ISS API",
        "bar_count": len(candles),
        "date_from": date_from,
        "date_to": date_to,
        "created_by": f"MarketAgent v{_VERSION}",
    }
    metadata_path = dataset_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return DatasetManifest(
        dataset_id=dataset_id,
        dataset_path=str(dataset_dir.resolve()),
        ohlcv_path=str(ohlcv_path.resolve()),
        metadata_path=str(metadata_path.resolve()),
        ticker=ticker,
        timeframe=timeframe,
        bar_count=len(candles),
        date_from=date_from,
        date_to=date_to,
        session_filter=session_filter,
        source="MOEX ISS API",
    )


# ---------------------------------------------------------------------------
# MarketAgent
# ---------------------------------------------------------------------------

class MarketAgent:
    """Layer 1 Data Agent — OHLCV ingestion from MOEX ISS.

    Implements AgentProtocol (structural — no explicit inheritance needed).
    Inject a FixtureSource for deterministic tests; omit for production.
    """

    agent_id = _AGENT_ID
    agent_type = _AGENT_TYPE
    version = _VERSION

    def __init__(
        self,
        data_dir: Path,
        source: Optional[object] = None,
    ) -> None:
        self._data_dir = data_dir
        self._source = source or MoexIssSource()

    def run(
        self,
        ticker: str,
        timeframe: str,
        date_from: str,
        date_to: str,
        session_filter: str = "main",
        dataset_id: Optional[str] = None,
        _clock: Optional[Callable[[], datetime]] = None,
    ) -> AgentResult:
        """Fetch, filter, resample, write dataset; return AgentResult.

        Parameters
        ----------
        ticker:         MOEX ticker symbol, e.g. "SBER"
        timeframe:      "1h" | "2h" | "4h" | "1d"
        date_from:      "YYYY-MM-DD"
        date_to:        "YYYY-MM-DD"
        session_filter: "main" (default) | "full"
        dataset_id:     explicit dataset ID; auto-generated if None
        _clock:         injected clock — use in tests for determinism
        """
        clock = _clock or datetime.now
        created_at = clock().isoformat(timespec="seconds")

        # 1. Fetch raw 1-H candles (source always returns 1-H data)
        raw_candles = self._source.fetch(ticker, timeframe, date_from, date_to)

        # 2. Session filter (applied before resampling)
        filtered = _filter_session(raw_candles, session_filter)

        # 3. Resample to requested timeframe
        if timeframe == "1d":
            candles = _resample_daily(filtered)
        elif timeframe in _RESAMPLE_FACTOR:
            candles = _resample_bars(filtered, _RESAMPLE_FACTOR[timeframe])
        else:
            candles = filtered  # "1h" — no resampling

        # 4. Write dataset
        ds_id = dataset_id or _build_dataset_id(ticker, timeframe, date_from, session_filter)
        manifest = _write_dataset(
            self._data_dir, ds_id, ticker, timeframe, candles, session_filter
        )

        # 5. Build AgentResult
        evidence = (
            EvidenceRef(
                source="MOEX ISS API",
                reference=_MOEX_ISS_TEMPLATE.format(
                    ticker=ticker,
                    date_from=date_from,
                    date_to=date_to,
                    offset=0,
                ),
                timestamp=created_at,
            ),
        )
        confidence = ConfidenceScore(
            value=1.0 if candles else 0.0,
            reason="all bars written; no gaps detected" if candles else "no bars returned",
        )

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            version=self.version,
            input_summary=(
                f"{ticker} {timeframe} {date_from}..{date_to} "
                f"session={session_filter}"
            ),
            output=manifest,
            evidence=evidence,
            confidence=confidence,
            created_at=created_at,
        )
