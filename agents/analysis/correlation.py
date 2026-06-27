"""CorrelationAgent — Layer 2 Analysis Agent.

Computes Pearson correlation of daily returns between an equity instrument
and macro context series (IMOEX, USDRUB, RGBI) at multiple lags.

No trading signals. No predictions. Context analysis only.
Results saved to data/context/correlation/{instrument.lower()}_{period}.json.

Supported lags (trading days):
    0   same-period
    +1  macro leads instrument by 1 day
    -1  instrument leads macro by 1 day
    +5  macro leads instrument by 5 days (1 week)
    -5  instrument leads macro by 5 days
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from agents.models import (
    AgentResult,
    ConfidenceScore,
    CorrelationPair,
    CorrelationSnapshot,
    EvidenceRef,
)

_AGENT_ID = "correlation-agent"
_AGENT_TYPE = "ANALYSIS"
_VERSION = "1.0"
DEFAULT_LAGS: tuple[int, ...] = (0, -1, 1, -5, 5)
DEFAULT_MACRO_SYMBOLS: tuple[str, ...] = ("IMOEX", "USDRUB", "RGBI")
_MIN_OBS = 3  # minimum aligned observations to compute correlation


# ---------------------------------------------------------------------------
# Source implementations
# ---------------------------------------------------------------------------

class FileCorrelationSource:
    """Loads data from disk.

    Instrument OHLCV: scans data/datasets/{instrument.lower()}_*{period}*/ohlcv.csv
    and aggregates hourly bars to end-of-day closes.

    Macro series: reads data/context/macro/{period}/{symbol}_1d.csv.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def load_instrument(self, instrument: str, period: str) -> list[dict]:
        pattern = f"{instrument.lower()}_*{period}*"
        datasets_dir = self._data_dir / "datasets"
        if not datasets_dir.exists():
            return []
        for directory in sorted(datasets_dir.glob(pattern)):
            csv_path = directory / "ohlcv.csv"
            if csv_path.exists():
                return self._read_ohlcv(csv_path)
        return []

    def _read_ohlcv(self, path: Path) -> list[dict]:
        daily: dict[str, float] = {}
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                ts = row.get("datetime") or row.get("ts") or row.get("date", "")
                date = str(ts)[:10]
                daily[date] = float(row["close"])   # last row of day wins
        return [{"date": d, "close": c} for d, c in sorted(daily.items())]

    def load_macro_symbol(self, symbol: str, period: str) -> list[dict]:
        path = self._data_dir / "context" / "macro" / period / f"{symbol}_1d.csv"
        if not path.exists():
            return []
        result: list[dict] = []
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                result.append({"date": row["date"], "close": float(row["close"])})
        return sorted(result, key=lambda r: r["date"])


class FixtureCorrelationSource:
    """Pre-baked daily {date, close} data for tests — no file I/O.

    Pass instrument_data and macro_data as dicts of pre-baked rows.
    Unknown keys return an empty list.
    """

    def __init__(
        self,
        instrument_data: dict[str, list[dict]],
        macro_data: dict[str, list[dict]],
    ) -> None:
        self._instr = {k: list(v) for k, v in instrument_data.items()}
        self._macro = {k: list(v) for k, v in macro_data.items()}

    def load_instrument(self, instrument: str, period: str) -> list[dict]:
        return list(self._instr.get(instrument, []))

    def load_macro_symbol(self, symbol: str, period: str) -> list[dict]:
        return list(self._macro.get(symbol, []))


# ---------------------------------------------------------------------------
# Pure computation helpers (all stdlib, no side effects)
# ---------------------------------------------------------------------------

def _to_daily_series(rows: list[dict]) -> list[tuple[str, float]]:
    """Sort rows by date and return (date, close) pairs."""
    return sorted(
        ((row["date"], float(row["close"])) for row in rows),
        key=lambda x: x[0],
    )


