"""MacroAgent — Layer 1 Data Agent for macro/market context.

Fetches daily time series for macro indicators from MOEX ISS and
writes them to data/context/macro/{period}/{symbol}_{timeframe}.csv.

Supported symbols (MOEX ISS):
    IMOEX   — Moscow Exchange Composite Index
    USDRUB  — USD/RUB exchange rate (USD000UTSTOM)
    RGBI    — Russian Government Bond Index

Output directory is separate from OHLCV datasets and is never
consumed by Research Service (data/context/, not data/datasets/).
"""
from __future__ import annotations

import csv
import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from agents.models import (
    AgentResult,
    ConfidenceScore,
    EvidenceRef,
    MacroSeries,
    MacroSnapshot,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AGENT_ID = "macro-agent"
_AGENT_TYPE = "DATA"
_VERSION = "1.0"

# Supported symbols → MOEX ISS routing config
_SYMBOL_CONFIGS: dict[str, dict[str, str]] = {
    "IMOEX": {
        "engine": "stock",
        "market": "index",
        "board": "SNDX",
        "security": "IMOEX",
    },
    "USDRUB": {
        "engine": "currency",
        "market": "selt",
        "board": "CETS",
        "security": "USD000UTSTOM",
    },
    "RGBI": {
        "engine": "stock",
        "market": "index",
        "board": "SNDX",
        "security": "RGBI",
    },
}

DEFAULT_SYMBOLS: tuple[str, ...] = ("IMOEX", "USDRUB", "RGBI")

_URL_TEMPLATE = (
    "https://iss.moex.com/iss/engines/{engine}/markets/{market}/boards/{board}"
    "/securities/{security}/candles.json"
    "?interval={interval}&from={date_from}&till={date_to}&start={offset}"
)
_INTERVAL_MAP = {"1d": 24, "1h": 60}
_PAGE_SIZE = 500


# ---------------------------------------------------------------------------
# MacroSource implementations
# ---------------------------------------------------------------------------

class MoexMacroSource:
    """Fetches daily macro data from the public MOEX ISS API.

    Each returned dict has keys: date, open, high, low, close, volume.
    Uses stdlib urllib — no external dependencies.
    """

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
    ) -> list[dict]:
        cfg = _SYMBOL_CONFIGS.get(symbol)
        if cfg is None:
            raise ValueError(
                f"MacroAgent: unknown symbol '{symbol}'. "
                f"Supported: {sorted(_SYMBOL_CONFIGS)}"
            )

        interval = _INTERVAL_MAP.get(timeframe, 24)
        rows: list[dict] = []
        offset = 0

        while True:
            url = _URL_TEMPLATE.format(
                engine=cfg["engine"],
                market=cfg["market"],
                board=cfg["board"],
                security=cfg["security"],
                interval=interval,
                date_from=date_from,
                date_to=date_to,
                offset=offset,
            )
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except urllib.error.URLError as exc:
                raise RuntimeError(
                    f"MOEX ISS macro request failed for {symbol}: {exc}"
                ) from exc

            block = payload.get("candles", {})
            columns: list[str] = block.get("columns", [])
            data: list[list] = block.get("data", [])

            if not data:
                break

            idx = {col: i for i, col in enumerate(columns)}
            for row in data:
                begin: str = str(row[idx["begin"]])
                date = begin[:10]   # "YYYY-MM-DD"
                rows.append(
                    {
                        "date": date,
                        "open": float(row[idx["open"]]),
                        "high": float(row[idx["high"]]),
                        "low": float(row[idx["low"]]),
                        "close": float(row[idx["close"]]),
                        "volume": int(float(row[idx["volume"]] or 0)),
                    }
                )

            if len(data) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE

        return rows


