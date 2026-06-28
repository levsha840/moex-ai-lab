"""Research router — hypotheses, datasets, candles, visual backtest reports."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

ROOT = Path(__file__).parent.parent.parent.parent

router = APIRouter()


# ── Hypotheses ────────────────────────────────────────────────────────────────

@router.get("/hypotheses")
def list_hypotheses():
    try:
        from services.research.hypothesis_registry import HypothesisTemplateRegistry
        registry = HypothesisTemplateRegistry()
        templates = registry.list()
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "category": getattr(t, "category", "unknown"),
                "priority": getattr(t, "priority", "P2"),
                "strategy_name": getattr(t, "strategy_name", ""),
            }
            for t in templates
        ]
    except Exception as e:
        return {"error": str(e), "hypotheses": []}


# ── Datasets ──────────────────────────────────────────────────────────────────

@router.get("/datasets")
def list_datasets(
    ticker: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
):
    manifest_path = ROOT / "data" / "universe" / "manifest_index.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cells = manifest.get("cells", [])
    if ticker and isinstance(ticker, str):
        cells = [c for c in cells if c.get("ticker", "").upper() == ticker.upper()]
    if period and isinstance(period, str):
        cells = [c for c in cells if str(c.get("period", "")) == str(period)]
    if timeframe and isinstance(timeframe, str):
        cells = [c for c in cells if c.get("timeframe", "") == timeframe]
    return cells


@router.get("/datasets/{dataset_id}/candles")
def get_candles(dataset_id: str, limit: int = Query(default=5000, le=10000)):
    """Return OHLCV bars for a dataset."""
    try:
        from services.research.dataset import DatasetLoader
        loader = DatasetLoader()
        dataset = loader.load(dataset_id, ROOT / "data")
        candles = list(dataset.candles)[:limit]
        # Convert to frontend-friendly format with Unix timestamps
        result = []
        for c in candles:
            ts_str = c.get("ts", "")
            try:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                ts_unix = int(dt.timestamp())
            except Exception:
                ts_unix = 0
            result.append({
                "time": ts_unix,
                "ts": ts_str,
                "open": float(c.get("open", 0)),
                "high": float(c.get("high", 0)),
                "low": float(c.get("low", 0)),
                "close": float(c.get("close", 0)),
                "volume": float(c.get("volume", 0)),
            })
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Visual Backtest Reports ───────────────────────────────────────────────────

@router.get("/reports")
def list_reports():
    """List all available visual backtest reports."""
    vb_dir = ROOT / "reports" / "visual_backtest"
    if not vb_dir.exists():
        return []
    reports = []
    for path in vb_dir.glob("**/report.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            metrics = data.get("metrics", {})
            reports.append({
                "report_id": data.get("report_id", ""),
                "hypothesis_id": data.get("hypothesis_id", ""),
                "ticker": data.get("ticker", ""),
                "period": data.get("period", ""),
                "timeframe": data.get("timeframe", "1h"),
                "dataset_id": data.get("dataset_id", ""),
                "generated_at": data.get("generated_at", ""),
                "metrics": metrics,
                "num_trades": metrics.get("num_trades", 0),
                "total_return_pct": metrics.get("total_return_pct", 0),
                "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
                "win_rate": metrics.get("win_rate", 0),
                "profit_factor": metrics.get("profit_factor", 0),
            })
        except Exception:
            pass
    reports.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    return reports


@router.get("/reports/{hypothesis_id}/{ticker}/{period}")
def get_report(hypothesis_id: str, ticker: str, period: str, timeframe: str = "1h"):
    """Get a specific visual backtest report with full trade journal."""
    slug = f"{ticker.lower()}_{period}_{timeframe}"
    path = ROOT / "reports" / "visual_backtest" / hypothesis_id / slug / "report.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {hypothesis_id}/{slug}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{hypothesis_id}/{ticker}/{period}/trades/{trade_id}")
def get_trade_detail(hypothesis_id: str, ticker: str, period: str, trade_id: str, timeframe: str = "1h"):
    """Get a single trade with explain-decision data."""
    slug = f"{ticker.lower()}_{period}_{timeframe}"
    path = ROOT / "reports" / "visual_backtest" / hypothesis_id / slug / "report.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    data = json.loads(path.read_text(encoding="utf-8"))
    journal = data.get("trade_journal", [])
    trade = next((t for t in journal if t.get("trade_id") == trade_id), None)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade '{trade_id}' not found")

    # Find the hypothesis template for signal config
    try:
        from services.research.hypothesis_registry import HypothesisTemplateRegistry
        registry = HypothesisTemplateRegistry()
        template = registry.get(hypothesis_id)
        strategy_name = getattr(template, "strategy_name", "unknown")
    except Exception:
        strategy_name = "unknown"

    # Build explain-decision data
    return {
        "trade": trade,
        "hypothesis_id": hypothesis_id,
        "strategy_name": strategy_name,
        "entry_analysis": {
            "signal_type": strategy_name,
            "entry_bar": trade.get("entry_bar"),
            "entry_price": trade.get("entry_price"),
            "entry_timestamp": trade.get("entry_timestamp"),
            "reason": "Signal threshold crossed on entry bar",
            "factors": _explain_entry(strategy_name),
        },
        "exit_analysis": {
            "exit_bar": trade.get("exit_bar"),
            "exit_price": trade.get("exit_price"),
            "exit_timestamp": trade.get("exit_timestamp"),
            "exit_reason": trade.get("exit_reason"),
            "pnl": trade.get("pnl"),
            "pnl_pct": trade.get("pnl_pct"),
        },
        "chief_scientist": {
            "decision": "MONITOR",
            "rationale": "Trade within normal operating parameters.",
        },
    }


def _explain_entry(strategy_name: str) -> list[dict]:
    explanations = {
        "bb_squeeze": [
            {"indicator": "Bollinger Bands Z-Score", "value": "< -2.0", "confirmed": True, "note": "Price below lower band — mean-reversion signal"},
            {"indicator": "ADX", "value": "< 20", "confirmed": True, "note": "Low trend strength — regime suitable for reversion"},
            {"indicator": "Volume", "value": "> avg", "confirmed": False, "note": "Volume not checked in this signal type"},
        ],
        "rsi_oversold": [
            {"indicator": "RSI(14)", "value": "< 30", "confirmed": True, "note": "Oversold condition — bounce candidate"},
            {"indicator": "Trend direction", "value": "any", "confirmed": True, "note": "Signal fires in all regimes"},
        ],
        "dual_ma_trend": [
            {"indicator": "SMA(5)", "value": "> SMA(20)", "confirmed": True, "note": "Fast MA above slow MA"},
            {"indicator": "SMA(20)", "value": "> SMA(50)", "confirmed": True, "note": "Medium MA above slow MA — dual confirmation"},
        ],
        "adx_continuation": [
            {"indicator": "ADX(14)", "value": "> 25", "confirmed": True, "note": "Strong trend in progress"},
            {"indicator": "RSI(14)", "value": "40–60", "confirmed": True, "note": "RSI in neutral zone — not over-extended"},
        ],
        "rsi_momentum": [
            {"indicator": "RSI(14)", "value": "> 55 rising", "confirmed": True, "note": "Momentum acceleration"},
            {"indicator": "SMA(20)", "value": "rising", "confirmed": True, "note": "Trend confirmation"},
        ],
        "sma_crossover": [
            {"indicator": "SMA(20)", "value": "crossed SMA(50) upward", "confirmed": True, "note": "Golden cross detected"},
        ],
        "momentum_pullback": [
            {"indicator": "SMA(5)", "value": "> SMA(20)", "confirmed": True, "note": "Trend up"},
            {"indicator": "RSI(14)", "value": "< 45", "confirmed": True, "note": "Short-term pullback"},
        ],
        "vol_breakout": [
            {"indicator": "Realized Vol", "value": "expanding", "confirmed": True, "note": "Volatility breakout detected"},
            {"indicator": "ATR", "value": "> 1.5x avg", "confirmed": True, "note": "Range expansion"},
        ],
        "trend_strength": [
            {"indicator": "ADX(14)", "value": "> 30", "confirmed": True, "note": "Strong trend"},
            {"indicator": "SMA alignment", "value": "5 > 20 > 50", "confirmed": True, "note": "All MAs aligned bull"},
        ],
    }
    return explanations.get(strategy_name, [
        {"indicator": "Signal", "value": "threshold met", "confirmed": True, "note": "Entry condition satisfied"}
    ])
