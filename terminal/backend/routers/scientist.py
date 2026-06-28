"""Chief Scientist router — decision log from research reports."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter

ROOT = Path(__file__).parent.parent.parent.parent

router = APIRouter()

_DECISION_ICONS = {
    "ARCHIVE_HYPOTHESIS": "ARCHIVE",
    "CONTINUE_RESEARCH": "REQUEST_MORE_EVIDENCE",
    "APPROVE_FOR_PAPER": "APPROVE",
    "REJECT": "REJECT",
    "MONITOR": "REQUEST_MORE_EVIDENCE",
}


@router.get("/decisions")
def get_decisions():
    """Collect all chief scientist decisions from legacy research reports."""
    decisions = []

    reports_dir = ROOT / "reports"
    for path in sorted(reports_dir.glob("*/report.json"), key=lambda p: os.path.getmtime(p), reverse=True):
        if "visual_backtest" in str(path):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            generated_at = data.get("generated_at", "")
            session_id = data.get("session_id", "")
            summary = data.get("summary", {})

            # From recommendations (chief scientist decisions)
            for rec in data.get("recommendations", []):
                kind_raw = rec.get("kind", "UNKNOWN")
                kind = _DECISION_ICONS.get(kind_raw, kind_raw)
                decisions.append({
                    "id": f"{session_id[:8]}_{rec.get('hypothesis_id', '')[:8]}",
                    "type": kind,
                    "timestamp": generated_at,
                    "hypothesis_id": rec.get("hypothesis_id", ""),
                    "hypothesis_title": rec.get("hypothesis_title", ""),
                    "rationale": rec.get("rationale", ""),
                    "stats": {
                        "pass_rate": rec.get("pass_rate"),
                        "windows_total": rec.get("windows_total"),
                    },
                    "session_id": session_id,
                    "research_link": f"/research/sessions/{session_id}",
                })

            # From findings (alpha gate decisions)
            for f in data.get("findings", []):
                outcome = f.get("outcome", "")
                if outcome in ("PASS", "FAIL"):
                    decisions.append({
                        "id": f"{session_id[:8]}_{f.get('hypothesis_id', '')[:8]}_gate",
                        "type": "APPROVE" if outcome == "PASS" else "REJECT",
                        "timestamp": generated_at,
                        "hypothesis_id": f.get("template_id", ""),
                        "hypothesis_title": f.get("hypothesis_title", ""),
                        "rationale": f.get("rationale", f"Alpha Gate: pass_rate={f.get('pass_rate',0):.1%} over {f.get('windows_total',0)} windows"),
                        "stats": {
                            "pass_rate": f.get("pass_rate"),
                            "windows_total": f.get("windows_total"),
                        },
                        "session_id": session_id,
                        "research_link": f"/research/sessions/{session_id}",
                    })
        except Exception:
            pass

    decisions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return decisions


@router.get("/stats")
def get_stats():
    decisions = get_decisions()
    counts = {}
    for d in decisions:
        t = d.get("type", "UNKNOWN")
        counts[t] = counts.get(t, 0) + 1
    return {
        "total_decisions": len(decisions),
        "by_type": counts,
    }