class FixtureMacroSource:
    """Returns pre-baked rows per symbol — use in tests to avoid HTTP calls.

    Pass a dict mapping symbol → list[dict], where each dict has:
    {date, open, high, low, close, volume}.
    Unknown symbols return an empty list.
    """

    def __init__(self, data: dict[str, list[dict]]) -> None:
        self._data = {k: list(v) for k, v in data.items()}

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
    ) -> list[dict]:
        return list(self._data.get(symbol, []))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_series(
    data_dir: Path,
    symbol: str,
    timeframe: str,
    period: str,
    rows: list[dict],
) -> str:
    """Write rows to CSV and return the absolute path."""
    series_dir = data_dir / "context" / "macro" / period
    series_dir.mkdir(parents=True, exist_ok=True)

    path = series_dir / f"{symbol}_{timeframe}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "open", "high", "low", "close", "volume"])
        for r in rows:
            writer.writerow(
                [r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"]]
            )
    return str(path.resolve())


def _build_evidence(
    symbol: str, cfg: dict[str, str], date_from: str, date_to: str, ts: str
) -> EvidenceRef:
    ref_url = _URL_TEMPLATE.format(
        engine=cfg["engine"],
        market=cfg["market"],
        board=cfg["board"],
        security=cfg["security"],
        interval=24,
        date_from=date_from,
        date_to=date_to,
        offset=0,
    )
    return EvidenceRef(source="MOEX ISS API", reference=ref_url, timestamp=ts)


# ---------------------------------------------------------------------------
# MacroAgent
# ---------------------------------------------------------------------------

class MacroAgent:
    """Layer 1 Data Agent — macro/market context ingestion from MOEX ISS.

    Writes per-symbol CSVs to data/context/macro/{period}/.
    Returns AgentResult[MacroSnapshot].
    Inject a FixtureMacroSource for deterministic tests.
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
        self._source = source or MoexMacroSource()

    def run(
        self,
        period: str,
        symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
        timeframe: str = "1d",
        _clock: Optional[Callable[[], datetime]] = None,
    ) -> AgentResult:
        """Fetch macro series, write CSVs, return AgentResult[MacroSnapshot].

        Parameters
        ----------
        period:    year string, e.g. "2023"
        symbols:   tuple of symbol names to fetch (default: IMOEX, USDRUB, RGBI)
        timeframe: "1d" (default) | "1h"
        _clock:    injected clock for determinism in tests
        """
        clock = _clock or datetime.now
        created_at = clock().isoformat(timespec="seconds")

        date_from = f"{period}-01-01"
        date_to = f"{period}-12-31"

        series_list: list[MacroSeries] = []
        evidence_list: list[EvidenceRef] = []
        missing: list[tuple[str, int]] = []

        for symbol in symbols:
            cfg = _SYMBOL_CONFIGS.get(symbol, {})

            try:
                rows = self._source.fetch(symbol, timeframe, date_from, date_to)
            except Exception:
                missing.append((symbol, 0))
                continue

            if not rows:
                missing.append((symbol, 0))
                continue

            path = _write_series(self._data_dir, symbol, timeframe, period, rows)
            series_list.append(
                MacroSeries(
                    symbol=symbol,
                    timeframe=timeframe,
                    date_from=rows[0]["date"],
                    date_to=rows[-1]["date"],
                    value_count=len(rows),
                    path=path,
                )
            )

            if cfg:
                evidence_list.append(
                    _build_evidence(symbol, cfg, date_from, date_to, created_at)
                )
            else:
                evidence_list.append(
                    EvidenceRef(
                        source="fixture",
                        reference=f"fixture://{symbol}",
                        timestamp=created_at,
                    )
                )

        fetched = len(series_list)
        total = len(symbols)
        confidence_value = fetched / total if total > 0 else 0.0
        confidence_reason = (
            f"{fetched}/{total} symbols fetched successfully"
            if missing
            else "all symbols fetched"
        )

        snapshot = MacroSnapshot(
            snapshot_id=f"macro_{period}_{timeframe}",
            period=period,
            observations=tuple(series_list),
            source_refs=tuple(evidence_list),
            missing_values=tuple(missing),
            confidence=ConfidenceScore(
                value=confidence_value, reason=confidence_reason
            ),
        )

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            version=self.version,
            input_summary=(
                f"macro period={period} symbols={','.join(symbols)} tf={timeframe}"
            ),
            output=snapshot,
            evidence=tuple(evidence_list),
            confidence=snapshot.confidence,
            created_at=created_at,
        )
