"""Dashboard router — lab status and activity feed."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

ROOT = Path(__file__).parent.parent.parent.parent

router = APIRouter()


def _reports_dir() -> Path:
    return ROOT / "reports"


def _vb_reports_dir() -> Path:
    return ROOT / "reports" / "visual_backtest"


def _data_dir() -> Path:
    return ROOT / "data"


def _legacy_reports() -> list[dict]:
    """Return cached legacy research session reports (60s TTL)."""
    from services.cache.reports_cache import ReportsCache
    return ReportsCache.get_instance(_reports_dir()).get_legacy_reports()


def _vb_reports() -> list[dict]:
    """Read all visual backtest reports."""
    results = []
    for path in (_vb_reports_dir()).glob("**/report.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_mtime"] = os.path.getmtime(path)
            results.append(data)
        except Exception:
            pass
    results.sort(key=lambda x: x["_mtime"], reverse=True)
    return results


def _count_hypotheses() -> int:
    try:
        from services.research.hypothesis_registry import HypothesisTemplateRegistry
        return len(HypothesisTemplateRegistry().list())
    except Exception:
        return len(list((ROOT / "hypotheses").glob("*.yaml")))


def _count_datasets() -> int:
    try:
        manifest = json.loads((ROOT / "data" / "universe" / "manifest_index.json").read_text())
        return manifest.get("total_cells", 0)
    except Exception:
        return len(list((ROOT / "data" / "datasets").iterdir())) if (ROOT / "data" / "datasets").exists() else 0


@router.get("/status")
def get_status():
    legacy = _legacy_reports()
    vb = _vb_reports()

    # Count strategy candidates from legacy findings
    all_findings = []
    for r in legacy:
        all_findings.extend(r.get("findings", []))

    passed = [f for f in all_findings if f.get("outcome") == "PASS"]
    failed = [f for f in all_findings if f.get("outcome") == "FAIL"]

    # Aggregate research runs
    total_windows = sum(f.get("windows_total", 0) for f in all_findings)

    return {
        "lab_version": "v1.10",
        "mode": "operational",
        "status": "active",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypotheses": {
            "registered": _count_hypotheses(),
            "tested": len({f.get("template_id") for f in all_findings if f.get("template_id")}),
            "passed_alpha_gate": len(passed),
            "failed": len(failed),
        },
        "research": {
            "sessions": len(legacy),
            "total_findings": len(all_findings),
            "total_windows": total_windows,
            "visual_backtest_reports": len(vb),
        },
        "datasets": {
            "total": _count_datasets(),
        },
        "candidates": {
            "total": len(passed),
            "approved_for_paper": 0,
        },
        "paper_trading": {
            "enabled": False,
            "positions": 0,
            "capital": 0.0,
            "pnl": 0.0,
        },
        "knowledge_base": {
            "snapshots": len(list((ROOT / "data" / "knowledge" / "snapshots").glob("*.json"))) if (ROOT / "data" / "knowledge" / "snapshots").exists() else 0,
        },
        "research_budget": {
            "total": len(all_findings),
            "used": len(all_findings),
            "remaining": 0,
        },
    }


@router.get("/activity")
def get_activity():
    """Recent lab events ordered by time."""
    events = []

    # From legacy research reports
    for r in _legacy_reports()[:10]:
        summary = r.get("summary", {})
        events.append({
            "id": r.get("report_id", "")[:12],
            "type": "RESEARCH_SESSION",
            "timestamp": r.get("generated_at", ""),
            "title": summary.get("description", "Research Session"),
            "detail": f"{len(r.get('findings', []))} findings",
            "status": "completed",
        })
        for finding in r.get("findings", []):
            events.append({
                "id": finding.get("hypothesis_id", "")[:12],
                "type": "ALPHA_GATE",
                "timestamp": r.get("generated_at", ""),
                "title": f"{finding.get('outcome', '?')} — {finding.get('hypothesis_title', '')}",
                "detail": f"pass_rate={finding.get('pass_rate', 0):.1%} over {finding.get('windows_total', 0)} windows",
                "status": "pass" if finding.get("outcome") == "PASS" else "fail",
            })
        for rec in r.get("recommendations", []):
            events.append({
                "id": rec.get("hypothesis_id", "")[:12],
                "type": rec.get("kind", "DECISION"),
                "timestamp": r.get("generated_at", ""),
                "title": f"Chief Scientist: {rec.get('kind', '?')}",
                "detail": rec.get("rationale", ""),
                "status": "info",
            })

    # From visual backtest reports
    for vb in _vb_reports()[:5]:
        metrics = vb.get("metrics", {})
        events.append({
            "id": vb.get("report_id", "")[:12],
            "type": "VISUAL_BACKTEST",
            "timestamp": vb.get("generated_at", ""),
            "title": f"Visual Backtest: {vb.get('hypothesis_id', '')} | {vb.get('ticker', '')} {vb.get('period', '')}",
            "detail": f"Return={metrics.get('total_return_pct', 0):+.1f}% MaxDD={metrics.get('max_drawdown_pct', 0):.1f}% Trades={metrics.get('num_trades', 0)}",
            "status": "completed",
        })

    # Sort by timestamp descending
    events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return events[:50]
