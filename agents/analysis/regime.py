"""RegimeDetectionAgent — Layer 2 Analysis Agent.

Classifies market context across three orthogonal regime dimensions:

    Trend      — TREND_UP | TREND_DOWN | RANGE
    Volatility — LOW_VOL  | NORMAL_VOL | HIGH_VOL
    Risk       — RISK_ON  | RISK_OFF   | NEUTRAL

All rules are deterministic and transparent — no ML, no LLM.

Methodology:
  Trend      linear slope + SMA position over a rolling window
  Volatility realized volatility vs full-period 25th / 75th percentile
  Risk       slope voting across IMOEX, USDRUB, RGBI

Results saved to data/context/regime/{instrument.lower()}_{period}.json.
No trading signals. No predictions. Context analysis only.
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
    EvidenceRef,
    RegimeLabel,
    RegimeSegment,
    RegimeSnapshot,
)

_AGENT_ID = "regime-detection-agent"
_AGENT_TYPE = "ANALYSIS"
_VERSION = "1.0"

DEFAULT_WINDOW = 21                 # ~1 trading month
DEFAULT_MACRO_SYMBOLS: tuple[str, ...] = ("IMOEX", "USDRUB", "RGBI")
_TREND_SLOPE_THRESHOLD = 0.001      # 0.1% per day, normalised by mean price
_ANNUALIZATION = 252.0


# ---------------------------------------------------------------------------
# Source implementations
# ---------------------------------------------------------------------------

class FileRegimeSource:
    """Loads instrument OHLCV and macro CSVs from data_dir."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def load_instrument(self, instrument: str, period: str) -> list[dict]:
        pattern = f"{instrument.lower()}_*{period}*"
        datasets_dir = self._data_dir / "datasets"
        if not datasets_dir.exists():
            return []
        for d in sorted(datasets_dir.glob(pattern)):
            csv_path = d / "ohlcv.csv"
            if csv_path.exists():
                return self._read_ohlcv(csv_path)
        return []

    def _read_ohlcv(self, path: Path) -> list[dict]:
        daily: dict[str, float] = {}
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                ts = row.get("datetime") or row.get("date", "")
                date = str(ts)[:10]
                daily[date] = float(row["close"])
        return [{"date": d, "close": c} for d, c in sorted(daily.items())]

    def load_macro_symbol(self, symbol: str, period: str) -> list[dict]:
        path = self._data_dir / "context" / "macro" / period / f"{symbol}_1d.csv"
        if not path.exists():
            return []
        rows: list[dict] = []
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                rows.append({"date": row["date"], "close": float(row["close"])})
        return sorted(rows, key=lambda r: r["date"])


class FixtureRegimeSource:
    """Pre-baked daily {date, close} data — no file I/O.  Use in tests."""

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
# Pure math helpers (no side effects)
# ---------------------------------------------------------------------------

def _to_daily_series(rows: list[dict]) -> list[tuple[str, float]]:
    return sorted(
        ((r["date"], float(r["close"])) for r in rows),
        key=lambda x: x[0],
    )


def _returns_from_closes(closes: list[float]) -> list[float]:
    """Simple daily returns: r[i] = closes[i+1] / closes[i] - 1."""
    result: list[float] = []
    for i in range(len(closes) - 1):
        if closes[i] != 0.0:
            result.append(closes[i + 1] / closes[i] - 1.0)
    return result


def _linear_slope(values: list[float]) -> float:
    """Ordinary least-squares slope (Δy per step)."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    xm = n / 2.0 - 0.5          # mean of [0, 1, ..., n-1]
    ym = sum(values) / n
    num = sum((x - xm) * (y - ym) for x, y in zip(xs, values))
    den = sum((x - xm) ** 2 for x in xs)
    return num / den if den != 0.0 else 0.0


def _sma(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _realized_vol(returns: list[float], ann: float = _ANNUALIZATION) -> float:
    """Annualised realised volatility (population std × sqrt(ann))."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    return math.sqrt(variance * ann)


def _percentile(values: list[float], p: float) -> float:
    """p ∈ [0, 100]. Linear interpolation between sorted elements."""
    if not values:
        return 0.0
    sv = sorted(values)
    n = len(sv)
    idx = (p / 100.0) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sv[lo] * (1.0 - frac) + sv[hi] * frac


