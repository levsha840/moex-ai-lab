"""Campaign Scheduler — MOEX AI LAB Operational Infrastructure.

Generates a structured research wave plan from the Research Universe.
Writes wave plan JSON files to research_programs/waves/.
Does NOT run any experiments.

Wave structure (sector-based, from docs/60_RESEARCH_UNIVERSE.md):
  Wave 1: Banks           (P1 instruments, priority periods)
  Wave 2: Oil & Gas       (P1 instruments, priority periods)
  Wave 3: Metals & Mining (P1 instruments, priority periods)
  Wave 4: Retail          (P1+P2, priority periods)
  Wave 5: Energy+Telecom  (P2 instruments)
  Wave 6: Tech+Transport  (P2+P3 instruments)

Usage:
    python scripts/campaign_scheduler.py [--period 2023] [--status]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

CONFIG_PATH  = ROOT / "config" / "research_universe.json"
BUDGET_PATH  = ROOT / "config" / "research_budget.json"
WAVES_DIR    = ROOT / "research_programs" / "waves"
UNIVERSE_DIR = ROOT / "data" / "universe"

DEFAULT_HYPOTHESIS_ID = "H-ADX-CONTINUATION"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_budget() -> dict:
    with open(BUDGET_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Dataset availability check
# ---------------------------------------------------------------------------

def _available_datasets(ticker: str, periods: list[str], timeframe: str) -> list[str]:
    session = "main"
    available = []
    for year in periods:
        dataset_id = f"{ticker.lower()}_{timeframe}_{year}_{session}"
        csv_path = ROOT / "data" / "datasets" / dataset_id / "ohlcv.csv"
        if csv_path.exists():
            available.append(year)
    return available


# ---------------------------------------------------------------------------
# Wave plan builder
# ---------------------------------------------------------------------------

def _build_wave(wave_cfg: dict, budget: dict, period_filter: str = "") -> dict:
    tf = wave_cfg["timeframe"]
    priority_periods = wave_cfg["priority_periods"]
    if period_filter:
        priority_periods = [p for p in priority_periods if p == period_filter]

    skip_flags = set(budget["scheduling"]["skip_flagged_periods"])
    all_periods = _load_config()["periods"]
    valid_years = {p["year"] for p in all_periods if not set(p["flags"]) & skip_flags}

    campaigns = []
    for ticker in wave_cfg["tickers"]:
        # Check which periods have data
        available = _available_datasets(ticker, priority_periods, tf)
        all_available = _available_datasets(ticker, list(valid_years), tf)

        for year in priority_periods:
            status = "ready" if year in available else "needs_data"
            campaign_id = f"{wave_cfg['wave_id']}_{ticker.lower()}_{year}"
            campaigns.append({
                "campaign_id":       campaign_id,
                "ticker":            ticker,
                "period":            year,
                "timeframe":         tf,
                "dataset_status":    status,
                "hypothesis_id":     DEFAULT_HYPOTHESIS_ID,
                "status":            "pending",
                "created_at":        "",
                "completed_at":      "",
                "result_summary":    "",
            })

        # List additional available periods (non-priority)
        extra = [y for y in all_available if y not in priority_periods]
        if extra:
            campaigns[-1]["additional_available_periods"] = extra

    ready = sum(1 for c in campaigns if c["dataset_status"] == "ready")
    total = len(campaigns)

    plan = {
        "wave_id":      wave_cfg["wave_id"],
        "name":         wave_cfg["name"],
        "tickers":      wave_cfg["tickers"],
        "timeframe":    tf,
        "hypothesis_id": DEFAULT_HYPOTHESIS_ID,
        "priority_periods": priority_periods,
        "total_campaigns": total,
        "ready_campaigns": ready,
        "blocked_campaigns": total - ready,
        "status":       "ready" if ready == total else ("partial" if ready > 0 else "blocked"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "campaigns":    campaigns,
    }
    return plan


# ---------------------------------------------------------------------------
# Schedule generator
# ---------------------------------------------------------------------------

def generate_schedule(period_filter: str = "") -> dict:
    cfg    = _load_config()
    budget = _load_budget()
    wave_order = budget["scheduling"]["wave_order"]

    WAVES_DIR.mkdir(parents=True, exist_ok=True)

    waves_by_id = {w["wave_id"]: w for w in cfg["waves"]}
    wave_summaries = []
    total_campaigns = 0
    total_ready = 0

    print("[campaign_scheduler] Generating research wave plans...")
    print()

    for wave_id in wave_order:
        if wave_id not in waves_by_id:
            continue
        wave_cfg = waves_by_id[wave_id]
        plan = _build_wave(wave_cfg, budget, period_filter)

        # Write wave plan file
        plan_path = WAVES_DIR / f"{wave_id}.json"
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)

        ready = plan["ready_campaigns"]
        total = plan["total_campaigns"]
        total_campaigns += total
        total_ready += ready

        status_label = {"ready": "[READY]", "partial": "[PARTIAL]", "blocked": "[BLOCKED]"}
        label = status_label.get(plan["status"], "[?]")
        print(f"  {label} {wave_id}: {plan['name']} — {ready}/{total} campaigns ready")
        for c in plan["campaigns"]:
            ds_label = "[data OK]" if c["dataset_status"] == "ready" else "[NO DATA]"
            print(f"         {ds_label} {c['ticker']} {c['period']} {c['timeframe']}")

        wave_summaries.append({
            "wave_id":         plan["wave_id"],
            "name":            plan["name"],
            "total_campaigns": total,
            "ready_campaigns": ready,
            "status":          plan["status"],
            "plan_file":       str(plan_path),
        })
        print()

    # Write overall schedule
    schedule = {
        "generated_at":    datetime.now().isoformat(timespec="seconds"),
        "period_filter":   period_filter or "all",
        "hypothesis_id":   DEFAULT_HYPOTHESIS_ID,
        "total_campaigns": total_campaigns,
        "ready_campaigns": total_ready,
        "blocked":         total_campaigns - total_ready,
        "waves":           wave_summaries,
    }
    schedule_path = WAVES_DIR / "schedule.json"
    with open(schedule_path, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)

    print("=== SCHEDULE SUMMARY ===")
    print(f"  Total campaigns:  {total_campaigns}")
    print(f"  Ready to run:     {total_ready}")
    print(f"  Blocked (no data): {total_campaigns - total_ready}")
    print(f"  Coverage:         {100*total_ready//total_campaigns if total_campaigns else 0}%")
    print(f"\n  Schedule written: {schedule_path}")
    print("\nTo unblock campaigns, run:")
    print("  python scripts/build_universe.py --tier P1 --period 2023")

    return schedule


# ---------------------------------------------------------------------------
# Status viewer
# ---------------------------------------------------------------------------

def show_status() -> None:
    schedule_path = WAVES_DIR / "schedule.json"
    if not schedule_path.exists():
        print("[campaign_scheduler] No schedule found. Run without --status first.")
        return

    with open(schedule_path, encoding="utf-8") as f:
        schedule = json.load(f)

    print(f"\n=== CAMPAIGN SCHEDULE STATUS (generated {schedule['generated_at']}) ===")
    print(f"Hypothesis: {schedule.get('hypothesis_id', 'N/A')}")
    print(f"Total: {schedule['total_campaigns']} | Ready: {schedule['ready_campaigns']} | Blocked: {schedule['blocked']}")
    print()
    for w in schedule["waves"]:
        pct = 100 * w["ready_campaigns"] // w["total_campaigns"] if w["total_campaigns"] else 0
        print(f"  {w['wave_id']} {w['name']:30s} {w['ready_campaigns']:3d}/{w['total_campaigns']:3d} ({pct:3d}%)  [{w['status'].upper()}]")

    print()
    # Count completed from wave files
    completed = 0
    for w in schedule["waves"]:
        plan_path = Path(w["plan_file"])
        if plan_path.exists():
            with open(plan_path, encoding="utf-8") as f:
                plan = json.load(f)
            done = sum(1 for c in plan.get("campaigns", []) if c.get("status") == "completed")
            if done:
                print(f"  {w['wave_id']}: {done} campaigns completed")
                completed += done
    if completed:
        print(f"\nTotal completed: {completed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate MOEX AI LAB research campaign schedule")
    parser.add_argument("--period", default="", help="Filter to single year, e.g. 2023")
    parser.add_argument("--status", action="store_true", help="Show current schedule status")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        generate_schedule(period_filter=args.period)
