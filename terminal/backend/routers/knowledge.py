"""Knowledge Map router — builds an interactive graph from existing data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

ROOT = Path(__file__).parent.parent.parent.parent

router = APIRouter()


def _load_regime_data() -> list[dict]:
    regime_dir = ROOT / "data" / "context" / "regime"
    if not regime_dir.exists():
        return []
    results = []
    for path in regime_dir.glob("*.json"):
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return results


def _load_hypotheses() -> list[dict]:
    try:
        from services.research.hypothesis_registry import HypothesisTemplateRegistry
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "category": getattr(t, "category", "momentum"),
                "priority": getattr(t, "priority", "P2"),
            }
            for t in HypothesisTemplateRegistry().list()
        ]
    except Exception:
        return []


def _load_vb_reports() -> list[dict]:
    vb_dir = ROOT / "reports" / "visual_backtest"
    if not vb_dir.exists():
        return []
    results = []
    for path in vb_dir.glob("**/report.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            results.append(data)
        except Exception:
            pass
    return results


@router.get("/graph")
def get_knowledge_graph():
    """Build a knowledge graph: Hypotheses → Market Effects → Instruments → Evidence."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    hypotheses = _load_hypotheses()
    regimes = _load_regime_data()
    reports = _load_vb_reports()

    # Category colors
    category_color = {
        "momentum": "#58a6ff",
        "mean_reversion": "#3fb950",
        "trend": "#f0883e",
        "volatility": "#bc8cff",
        "regime": "#ff7b72",
        "evidence": "#79c0ff",
        "instrument": "#d2a679",
    }

    # Root node
    nodes.append({
        "id": "lab",
        "label": "MOEX AI LAB",
        "type": "root",
        "color": "#f0883e",
        "size": 40,
        "description": "Research Laboratory",
    })

    # Category nodes
    categories = {}
    for h in hypotheses:
        cat = h.get("category", "momentum")
        if cat not in categories:
            categories[cat] = cat
            nodes.append({
                "id": f"cat_{cat}",
                "label": cat.replace("_", " ").title(),
                "type": "category",
                "color": category_color.get(cat, "#8b949e"),
                "size": 25,
                "description": f"{cat} strategies",
            })
            edges.append({
                "source": "lab",
                "target": f"cat_{cat}",
                "label": "contains",
                "weight": 2,
            })

    # Hypothesis nodes
    for h in hypotheses:
        cat = h.get("category", "momentum")
        nodes.append({
            "id": h["template_id"],
            "label": h["name"][:30],
            "type": "hypothesis",
            "color": category_color.get(cat, "#8b949e"),
            "size": 18,
            "description": h["name"],
            "priority": h.get("priority", "P2"),
        })
        edges.append({
            "source": f"cat_{cat}",
            "target": h["template_id"],
            "label": "tests",
            "weight": 1,
        })

    # Instrument nodes from regime data
    instruments = {}
    for r in regimes:
        inst = r.get("instrument", "")
        period = str(r.get("period", ""))
        key = f"{inst}_{period}"
        if inst and key not in instruments:
            instruments[key] = True
            nodes.append({
                "id": f"inst_{key}",
                "label": f"{inst}\n{period}",
                "type": "instrument",
                "color": category_color["instrument"],
                "size": 14,
                "description": f"{inst} {period}",
            })
            # Regime segments
            for seg in r.get("segments", [])[:2]:
                regime_key = f"regime_{seg.get('label', '')}"
                if not any(n["id"] == regime_key for n in nodes):
                    nodes.append({
                        "id": regime_key,
                        "label": seg.get("label", ""),
                        "type": "regime",
                        "color": "#ff7b72" if "DOWN" in seg.get("label", "") else "#3fb950",
                        "size": 10,
                        "description": f"Regime: {seg.get('label')}",
                    })
                edges.append({
                    "source": f"inst_{key}",
                    "target": regime_key,
                    "label": "exhibits",
                    "weight": 1,
                })

    # Evidence nodes from visual backtest reports
    for rep in reports:
        ticker = rep.get("ticker", "")
        period = rep.get("period", "")
        h_id = rep.get("hypothesis_id", "")
        metrics = rep.get("metrics", {})
        ret = metrics.get("total_return_pct", 0)

        evidence_id = f"evidence_{rep.get('report_id', '')[:8]}"
        nodes.append({
            "id": evidence_id,
            "label": f"Evidence\n{ticker} {period}\n{ret:+.1f}%",
            "type": "evidence",
            "color": "#3fb950" if ret > 0 else "#f85149",
            "size": 12,
            "description": f"{ticker} {period}: Return={ret:+.1f}% WinRate={metrics.get('win_rate',0)*100:.0f}%",
        })

        # Connect hypothesis → evidence
        if h_id:
            edges.append({
                "source": h_id,
                "target": evidence_id,
                "label": "validated on",
                "weight": 2,
            })

        # Connect instrument → evidence
        inst_key = f"inst_{ticker}_{period}"
        if any(n["id"] == inst_key for n in nodes):
            edges.append({
                "source": inst_key,
                "target": evidence_id,
                "label": "produced",
                "weight": 1,
            })

    return {"nodes": nodes, "edges": edges}


@router.get("/snapshots")
def get_snapshots():
    snapshots = []
    snap_dir = ROOT / "data" / "knowledge" / "snapshots"
    if snap_dir.exists():
        for path in snap_dir.glob("*.json"):
            try:
                snapshots.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass
    return snapshots