def _rolling_rvs(rets: list[float], window: int) -> list[float]:
    """Rolling realised vol for each position in rets (needs ≥ 2 in window)."""
    rvs: list[float] = []
    for i in range(len(rets)):
        chunk = rets[max(0, i - window + 1): i + 1]
        if len(chunk) >= 2:
            rvs.append(_realized_vol(chunk))
    return rvs


def _segment_dates(dates: list[str], window: int) -> list[tuple[int, int]]:
    """Split date index into non-overlapping [start, end) chunks of size window."""
    segs: list[tuple[int, int]] = []
    i, n = 0, len(dates)
    while i < n:
        segs.append((i, min(i + window, n)))
        i += window
    return segs


# ---------------------------------------------------------------------------
# Classification functions
# ---------------------------------------------------------------------------

def _classify_trend(
    closes: list[float],
    slope_threshold: float = _TREND_SLOPE_THRESHOLD,
) -> tuple[str, float, list[tuple[str, float]]]:
    """Returns (label, confidence, metrics).

    Metrics: slope_normalized, sma_position, mean_price.
    slope_normalized = slope_per_day / mean_price
    sma_position     = (last_close - SMA) / SMA
    """
    if len(closes) < 2:
        return RegimeLabel.RANGE, 0.0, [
            ("slope_normalized", 0.0), ("sma_position", 0.0), ("mean_price", closes[0] if closes else 0.0)
        ]

    mean_price = _sma(closes)
    slope = _linear_slope(closes)
    slope_norm = slope / mean_price if mean_price != 0.0 else 0.0

    sma = mean_price                               # SMA of the window = mean
    position = (closes[-1] - sma) / sma if sma != 0.0 else 0.0

    metrics = [
        ("slope_normalized", round(slope_norm, 8)),
        ("sma_position", round(position, 8)),
        ("mean_price", round(mean_price, 4)),
    ]

    if slope_norm > slope_threshold and position > 0.0:
        label = RegimeLabel.TREND_UP
    elif slope_norm < -slope_threshold and position < 0.0:
        label = RegimeLabel.TREND_DOWN
    else:
        label = RegimeLabel.RANGE

    # Confidence: average of normalised slope strength and SMA-position strength
    slope_strength = min(abs(slope_norm) / (slope_threshold * 3.0), 1.0)
    pos_strength = min(abs(position) / 0.02, 1.0)
    confidence = round((slope_strength + pos_strength) / 2.0, 6)

    return label, confidence, metrics


def _classify_volatility(
    window_rets: list[float],
    p25: float,
    p75: float,
) -> tuple[str, float, list[tuple[str, float]]]:
    """Returns (label, confidence, metrics).

    Compares window realised vol against full-period p25/p75.
    """
    rv = _realized_vol(window_rets)
    metrics = [
        ("realized_vol", round(rv, 6)),
        ("p25", round(p25, 6)),
        ("p75", round(p75, 6)),
    ]

    # Degenerate: no percentile data → NORMAL_VOL
    if p25 == 0.0 and p75 == 0.0:
        return RegimeLabel.NORMAL_VOL, 0.0, metrics

    if rv <= p25:
        label = RegimeLabel.LOW_VOL
        confidence = round(
            max(0.0, min(1.0, (p25 - rv) / (p25 + 1e-10))), 6
        )
    elif rv >= p75:
        label = RegimeLabel.HIGH_VOL
        confidence = round(
            max(0.0, min(1.0, (rv - p75) / (p75 + 1e-10))), 6
        )
    else:
        label = RegimeLabel.NORMAL_VOL
        band = p75 - p25
        dist = min(rv - p25, p75 - rv)
        confidence = round(
            max(0.0, min(1.0, dist * 2.0 / band)) if band > 0.0 else 0.0, 6
        )

    return label, confidence, metrics


