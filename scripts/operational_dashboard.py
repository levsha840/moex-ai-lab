"""Operational Dashboard — MOEX AI LAB.

Generates docs/OPERATIONAL_DASHBOARD.md by reading:
  - data/universe/manifest_index.json     (dataset coverage)
  - research_programs/waves/schedule.json (wave plan)
  - research_programs/decisions/*.json    (ChiefScientist decisions)
  - knowledge/snapshots/*.json            (KnowledgeBase facts)
  - reports/**/                           (Research Service run counts)
  - config/research_universe.json         (sector map)

Does NOT run any experiments.
Does NOT modify Research Service, agents, or models.

Usage:
    python scripts/operational_dashboard.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DATA_DIR      = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"
DECISIONS_DIR = ROOT / "research_programs" / "decisions"
REPORTS_DIR   = ROOT / "reports"
WAVES_DIR     = ROOT / "research_programs" / "waves"
CONFIG_PATH   = ROOT / "config" / "research_universe.json"
DASHBOARD_OUT = ROOT / "docs" / "OPERATIONAL_DASHBOARD.md"


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def _load_universe_cfg() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_manifest() -> dict:
    path = DATA_DIR / "universe" / "manifest_index.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_schedule() -> dict:
    path = WAVES_DIR / "schedule.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_decisions() -> list[dict]:
    if not DECISIONS_DIR.exists():
        return []
    decisions = []
    for p in sorted(DECISIONS_DIR.glob("*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                decisions.append(json.load(f))
        except Exception:
            pass
    return decisions


def _count_reports() -> int:
    if not REPORTS_DIR.exists():
        return 0
    return sum(1 for p in REPORTS_DIR.rglob("session_report*.json"))


def _load_kb_snapshots() -> list[dict]:
    snaps_dir = KNOWLEDGE_DIR / "snapshots"
    if not snaps_dir.exists():
        return []
    snapshots = []
    for p in sorted(snaps_dir.glob("*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                snapshots.append(json.load(f))
        except Exception:
            pass
    return snapshots


# ---------------------------------------------------------------------------
# Stats collectors
# ---------------------------------------------------------------------------

def _dataset_stats(manifest: dict, cfg: dict) -> dict:
    cells = manifest.get("cells", [])
    total = len(cells)
    ok    = sum(1 for c in cells if c.get("status") in ("ok", "skipped"))

    by_timeframe: dict[str, int] = {}
    by_period: dict[str, int] = {}
    by_sector: dict[str, int] = {}

    ticker_to_sector = {i["ticker"]: i["sector"] for i in cfg.get("instruments", [])}

    for c in cells:
        if c.get("status") not in ("ok", "skipped"):
            continue
        tf = c.get("timeframe", "?")
        yr = c.get("period", "?")
        sec = ticker_to_sector.get(c.get("ticker", ""), "Unknown")
        by_timeframe[tf]  = by_timeframe.get(tf, 0) + 1
        by_period[yr]     = by_period.get(yr, 0) + 1
        by_sector[sec]    = by_sector.get(sec, 0) + 1

    return {
        "total_cells": total,
        "complete":    ok,
        "pct":         100 * ok // total if total else 0,
        "by_timeframe": by_timeframe,
        "by_period":    by_period,
        "by_sector":    by_sector,
        "generated_at": manifest.get("generated_at", ""),
    }


def _decision_stats(decisions: list[dict]) -> dict:
    by_type: dict[str, int] = {}
    by_hypothesis: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    archived: set = set()

    for d in decisions:
        dt = d.get("decision_type", "UNKNOWN")
        hy = d.get("hypothesis_id", "")
        pr = d.get("priority", "?")
        by_type[dt]  = by_type.get(dt, 0) + 1
        by_priority[pr] = by_priority.get(pr, 0) + 1
        if hy:
            by_hypothesis[hy] = by_hypothesis.get(hy, 0) + 1
        if dt == "ARCHIVE_HYPOTHESIS" and hy:
            archived.add(hy)

    return {
        "total":        len(decisions),
        "by_type":      by_type,
        "by_priority":  by_priority,
        "by_hypothesis": by_hypothesis,
        "archived_count": len(archived),
        "archived_ids":   sorted(archived),
    }


def _kb_stats(snapshots: list[dict]) -> dict:
    if not snapshots:
        return {
            "total_snapshots": 0, "total_facts": 0, "total_patterns": 0,
            "total_connections": 0, "total_contradictions": 0,
            "by_hypothesis": {}, "by_regime": {}, "by_instrument": {},
        }

    # Use the most recent snapshot
    latest = snapshots[-1]
    facts        = latest.get("facts", [])
    patterns     = latest.get("patterns", [])
    connections  = latest.get("connections", [])
    contrad      = latest.get("contradictions", [])

    by_hyp: dict[str, int] = {}
    by_regime: dict[str, int] = {}
    by_inst: dict[str, int] = {}

    for f in facts:
        h  = f.get("hypothesis_id", "")
        r  = f.get("regime", "") or "no_regime"
        i  = f.get("instrument", "")
        if h:  by_hyp[h]  = by_hyp.get(h, 0) + 1
        if r:  by_regime[r] = by_regime.get(r, 0) + 1
        if i:  by_inst[i]   = by_inst.get(i, 0) + 1

    return {
        "total_snapshots":   len(snapshots),
        "total_facts":       len(facts),
        "total_patterns":    len(patterns),
        "total_connections": len(connections),
        "total_contradictions": len(contrad),
        "by_hypothesis": by_hyp,
        "by_regime":     by_regime,
        "by_instrument": by_inst,
    }


def _wave_stats(schedule: dict) -> dict:
    waves = schedule.get("waves", [])
    if not waves:
        return {}
    return {
        "total_waves":     len(waves),
        "total_campaigns": schedule.get("total_campaigns", 0),
        "ready_campaigns": schedule.get("ready_campaigns", 0),
        "blocked":         schedule.get("blocked", 0),
        "waves":           waves,
    }


# ---------------------------------------------------------------------------
# Dashboard renderer
# ---------------------------------------------------------------------------

def _fmt_table(headers: list[str], rows: list[list]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    sep  = "| " + " | ".join("-" * w for w in widths) + " |"
    head = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    lines = [head, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)) + " |")
    return "\n".join(lines)


def generate_dashboard() -> Path:
    cfg      = _load_universe_cfg()
    manifest = _load_manifest()
    schedule = _load_schedule()
    decisions = _load_decisions()
    snapshots = _load_kb_snapshots()
    rs_runs   = _count_reports()

    ds   = _dataset_stats(manifest, cfg)
    dec  = _decision_stats(decisions)
    kb   = _kb_stats(snapshots)
    wav  = _wave_stats(schedule)

    now = datetime.now().isoformat(timespec="seconds")

    lines = [
        "# OPERATIONAL DASHBOARD — MOEX AI LAB",
        "",
        f"> Generated: {now}",
        f"> Era: Research Organization Era",
        f"> Baseline: `v0.9-intelligence-alpha`",
        "",
        "---",
        "",
        "## 1. Research Progress",
        "",
    ]

    # Top-level metrics
    lines += [
        _fmt_table(
            ["Metric", "Value"],
            [
                ["Research Service runs",      str(rs_runs)],
                ["ChiefScientist decisions",    str(dec["total"])],
                ["Knowledge facts",             str(kb["total_facts"])],
                ["Knowledge patterns",          str(kb["total_patterns"])],
                ["Knowledge connections",       str(kb["total_connections"])],
                ["Contradictions detected",     str(kb["total_contradictions"])],
                ["Hypotheses archived",         str(dec["archived_count"])],
                ["KB snapshots (cumulative)",   str(kb["total_snapshots"])],
            ]
        ),
        "",
    ]

    # Hypothesis breakdown
    lines += ["---", "", "## 2. Hypothesis Status", ""]
    if kb["by_hypothesis"]:
        hyp_rows = [[h, str(v), "active" if h not in dec.get("archived_ids", []) else "ARCHIVED"]
                    for h, v in sorted(kb["by_hypothesis"].items(), key=lambda x: -x[1])]
        lines += [_fmt_table(["Hypothesis ID", "Facts", "Status"], hyp_rows), ""]
    else:
        lines += ["> No hypothesis data yet. Run research campaigns to accumulate facts.", ""]

    # Decision distribution
    lines += ["---", "", "## 3. Decision Distribution", ""]
    if dec["by_type"]:
        dec_rows = [[dt, str(cnt)] for dt, cnt in sorted(dec["by_type"].items())]
        lines += [_fmt_table(["Decision Type", "Count"], dec_rows), ""]
        pri_rows = [[pr, str(cnt)] for pr, cnt in sorted(dec["by_priority"].items())]
        lines += ["**By Priority:**", "", _fmt_table(["Priority", "Count"], pri_rows), ""]
    else:
        lines += ["> No decisions recorded yet.", ""]

    # KB by regime
    lines += ["---", "", "## 4. Knowledge Base — Regime Coverage", ""]
    if kb["by_regime"]:
        reg_rows = [[r, str(v)] for r, v in sorted(kb["by_regime"].items(), key=lambda x: -x[1])]
        lines += [_fmt_table(["Regime", "Facts"], reg_rows), ""]
    else:
        lines += ["> No regime-labelled facts yet.", ""]

    # KB by instrument
    lines += ["---", "", "## 5. Knowledge Base — Instrument Coverage", ""]
    if kb["by_instrument"]:
        inst_rows = [[i, str(v)] for i, v in sorted(kb["by_instrument"].items(), key=lambda x: -x[1])]
        lines += [_fmt_table(["Instrument", "Facts"], inst_rows), ""]
    else:
        lines += ["> No per-instrument facts yet.", ""]

    # Dataset coverage
    lines += ["---", "", "## 6. Dataset Coverage", ""]
    if ds["total_cells"] > 0:
        lines += [
            f"**Total cells:** {ds['complete']} / {ds['total_cells']} ({ds['pct']}%)",
            f"**Last built:** {ds['generated_at']}",
            "",
            "**By timeframe:**",
            "",
        ]
        if ds["by_timeframe"]:
            tf_rows = [[tf, str(cnt)] for tf, cnt in sorted(ds["by_timeframe"].items())]
            lines += [_fmt_table(["Timeframe", "Datasets"], tf_rows), ""]
        lines += ["**By period:**", ""]
        if ds["by_period"]:
            per_rows = [[yr, str(cnt)] for yr, cnt in sorted(ds["by_period"].items())]
            lines += [_fmt_table(["Period", "Datasets"], per_rows), ""]
        lines += ["**By sector:**", ""]
        if ds["by_sector"]:
            sec_rows = [[s, str(cnt)] for s, cnt in sorted(ds["by_sector"].items())]
            lines += [_fmt_table(["Sector", "Datasets"], sec_rows), ""]
    else:
        lines += [
            "> No dataset manifest found.",
            "> Run: `python scripts/build_universe.py --dry-run` to assess coverage.",
            "",
        ]

    # Wave schedule
    lines += ["---", "", "## 7. Research Wave Schedule", ""]
    if wav.get("waves"):
        lines += [
            f"**Total campaigns:** {wav['total_campaigns']} | **Ready:** {wav['ready_campaigns']} | **Blocked:** {wav['blocked']}",
            "",
        ]
        wave_rows = []
        for w in wav["waves"]:
            pct = 100 * w["ready_campaigns"] // w["total_campaigns"] if w["total_campaigns"] else 0
            wave_rows.append([w["wave_id"], w["name"], str(w["ready_campaigns"]), str(w["total_campaigns"]), f"{pct}%", w["status"].upper()])
        lines += [_fmt_table(["Wave", "Name", "Ready", "Total", "Pct", "Status"], wave_rows), ""]
        lines += [
            "To unblock campaigns, run:",
            "```",
            "python scripts/build_universe.py --tier P1 --period 2023",
            "```",
            "",
        ]
    else:
        lines += [
            "> No schedule found.",
            "> Run: `python scripts/campaign_scheduler.py` to generate wave plans.",
            "",
        ]

    # Operational readiness
    lines += ["---", "", "## 8. Operational Readiness", ""]
    readiness = []
    readiness.append(("Research Universe defined (28 instruments)", True))
    readiness.append(("Config files present", CONFIG_PATH.exists()))
    readiness.append(("Dataset manifest exists", bool(manifest)))
    readiness.append(("Wave schedule exists", bool(schedule)))
    readiness.append(("KB snapshots present", kb["total_snapshots"] > 0))
    readiness.append(("Research decisions logged", dec["total"] > 0))
    readiness.append(("RS runs completed", rs_runs > 0))

    for label, ok in readiness:
        icon = "[OK]  " if ok else "[WAIT]"
        lines.append(f"- {icon} {label}")

    score = sum(1 for _, ok in readiness if ok)
    lines += [
        "",
        f"**Readiness score: {score}/{len(readiness)}**",
        "",
        "---",
        "",
        "*Generated by `scripts/operational_dashboard.py`*",
        "*Data sources: manifest_index.json, schedule.json, decisions/*.json, knowledge/snapshots/*"
    ]

    DASHBOARD_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[operational_dashboard] Dashboard written: {DASHBOARD_OUT}")
    print(f"  RS runs: {rs_runs} | Decisions: {dec['total']} | KB facts: {kb['total_facts']}")
    print(f"  Datasets: {ds['complete']}/{ds['total_cells']} | Readiness: {score}/{len(readiness)}")

    return DASHBOARD_OUT


if __name__ == "__main__":
    generate_dashboard()
