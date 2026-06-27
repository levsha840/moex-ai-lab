"""Universe Builder — MOEX AI LAB Operational Infrastructure.

Prepares OHLCV datasets for all Core Universe cells:
  Cell = Instrument x Period x Timeframe
  28 instruments x 7 periods x 3 timeframes = 588 target cells.

Strategy (efficient — one API fetch per instrument x period):
  1. For each instrument x period, fetch 1H data via MarketAgent.
  2. Derive 4H and 1D from the 1H CSV — no extra API calls.
  3. Write manifest_index.json with coverage stats.

Resume: safe to run multiple times — already-complete cells are skipped.

Usage:
    python scripts/build_universe.py [--tier P1] [--period 2023] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agents.data.market import MarketAgent

DATA_DIR = ROOT / "data"
UNIVERSE_DIR = DATA_DIR / "universe"
CONFIG_PATH = ROOT / "config" / "research_universe.json"
BUDGET_PATH = ROOT / "config" / "research_budget.json"

SESSION = "main"


# ---------------------------------------------------------------------------
# Config loaders
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_budget() -> dict:
    with open(BUDGET_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CSV resampling helpers (local — no agent import needed)
# ---------------------------------------------------------------------------

def _read_ohlcv(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append({
                "ts":     row["datetime"],
                "open":   float(row["open"]),
                "high":   float(row["high"]),
                "low":    float(row["low"]),
                "close":  float(row["close"]),
                "volume": int(float(row["volume"])),
            })
    return rows


def _resample_4h(candles: list[dict]) -> list[dict]:
    result = []
    for i in range(0, len(candles), 4):
        chunk = candles[i:i + 4]
        if not chunk:
            break
        result.append({
            "ts":     chunk[0]["ts"],
            "open":   chunk[0]["open"],
            "high":   max(c["high"] for c in chunk),
            "low":    min(c["low"] for c in chunk),
            "close":  chunk[-1]["close"],
            "volume": sum(c["volume"] for c in chunk),
        })
    return result


def _resample_1d(candles: list[dict]) -> list[dict]:
    by_date: dict[str, list[dict]] = OrderedDict()
    for c in candles:
        by_date.setdefault(c["ts"][:10], []).append(c)
    result = []
    for date, bars in by_date.items():
        result.append({
            "ts":     f"{date} 00:00:00",
            "open":   bars[0]["open"],
            "high":   max(b["high"] for b in bars),
            "low":    min(b["low"] for b in bars),
            "close":  bars[-1]["close"],
            "volume": sum(b["volume"] for b in bars),
        })
    return result


def _write_derived_dataset(
    ticker: str,
    timeframe: str,
    year: str,
    candles: list[dict],
) -> dict:
    dataset_id = f"{ticker.lower()}_{timeframe}_{year}_{SESSION}"
    dataset_dir = DATA_DIR / "datasets" / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)

    ohlcv_path = dataset_dir / "ohlcv.csv"
    with open(ohlcv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["datetime", "open", "high", "low", "close", "volume"])
        for c in candles:
            writer.writerow([c["ts"], c["open"], c["high"], c["low"], c["close"], c["volume"]])

    date_from = candles[0]["ts"][:10] if candles else ""
    date_to = candles[-1]["ts"][:10] if candles else ""

    meta = {
        "dataset_id":    dataset_id,
        "ticker":        ticker,
        "timeframe":     timeframe,
        "session_filter": SESSION,
        "source":        "MOEX ISS API (derived via build_universe.py)",
        "bar_count":     len(candles),
        "date_from":     date_from,
        "date_to":       date_to,
        "created_by":    "build_universe.py v1",
    }
    with open(dataset_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return {
        "dataset_id": dataset_id,
        "timeframe":  timeframe,
        "bar_count":  len(candles),
        "date_from":  date_from,
        "date_to":    date_to,
        "status":     "ok" if candles else "empty",
        "source":     "derived",
    }


# ---------------------------------------------------------------------------
# Dataset existence check
# ---------------------------------------------------------------------------

def _dataset_exists(ticker: str, timeframe: str, year: str) -> tuple[bool, int]:
    dataset_id = f"{ticker.lower()}_{timeframe}_{year}_{SESSION}"
    csv_path = DATA_DIR / "datasets" / dataset_id / "ohlcv.csv"
    if not csv_path.exists():
        return False, 0
    try:
        with open(csv_path, encoding="utf-8", newline="") as f:
            bar_count = max(0, sum(1 for _ in f) - 1)
        return bar_count > 0, bar_count
    except Exception:
        return False, 0


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_universe(
    tier_filter: str = "all",
    period_filter: str = "",
    dry_run: bool = False,
) -> dict:
    cfg = _load_config()
    budget = _load_budget()
    delay = budget["resource_limits"]["moex_request_delay_sec"]

    instruments = cfg["instruments"]
    if tier_filter != "all":
        instruments = [i for i in instruments if i["priority"] == tier_filter]

    periods = cfg["periods"]
    skip_flags = set(budget["scheduling"]["skip_flagged_periods"])
    periods = [p for p in periods if not set(p["flags"]) & skip_flags]
    if period_filter:
        periods = [p for p in periods if p["year"] == period_filter]

    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    agent = MarketAgent(data_dir=DATA_DIR)

    total_cells = len(instruments) * len(periods) * 3  # 3 timeframes
    fetched = 0
    derived = 0
    skipped = 0
    failed = 0
    cells_log = []

    print(f"[build_universe] Universe: {len(instruments)} instruments x {len(periods)} periods x 3 TF = {total_cells} cells")
    print(f"[build_universe] Tier filter: {tier_filter} | Period filter: {period_filter or 'all'} | Dry run: {dry_run}")
    print()

    for inst in instruments:
        ticker = inst["ticker"]
        for period in periods:
            year = period["year"]
            date_from = f"{year}-01-01"
            date_to   = f"{year}-12-31"

            # --- Check 1H ---
            exists_1h, bars_1h = _dataset_exists(ticker, "1h", year)

            if exists_1h:
                print(f"  [SKIP]  {ticker} {year} 1h ({bars_1h} bars already present)")
                skipped += 1
                cells_log.append({
                    "ticker": ticker, "period": year, "timeframe": "1h",
                    "dataset_id": f"{ticker.lower()}_1h_{year}_{SESSION}",
                    "status": "skipped", "bar_count": bars_1h,
                    "date_from": "", "date_to": "", "source": "existing",
                })
                raw_1h = None  # load below if needed for derivation
            else:
                if dry_run:
                    print(f"  [DRYRUN] {ticker} {year} 1h — would fetch from MOEX ISS")
                    cells_log.append({
                        "ticker": ticker, "period": year, "timeframe": "1h",
                        "dataset_id": f"{ticker.lower()}_1h_{year}_{SESSION}",
                        "status": "dry_run", "bar_count": 0,
                        "date_from": date_from, "date_to": date_to, "source": "api",
                    })
                    raw_1h = None
                else:
                    try:
                        time.sleep(delay)
                        result = agent.run(
                            ticker=ticker, timeframe="1h",
                            date_from=date_from, date_to=date_to,
                        )
                        manifest = result.output
                        print(f"  [FETCH] {ticker} {year} 1h — {manifest.bar_count} bars")
                        fetched += 1
                        exists_1h = manifest.bar_count > 0
                        bars_1h = manifest.bar_count
                        cells_log.append({
                            "ticker": ticker, "period": year, "timeframe": "1h",
                            "dataset_id": manifest.dataset_id,
                            "status": "ok" if exists_1h else "empty",
                            "bar_count": bars_1h,
                            "date_from": manifest.date_from,
                            "date_to": manifest.date_to,
                            "source": "api",
                        })
                        raw_1h = None  # will load from disk below
                    except Exception as exc:
                        print(f"  [FAIL]  {ticker} {year} 1h — {exc}")
                        failed += 1
                        cells_log.append({
                            "ticker": ticker, "period": year, "timeframe": "1h",
                            "dataset_id": f"{ticker.lower()}_1h_{year}_{SESSION}",
                            "status": "failed", "bar_count": 0,
                            "date_from": "", "date_to": "",
                            "source": "api", "error": str(exc),
                        })
                        # Skip 4H and 1D if 1H failed
                        for tf in ("4h", "1d"):
                            cells_log.append({
                                "ticker": ticker, "period": year, "timeframe": tf,
                                "dataset_id": f"{ticker.lower()}_{tf}_{year}_{SESSION}",
                                "status": "skipped_no_1h", "bar_count": 0,
                                "date_from": "", "date_to": "", "source": "derived",
                            })
                        continue

            # --- Derive 4H and 1D from 1H if 1H data is on disk ---
            if not exists_1h:
                for tf in ("4h", "1d"):
                    cells_log.append({
                        "ticker": ticker, "period": year, "timeframe": tf,
                        "dataset_id": f"{ticker.lower()}_{tf}_{year}_{SESSION}",
                        "status": "skipped_empty_1h", "bar_count": 0,
                        "date_from": "", "date_to": "", "source": "derived",
                    })
                continue

            for tf, label in (("4h", "4H"), ("1d", "1D")):
                exists_tf, bars_tf = _dataset_exists(ticker, tf, year)
                if exists_tf:
                    print(f"  [SKIP]  {ticker} {year} {tf} ({bars_tf} bars already present)")
                    skipped += 1
                    cells_log.append({
                        "ticker": ticker, "period": year, "timeframe": tf,
                        "dataset_id": f"{ticker.lower()}_{tf}_{year}_{SESSION}",
                        "status": "skipped", "bar_count": bars_tf,
                        "date_from": "", "date_to": "", "source": "existing",
                    })
                    continue

                if dry_run:
                    print(f"  [DRYRUN] {ticker} {year} {tf} — would derive from 1H")
                    cells_log.append({
                        "ticker": ticker, "period": year, "timeframe": tf,
                        "dataset_id": f"{ticker.lower()}_{tf}_{year}_{SESSION}",
                        "status": "dry_run", "bar_count": 0,
                        "date_from": "", "date_to": "", "source": "derived",
                    })
                    continue

                try:
                    # Load 1H candles from disk (once, cache in raw_1h)
                    if raw_1h is None:
                        csv_1h = DATA_DIR / "datasets" / f"{ticker.lower()}_1h_{year}_{SESSION}" / "ohlcv.csv"
                        raw_1h = _read_ohlcv(csv_1h)

                    resampled = _resample_4h(raw_1h) if tf == "4h" else _resample_1d(raw_1h)
                    cell_meta = _write_derived_dataset(ticker, tf, year, resampled)
                    print(f"  [DERIVE] {ticker} {year} {tf} — {cell_meta['bar_count']} bars from 1H")
                    derived += 1
                    cells_log.append({
                        "ticker": ticker, "period": year, "timeframe": tf,
                        **cell_meta,
                    })
                except Exception as exc:
                    print(f"  [FAIL]  {ticker} {year} {tf} derive — {exc}")
                    failed += 1
                    cells_log.append({
                        "ticker": ticker, "period": year, "timeframe": tf,
                        "dataset_id": f"{ticker.lower()}_{tf}_{year}_{SESSION}",
                        "status": "failed", "bar_count": 0,
                        "date_from": "", "date_to": "",
                        "source": "derived", "error": str(exc),
                    })

    # --- Write manifest index ---
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tier_filter":  tier_filter,
        "period_filter": period_filter or "all",
        "dry_run":      dry_run,
        "total_cells":  total_cells,
        "fetched":      fetched,
        "derived":      derived,
        "skipped":      skipped,
        "failed":       failed,
        "complete":     len([c for c in cells_log if c["status"] in ("ok", "skipped")]),
        "cells":        cells_log,
    }

    manifest_path = UNIVERSE_DIR / "manifest_index.json"
    if not dry_run:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n[build_universe] Manifest written: {manifest_path}")

    print("\n=== UNIVERSE BUILD SUMMARY ===")
    print(f"  Total cells:  {total_cells}")
    print(f"  Fetched (API): {fetched}")
    print(f"  Derived (1H):  {derived}")
    print(f"  Skipped (exists): {skipped}")
    print(f"  Failed:        {failed}")
    ok_count = len([c for c in cells_log if c["status"] in ("ok", "skipped")])
    print(f"  Coverage:      {ok_count}/{total_cells} ({100*ok_count//total_cells if total_cells else 0}%)")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build MOEX AI LAB Research Universe datasets")
    parser.add_argument("--tier",   default="all",  help="Filter by tier: P1, P2, P3, or all")
    parser.add_argument("--period", default="",     help="Filter to single year, e.g. 2023")
    parser.add_argument("--dry-run", action="store_true", help="Check without fetching")
    args = parser.parse_args()

    build_universe(
        tier_filter=args.tier,
        period_filter=args.period,
        dry_run=args.dry_run,
    )
