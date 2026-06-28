"""Paper Portfolio router."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/summary")
def get_summary():
    """Paper portfolio summary. No positions approved yet — returns zeroed state."""
    return {
        "enabled": False,
        "initial_capital": 1_000_000.0,
        "current_capital": 1_000_000.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "open_positions": 0,
        "total_trades": 0,
        "win_rate": 0.0,
        "exposure_pct": 0.0,
        "note": "No strategies approved for paper trading yet. Approve a RESEARCH_PASS candidate first.",
    }


@router.get("/equity")
def get_equity():
    """Equity curve — flat until paper trading activates."""
    return [{"bar": 0, "capital": 1_000_000.0, "drawdown_pct": 0.0}]


@router.get("/positions")
def get_positions():
    return []


@router.get("/trades")
def get_trades():
    return []
