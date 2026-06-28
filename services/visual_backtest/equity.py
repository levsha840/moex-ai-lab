"""Equity curve and backtest metrics computation.

All functions are pure (no I/O, no randomness) → deterministic, testable.
"""
from __future__ import annotations

import math
from services.visual_backtest.models import BacktestMetrics, EquityPoint, TradeJournalEntry


def build_equity_curve(
    candles: list[dict],
    trades: list[TradeJournalEntry],
    initial_capital: float,
) -> list[EquityPoint]:
    """Build a bar-by-bar equity curve with drawdown.

    Capital is constant between trades; it steps at each trade exit.
    Drawdown is computed as (capital - rolling_max) / rolling_max * 100.

    Args:
        candles:         All OHLCV candles (same as used for journal).
        trades:          Ordered list of completed trades.
        initial_capital: Starting capital.

    Returns:
        List of EquityPoint, one per bar.
    """
    n = len(candles)
    if n == 0:
        return []

    # Build bar-indexed lookup: bar -> capital_after (at exit)
    capital_at_exit: dict[int, float] = {}
    for t in trades:
        capital_at_exit[t.exit_bar] = t.capital_after

    # Build in-position mask: set of bars where a position is open
    in_position_bars: set[int] = set()
    for t in trades:
        for b in range(t.entry_bar, t.exit_bar + 1):
            in_position_bars.add(b)

    # Walk bar-by-bar
    curve: list[EquityPoint] = []
    current_capital = initial_capital
    rolling_max = initial_capital
    timestamps = [c.get("ts") for c in candles]

    for bar in range(n):
        if bar in capital_at_exit:
            current_capital = capital_at_exit[bar]

        rolling_max = max(rolling_max, current_capital)
        dd_pct = (current_capital - rolling_max) / rolling_max * 100.0 if rolling_max > 0 else 0.0

        curve.append(EquityPoint(
            bar=bar,
            timestamp=timestamps[bar],
            capital=current_capital,
            drawdown_pct=dd_pct,
            in_position=bar in in_position_bars,
        ))

    return curve


def compute_metrics(
    trades: list[TradeJournalEntry],
    equity_curve: list[EquityPoint],
    initial_capital: float,
) -> BacktestMetrics:
    """Compute aggregate performance metrics.

    Args:
        trades:          All completed trades from the journal.
        equity_curve:    Bar-by-bar equity series.
        initial_capital: Starting capital.

    Returns:
        BacktestMetrics with all fields filled.
    """
    final_capital = equity_curve[-1].capital if equity_curve else initial_capital
    total_return = final_capital - initial_capital
    total_return_pct = total_return / initial_capital * 100.0 if initial_capital > 0 else 0.0

    # Drawdown
    max_drawdown_pct = min((ep.drawdown_pct for ep in equity_curve), default=0.0)

    # Trade stats
    num_trades = len(trades)
    if num_trades == 0:
        return BacktestMetrics(
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            win_rate=0.0,
            profit_factor=0.0,
            num_trades=0,
            avg_trade_pnl=0.0,
            avg_trade_pnl_pct=0.0,
            exposure_time_pct=0.0,
        )

    winners = [t for t in trades if t.is_winner]
    losers  = [t for t in trades if not t.is_winner]

    win_rate = len(winners) / num_trades
    sum_wins  = sum(t.pnl for t in winners)
    sum_losses = abs(sum(t.pnl for t in losers))
    profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else math.inf

    avg_trade_pnl     = sum(t.pnl for t in trades) / num_trades
    avg_trade_pnl_pct = sum(t.pnl_pct for t in trades) / num_trades

    # Exposure time: bars in position / total bars
    n_bars = len(equity_curve)
    in_pos_bars = sum(1 for ep in equity_curve if ep.in_position)
    exposure_time_pct = in_pos_bars / n_bars * 100.0 if n_bars > 0 else 0.0

    return BacktestMetrics(
        initial_capital=initial_capital,
        final_capital=final_capital,
        total_return=total_return,
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_drawdown_pct,
        win_rate=win_rate,
        profit_factor=profit_factor,
        num_trades=num_trades,
        avg_trade_pnl=avg_trade_pnl,
        avg_trade_pnl_pct=avg_trade_pnl_pct,
        exposure_time_pct=exposure_time_pct,
    )
