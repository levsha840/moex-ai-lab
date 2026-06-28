"""Strategy Vault router — all research findings as strategy candidates."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

ROOT = Path(__file__).parent.parent.parent.parent

router = APIRouter()


def _all_findings() -> list[dict]:
    """Collect all research findings from legacy reports + visual backtest reports."""
    findings = []

    # From legacy research reports
    reports_dir = ROOT / "reports"
    for path in reports_dir.glob("*/report.json"):
        if "visual_backtest" in str(path):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            generated_at = data.get("generated_at", "")
            for f in data.get("findings", []):
                findings.append({
                    "id": f.get("hypothesis_id", "")[:16],
                    "strategy": f.get("hypothesis_title", "Unknown"),
                    "template_id": f.get("template_id", ""),
                    "strategy_name": f.get("strategy_name", ""),
                    "status": "RESEARCH_PASS" if f.get("outcome") == "PASS" else "RESEARCH_FAIL",
                    "research_score": round(f.get("pass_rate", 0) * 100, 1),
                    "pass_rate": f.get("pass_rate", 0),
                    "windows_total": f.get("windows_total", 0),
                    "win_rate": None,
                    "profit_factor": None,
                    "total_return_pct": None,
                    "max_drawdown_pct": None,
                    "paper_status": "PENDING",
                    "sandbox_status": "NOT_STARTED",
                    "source": "research",
                    "generated_at": generated_at,
                })
        except Exception:
            pass

    # From visual backtest reports (richer data)
    vb_dir = ROOT / "reports" / "visual_backtest"
    if vb_dir.exists():
        for path in vb_dir.glob("**/report.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                metrics = data.get("metrics", {})
                findings.append({
                    "id": data.get("report_id", "")[:16],
                    "strategy": f"{data.get('hypothesis_id', '')} | {data.get('ticker', '')} {data.get('period', '')}",
                    "template_id": data.get("hypothesis_id", ""),
                    "strategy_name": "",
                    "status": "VISUAL_BACKTEST",
                    "research_score": None,
                    "pass_rate": None,
                    "windows_total": None,
                    "win_rate": metrics.get("win_rate", 0),
                    "profit_factor": metrics.get("profit_factor", 0),
                    "total_return_pct": metrics.get("total_return_pct", 0),
                    "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
                    "paper_status": "NOT_STARTED",
                    "sandbox_status": "NOT_STARTED",
                    "source": "visual_backtest",
                    "generated_at": data.get("generated_at", ""),
                })
            except Exception:
                pass

    findings.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    return findings


@router.get("")
def list_strategies(
    status: Optional[str] = Query(None, description="Filter: RESEARCH_PASS | RESEARCH_FAIL | VISUAL_BACKTEST | all"),
    source: Optional[str] = Query(None, description="Filter: research | visual_backtest"),
):
    findings = _all_findings()
    if status and status != "all":
        findings = [f for f in findings if f["status"] == status]
    if source:
        findings = [f for f in findings if f["source"] == source]
    return findings


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str):
    for f in _all_findings():
        if f["id"] == strategy_id or f["template_id"] == strategy_id:
            return f
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