def _classify_risk(
    imoex_closes: list[float],
    usdrub_closes: list[float],
    rgbi_closes: Optional[list[float]] = None,
) -> tuple[str, float, list[tuple[str, float]]]:
    """Returns (label, confidence, metrics).

    Voting logic:
        RISK_ON signals:  IMOEX slope > 0, USDRUB slope < 0 (RUB strengthens)
        RISK_OFF signals: IMOEX slope < 0, USDRUB slope > 0 (RUB weakens)

    RGBI adds a third vote if available.
    """
    if not imoex_closes or not usdrub_closes:
        return RegimeLabel.NEUTRAL, 0.0, []

    imoex_mean = _sma(imoex_closes)
    usdrub_mean = _sma(usdrub_closes)
    imoex_slope = _linear_slope(imoex_closes)
    usdrub_slope = _linear_slope(usdrub_closes)

    imoex_norm = imoex_slope / imoex_mean if imoex_mean != 0.0 else 0.0
    usdrub_norm = usdrub_slope / usdrub_mean if usdrub_mean != 0.0 else 0.0

    risk_on_votes = int(imoex_norm > 0.0) + int(usdrub_norm < 0.0)
    risk_off_votes = int(imoex_norm < 0.0) + int(usdrub_norm > 0.0)
    total_signals = 2

    if rgbi_closes and len(rgbi_closes) >= 2:
        rgbi_mean = _sma(rgbi_closes)
        rgbi_slope = _linear_slope(rgbi_closes)
        rgbi_norm = rgbi_slope / rgbi_mean if rgbi_mean != 0.0 else 0.0
        # RGBI rising → risk-on (bonds rallying with equities = RISK_ON)
        # RGBI falling → risk-off
        risk_on_votes += int(rgbi_norm > 0.0)
        risk_off_votes += int(rgbi_norm < 0.0)
        total_signals = 3
    else:
        rgbi_norm = 0.0

    if risk_on_votes > risk_off_votes:
        label = RegimeLabel.RISK_ON
        confidence = round(risk_on_votes / total_signals, 6)
    elif risk_off_votes > risk_on_votes:
        label = RegimeLabel.RISK_OFF
        confidence = round(risk_off_votes / total_signals, 6)
    else:
        label = RegimeLabel.NEUTRAL
        confidence = round(0.5, 6)

    metrics = [
        ("imoex_slope_norm", round(imoex_norm, 8)),
        ("usdrub_slope_norm", round(usdrub_norm, 8)),
        ("rgbi_slope_norm", round(rgbi_norm, 8)),
        ("risk_on_votes", float(risk_on_votes)),
        ("risk_off_votes", float(risk_off_votes)),
    ]
    return label, confidence, metrics


def _closes_in_window(
    series: list[tuple[str, float]],
    date_from: str,
    date_to: str,
) -> list[float]:
    return [c for d, c in series if date_from <= d <= date_to]