def _compute_returns(daily: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Compute (date, (c_t / c_{t-1}) - 1). Skips bars where prev_close == 0."""
    result: list[tuple[str, float]] = []
    for i in range(1, len(daily)):
        prev = daily[i - 1][1]
        if prev == 0.0:
            continue
        result.append((daily[i][0], daily[i][1] / prev - 1.0))
    return result


def _align_returns(
    instr_rets: list[tuple[str, float]],
    macro_rets: list[tuple[str, float]],
) -> tuple[list[float], list[float]]:
    """Return two parallel float lists for dates present in both series."""
    macro_map = {d: r for d, r in macro_rets}
    xs: list[float] = []
    ys: list[float] = []
    for date, ret in instr_rets:
        if date in macro_map:
            xs.append(ret)
            ys.append(macro_map[date])
    return xs, ys


def _pearson(x: list[float], y: list[float]) -> float:
    """Pearson r. Returns math.nan if n < _MIN_OBS or either series has zero variance."""
    n = len(x)
    if n < _MIN_OBS:
        return math.nan
    xm = sum(x) / n
    ym = sum(y) / n
    num = sum((xi - xm) * (yi - ym) for xi, yi in zip(x, y))
    dx = math.sqrt(sum((xi - xm) ** 2 for xi in x))
    dy = math.sqrt(sum((yi - ym) ** 2 for yi in y))
    if dx == 0.0 or dy == 0.0:
        return math.nan
    return num / (dx * dy)


def _lagged_pearson(
    instr_rets: list[float],
    macro_rets: list[float],
    lag: int,
) -> tuple[float, int]:
    """Pearson correlation with trading-day lag.

    lag > 0: macro leads instrument — pairs (instr[t], macro[t-lag])
    lag < 0: instrument leads macro — pairs (instr[t], macro[t+abs(lag)])
    lag == 0: same-period

    Returns (r, observation_count).
    """
    if lag == 0:
        x, y = instr_rets, macro_rets
    elif lag > 0:
        x = instr_rets[lag:]
        y = macro_rets[:-lag]
    else:
        x = instr_rets[:lag]     # instr_rets[:-abs(lag)]
        y = macro_rets[-lag:]    # macro_rets[abs(lag):]
    n = len(x)
    return _pearson(x, y), n


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _write_snapshot(data_dir: Path, snapshot: CorrelationSnapshot) -> Path:
    """Serialise CorrelationSnapshot to JSON. Returns written path."""
    out_dir = data_dir / "context" / "correlation"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{snapshot.instrument.lower()}_{snapshot.period}.json"

    def _pair(p: CorrelationPair) -> dict:
        r = p.correlation
        return {
            "instrument": p.instrument,
            "macro_symbol": p.macro_symbol,
            "lag": p.lag,
            "correlation": None if math.isnan(r) else round(r, 6),
            "observation_count": p.observation_count,
        }

    payload = {
        "snapshot_id": snapshot.snapshot_id,
        "instrument": snapshot.instrument,
        "period": snapshot.period,
        "pairs": [_pair(p) for p in snapshot.pairs],
        "total_instrument_bars": snapshot.total_instrument_bars,
        "aligned_dates": snapshot.aligned_dates,
        "missing_alignment": snapshot.missing_alignment,
        "confidence_value": snapshot.confidence.value,
        "confidence_reason": snapshot.confidence.reason,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# CorrelationAgent
# ---------------------------------------------------------------------------

class CorrelationAgent:
    """Layer 2 Analysis Agent — daily-return correlation context analysis.

    For each macro symbol, computes Pearson r at multiple lags and assembles
    a CorrelationSnapshot. No signals, no predictions, no trades.

    Inject FixtureCorrelationSource for deterministic tests (no disk I/O).
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
        self._source = source or FileCorrelationSource(data_dir)

    def run(
        self,
        instrument: str,
        period: str,
        macro_symbols: tuple[str, ...] = DEFAULT_MACRO_SYMBOLS,
        lags: tuple[int, ...] = DEFAULT_LAGS,
        _clock: Optional[Callable[[], datetime]] = None,
    ) -> AgentResult:
        """Compute correlations and save CorrelationSnapshot.

        Parameters
        ----------
        instrument:    ticker string, e.g. "SBER"
        period:        year string, e.g. "2023"
        macro_symbols: which macro series to correlate against
        lags:          lag offsets in trading days (default: 0, ±1, ±5)
        _clock:        injected clock for determinism in tests
        """
        clock = _clock or datetime.now
        created_at = clock().isoformat(timespec="seconds")

        # --- load instrument ---
        instr_rows = self._source.load_instrument(instrument, period)
        instr_daily = _to_daily_series(instr_rows)
        instr_rets = _compute_returns(instr_daily)
        total_bars = len(instr_daily)
        instr_dates = {d for d, _ in instr_daily}

        # --- correlate against each macro symbol ---
        pairs: list[CorrelationPair] = []
        evidence: list[EvidenceRef] = []
        all_macro_dates: set[str] = set()

        for symbol in macro_symbols:
            macro_rows = self._source.load_macro_symbol(symbol, period)
            if not macro_rows:
                continue

            macro_daily = _to_daily_series(macro_rows)
            macro_rets = _compute_returns(macro_daily)

            for date, _ in macro_daily:
                all_macro_dates.add(date)

            i_aligned, m_aligned = _align_returns(instr_rets, macro_rets)

            for lag in lags:
                r, n = _lagged_pearson(i_aligned, m_aligned, lag)
                pairs.append(CorrelationPair(
                    instrument=instrument,
                    macro_symbol=symbol,
                    lag=lag,
                    correlation=r,
                    observation_count=n,
                ))

            evidence.append(EvidenceRef(
                source=f"macro/{symbol}",
                reference=str(
                    self._data_dir / "context" / "macro" / period / f"{symbol}_1d.csv"
                ),
                timestamp=created_at,
            ))

        # instrument provenance goes first
        evidence.insert(0, EvidenceRef(
            source=f"instrument/{instrument}",
            reference=f"data/datasets/{instrument.lower()}_*_{period}*",
            timestamp=created_at,
        ))

        # --- alignment stats ---
        aligned = len(instr_dates & all_macro_dates) if all_macro_dates else 0
        missing = total_bars - aligned

        # --- confidence: alignment ratio ---
        conf_value = aligned / total_bars if total_bars > 0 else 0.0
        conf_reason = (
            f"aligned {aligned}/{total_bars} bars across "
            f"{len(macro_symbols)} macro symbols"
        )

        snapshot = CorrelationSnapshot(
            snapshot_id=f"corr_{instrument}_{period}",
            instrument=instrument,
            period=period,
            pairs=tuple(pairs),
            total_instrument_bars=total_bars,
            aligned_dates=aligned,
            missing_alignment=missing,
            source_refs=tuple(evidence),
            confidence=ConfidenceScore(
                value=round(conf_value, 6),
                reason=conf_reason,
            ),
        )

        _write_snapshot(self._data_dir, snapshot)

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            version=self.version,
            input_summary=(
                f"correlation {instrument} {period} "
                f"macros={','.join(macro_symbols)} lags={lags}"
            ),
            output=snapshot,
            evidence=tuple(evidence),
            confidence=snapshot.confidence,
            created_at=created_at,
        )
