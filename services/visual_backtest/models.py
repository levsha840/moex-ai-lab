"""Data models for visual backtest reports.

All models are pure Python dataclasses — no external dependencies.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TradeJournalEntry:
    """Single completed trade: entry → exit with P&L and running capital.

    All P&L values are computed on notional capital (not per-share quantity).
    Direction is always LONG for current long-only strategies.
    exit_reason: TIME_EXIT | END_OF_DATA
    """

    trade_id: str
    entry_timestamp: str | None
    entry_bar: int
    entry_price: float
    exit_timestamp: str | None
    exit_bar: int
    exit_price: float
    exit_reason: str
    direction: str
    pnl: float          # absolute PnL in capital currency units
    pnl_pct: float      # % return on entry price
    capital_before: float
    capital_after: float
    is_winner: bool

    @classmethod
    def build(
        cls,
        trade_id: str,
        entry_bar: int,
        entry_price: float,
        exit_bar: int,
        exit_price: float,
        exit_reason: str,
        capital_before: float,
        entry_timestamp: str | None = None,
        exit_timestamp: str | None = None,
        direction: str = "LONG",
    ) -> "TradeJournalEntry":
        pnl_pct = (exit_price - entry_price) / entry_price * 100.0 if entry_price != 0 else 0.0
        pnl = capital_before * pnl_pct / 100.0
        capital_after = capital_before + pnl
        return cls(
            trade_id=trade_id,
            entry_timestamp=entry_timestamp,
            entry_bar=entry_bar,
            entry_price=entry_price,
            exit_timestamp=exit_timestamp,
            exit_bar=exit_bar,
            exit_price=exit_price,
            exit_reason=exit_reason,
            direction=direction,
            pnl=pnl,
            pnl_pct=pnl_pct,
            capital_before=capital_before,
            capital_after=capital_after,
            is_winner=pnl > 0.0,
        )


@dataclass(frozen=True)
class EquityPoint:
    """Equity curve value at a single bar."""

    bar: int
    timestamp: str | None
    capital: float
    drawdown_pct: float  # 0.0 at all-time high; negative values = drawdown %
    in_position: bool


@dataclass(frozen=True)
class BacktestMetrics:
    """Aggregate performance metrics for a single strategy backtest."""

    initial_capital: float
    final_capital: float
    total_return: float      # absolute currency units
    total_return_pct: float  # %
    max_drawdown_pct: float  # most negative drawdown (e.g. -15.3)
    win_rate: float          # 0–1; 0.0 if no trades
    profit_factor: float     # sum_wins / |sum_losses|; float('inf') if no losses
    num_trades: int
    avg_trade_pnl: float
    avg_trade_pnl_pct: float
    exposure_time_pct: float  # % of test bars spent in a position

    @property
    def is_profitable(self) -> bool:
        return self.total_return_pct > 0.0

    def to_dict(self) -> dict:
        return {
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "total_return": round(self.total_return, 2),
            "total_return_pct": round(self.total_return_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": (
                round(self.profit_factor, 4)
                if math.isfinite(self.profit_factor) else "inf"
            ),
            "num_trades": self.num_trades,
            "avg_trade_pnl": round(self.avg_trade_pnl, 2),
            "avg_trade_pnl_pct": round(self.avg_trade_pnl_pct, 4),
            "exposure_time_pct": round(self.exposure_time_pct, 2),
        }


@dataclass
class VisualBacktestReport:
    """Complete backtest report for one hypothesis × dataset combination."""

    report_id: str
    hypothesis_id: str
    ticker: str
    period: str
    timeframe: str
    dataset_id: str
    initial_capital: float
    trade_journal: list[TradeJournalEntry]
    equity_curve: list[EquityPoint]
    metrics: BacktestMetrics
    chart_path: Path | None
    report_json_path: Path
    generated_at: str

    def to_dict(self) -> dict:
        def _entry_dict(e: TradeJournalEntry) -> dict:
            return {
                "trade_id": e.trade_id,
                "entry_timestamp": e.entry_timestamp,
                "entry_bar": e.entry_bar,
                "entry_price": e.entry_price,
                "exit_timestamp": e.exit_timestamp,
                "exit_bar": e.exit_bar,
                "exit_price": e.exit_price,
                "exit_reason": e.exit_reason,
                "direction": e.direction,
                "pnl": round(e.pnl, 4),
                "pnl_pct": round(e.pnl_pct, 4),
                "capital_before": round(e.capital_before, 2),
                "capital_after": round(e.capital_after, 2),
                "is_winner": e.is_winner,
            }

        return {
            "report_id": self.report_id,
            "hypothesis_id": self.hypothesis_id,
            "ticker": self.ticker,
            "period": self.period,
            "timeframe": self.timeframe,
            "dataset_id": self.dataset_id,
            "initial_capital": self.initial_capital,
            "metrics": self.metrics.to_dict(),
            "trade_journal": [_entry_dict(e) for e in self.trade_journal],
            "chart_path": str(self.chart_path) if self.chart_path else None,
            "generated_at": self.generated_at,
        }