def _segment_to_model(
    regime_type: str,
    label: str,
    date_from: str,
    date_to: str,
    confidence: float,
    metrics: list[tuple[str, float]],
    evidence_texts: list[str],
) -> RegimeSegment:
    return RegimeSegment(
        regime_type=regime_type,
        label=label,
        date_from=date_from,
        date_to=date_to,
        confidence=confidence,
        metrics=tuple(metrics),
        evidence=tuple(evidence_texts),
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _write_snapshot(data_dir: Path, snap: RegimeSnapshot) -> Path:
    out_dir = data_dir / "context" / "regime"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{snap.instrument.lower()}_{snap.period}.json"

    def _seg(s: RegimeSegment) -> dict:
        return {
            "regime_type": s.regime_type,
            "label": s.label,
            "date_from": s.date_from,
            "date_to": s.date_to,
            "confidence": s.confidence,
            "metrics": {k: (None if math.isnan(v) else v) for k, v in s.metrics},
            "evidence": list(s.evidence),
        }

    payload = {
        "snapshot_id": snap.snapshot_id,
        "instrument": snap.instrument,
        "period": snap.period,
        "segments": [_seg(s) for s in snap.segments],
        "confidence_value": snap.confidence.value,
        "confidence_reason": snap.confidence.reason,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# RegimeDetectionAgent
# ---------------------------------------------------------------------------

class RegimeDetectionAgent:
    """Layer 2 Analysis Agent — deterministic market regime classification.

    Classifies trend, volatility, and risk regime for each non-overlapping
    time window in the period. Results written to data/context/regime/.

    Inject FixtureRegimeSource for deterministic tests.
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
        self._source = source or FileRegimeSource(data_dir)

    def run(
        self,
        instrument: str,
        period: str,
        macro_symbols: tuple[str, ...] = DEFAULT_MACRO_SYMBOLS,
        window: int = DEFAULT_WINDOW,
        _clock: Optional[Callable[[], datetime]] = None,
    ) -> AgentResult:
        """Classify regime over all non-overlapping windows and return snapshot.

        Parameters
        ----------
        instrument:    ticker string, e.g. "SBER"
        period:        year string, e.g. "2023"
        macro_symbols: which macro series to use for risk regime
        window:        window size in trading days (default 21)
        _clock:        injected clock for determinism in tests
        """
        clock = _clock or datetime.now
        created_at = clock().isoformat(timespec="seconds")

        # --- instrument data ---
        instr_rows = self._source.load_instrument(instrument, period)
        instr_daily = _to_daily_series(instr_rows)
        instr_dates = [d for d, _ in instr_daily]
        instr_closes = [c for _, c in instr_daily]
        instr_rets = _returns_from_closes(instr_closes)

        # --- macro data ---
        macro: dict[str, list[tuple[str, float]]] = {}
        for sym in macro_symbols:
            rows = self._source.load_macro_symbol(sym, period)
            if rows:
                macro[sym] = _to_daily_series(rows)

        # --- volatility percentile reference (all-period rolling RVs) ---
        all_rvs = _rolling_rvs(instr_rets, window)
        p25 = _percentile(all_rvs, 25) if len(all_rvs) >= 2 else 0.0
        p75 = _percentile(all_rvs, 75) if len(all_rvs) >= 2 else 0.0

        # --- segment and classify ---
        date_segs = _segment_dates(instr_dates, window)
        segments: list[RegimeSegment] = []

        for start, end in date_segs:
            date_from = instr_dates[start]
            date_to = instr_dates[end - 1]
            win_closes = instr_closes[start:end]
            win_rets = instr_rets[start: end - 1]  # returns within window

            # Trend
            t_label, t_conf, t_metrics = _classify_trend(win_closes)
            segments.append(_segment_to_model(
                "trend", t_label, date_from, date_to, t_conf, t_metrics,
                [f"slope_norm={t_metrics[0][1]:.5f} sma_pos={t_metrics[1][1]:.5f}"],
            ))

            # Volatility
            v_label, v_conf, v_metrics = _classify_volatility(win_rets, p25, p75)
            segments.append(_segment_to_model(
                "volatility", v_label, date_from, date_to, v_conf, v_metrics,
                [f"rv={v_metrics[0][1]:.4f} p25={p25:.4f} p75={p75:.4f}"],
            ))

            # Risk
            imoex_w = _closes_in_window(macro.get("IMOEX", []), date_from, date_to)
            usdrub_w = _closes_in_window(macro.get("USDRUB", []), date_from, date_to)
            rgbi_w: Optional[list[float]] = (
                _closes_in_window(macro.get("RGBI", []), date_from, date_to) or None
            )
            r_label, r_conf, r_metrics = _classify_risk(imoex_w, usdrub_w, rgbi_w)
            evidence_text = (
                f"imoex={r_metrics[0][1]:.5f} usdrub={r_metrics[1][1]:.5f}"
                if r_metrics else "no macro data"
            )
            segments.append(_segment_to_model(
                "risk", r_label, date_from, date_to, r_conf, r_metrics,
                [evidence_text],
            ))

        # --- evidence refs ---
        evidence: list[EvidenceRef] = [
            EvidenceRef(
                source=f"instrument/{instrument}",
                reference=f"data/datasets/{instrument.lower()}_*_{period}*",
                timestamp=created_at,
            )
        ]
        for sym in macro.keys():
            evidence.append(EvidenceRef(
                source=f"macro/{sym}",
                reference=str(
                    self._data_dir / "context" / "macro" / period / f"{sym}_1d.csv"
                ),
                timestamp=created_at,
            ))

        # --- snapshot confidence: mean of all segment confidences ---
        if segments:
            conf_value = round(
                sum(s.confidence for s in segments) / len(segments), 6
            )
        else:
            conf_value = 0.0

        snapshot = RegimeSnapshot(
            snapshot_id=f"regime_{instrument}_{period}",
            instrument=instrument,
            period=period,
            segments=tuple(segments),
            source_refs=tuple(evidence),
            confidence=ConfidenceScore(
                value=conf_value,
                reason=(
                    f"{len(date_segs)} windows × 3 regime types "
                    f"= {len(segments)} segments"
                ),
            ),
        )

        _write_snapshot(self._data_dir, snapshot)

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            version=self.version,
            input_summary=(
                f"regime {instrument} {period} window={window} "
                f"macros={','.join(macro_symbols)}"
            ),
            output=snapshot,
            evidence=tuple(evidence),
            confidence=snapshot.confidence,
            created_at=created_at,
        )
