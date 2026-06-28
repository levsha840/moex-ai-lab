"""Visual chart renderer — matplotlib PNG output.

Generates a 3-panel chart per hypothesis × dataset:
  Panel 1: Close price + BUY (^) / EXIT (v) trade markers + SMA20
  Panel 2: Equity curve (capital over time)
  Panel 3: Drawdown curve (filled below zero)

Uses the 'Agg' backend — works headless (no display required).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

from services.visual_backtest.models import BacktestMetrics, EquityPoint, TradeJournalEntry

if TYPE_CHECKING:
    pass


def render_chart(
    candles: list[dict],
    trades: list[TradeJournalEntry],
    equity_curve: list[EquityPoint],
    metrics: BacktestMetrics,
    output_path: Path,
    title: str = "",
) -> Path:
    """Render a 3-panel backtest chart and save to output_path (PNG).

    Args:
        candles:      Full OHLCV candle list (for close price panel).
        trades:       Trade journal entries.
        equity_curve: Bar-by-bar equity series.
        metrics:      Aggregate metrics (shown in subtitle).
        output_path:  Where to save the PNG file.
        title:        Chart title (e.g. "H-BB-SQUEEZE | SBER 2023 1H").

    Returns:
        Path to the saved PNG file.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.gridspec as gridspec

    closes = [float(c["close"]) for c in candles]
    n = len(closes)
    bars = list(range(n))

    # SMA20 for price panel overlay
    sma20: list[float | None] = [None] * n
    for i in range(19, n):
        sma20[i] = sum(closes[i - 19: i + 1]) / 20.0

    # Trade marker coordinates
    buy_bars:  list[int]   = [t.entry_bar for t in trades]
    buy_prices = [t.entry_price for t in trades]
    sell_bars: list[int]  = [t.exit_bar for t in trades]
    sell_prices = [t.exit_price for t in trades]

    # Equity and drawdown series
    eq_capital = [ep.capital for ep in equity_curve]
    dd_pct     = [ep.drawdown_pct for ep in equity_curve]

    # ── Figure setup ──────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(16, 10))
    fig.patch.set_facecolor("#0d1117")

    gs = gridspec.GridSpec(3, 1, height_ratios=[3, 1.5, 1.2], hspace=0.08)
    ax_price = fig.add_subplot(gs[0])
    ax_eq    = fig.add_subplot(gs[1], sharex=ax_price)
    ax_dd    = fig.add_subplot(gs[2], sharex=ax_price)

    _style_axis(ax_price)
    _style_axis(ax_eq)
    _style_axis(ax_dd)

    # ── Panel 1: Price ─────────────────────────────────────────────────────────
    ax_price.plot(bars, closes, color="#58a6ff", linewidth=0.8, label="Close", zorder=2)

    valid_sma20_x = [i for i in bars if sma20[i] is not None]
    valid_sma20_y = [sma20[i] for i in valid_sma20_x]
    if valid_sma20_x:
        ax_price.plot(valid_sma20_x, valid_sma20_y, color="#f0883e",
                      linewidth=0.7, alpha=0.8, label="SMA20", zorder=2)

    # BUY markers
    if buy_bars:
        ax_price.scatter(buy_bars, buy_prices, marker="^", color="#3fb950",
                         s=60, zorder=5, label="BUY")

    # SELL/EXIT markers
    if sell_bars:
        ax_price.scatter(sell_bars, sell_prices, marker="v", color="#f85149",
                         s=60, zorder=5, label="EXIT")

    # Shade in-position periods
    for t in trades:
        ax_price.axvspan(t.entry_bar, t.exit_bar, alpha=0.08, color="#3fb950", zorder=1)

    ax_price.set_ylabel("Price (RUB)", color="#8b949e", fontsize=9)
    ax_price.legend(loc="upper left", framealpha=0.0, fontsize=8,
                    labelcolor="white")

    subtitle = (
        f"Trades: {metrics.num_trades} | "
        f"Return: {metrics.total_return_pct:+.2f}% | "
        f"MaxDD: {metrics.max_drawdown_pct:.2f}% | "
        f"WinRate: {metrics.win_rate*100:.1f}% | "
        f"PF: {'inf' if math.isinf(metrics.profit_factor) else f'{metrics.profit_factor:.2f}'} | "
        f"Exposure: {metrics.exposure_time_pct:.1f}%"
    )
    fig.suptitle(title, color="white", fontsize=11, y=0.98)
    ax_price.set_title(subtitle, color="#8b949e", fontsize=8, pad=4)

    # ── Panel 2: Equity curve ──────────────────────────────────────────────────
    ax_eq.plot(bars[:len(eq_capital)], eq_capital, color="#3fb950", linewidth=0.9)
    ax_eq.axhline(metrics.initial_capital, color="#8b949e", linewidth=0.6,
                  linestyle="--", alpha=0.7)
    ax_eq.fill_between(
        bars[:len(eq_capital)], metrics.initial_capital, eq_capital,
        where=[c >= metrics.initial_capital for c in eq_capital],
        alpha=0.15, color="#3fb950",
    )
    ax_eq.fill_between(
        bars[:len(eq_capital)], metrics.initial_capital, eq_capital,
        where=[c < metrics.initial_capital for c in eq_capital],
        alpha=0.15, color="#f85149",
    )
    ax_eq.set_ylabel("Capital", color="#8b949e", fontsize=9)

    # ── Panel 3: Drawdown ──────────────────────────────────────────────────────
    ax_dd.fill_between(bars[:len(dd_pct)], 0, dd_pct, alpha=0.5, color="#f85149")
    ax_dd.plot(bars[:len(dd_pct)], dd_pct, color="#f85149", linewidth=0.7)
    ax_dd.axhline(0, color="#8b949e", linewidth=0.5, alpha=0.6)
    ax_dd.set_ylabel("Drawdown %", color="#8b949e", fontsize=9)
    ax_dd.set_xlabel("Bar", color="#8b949e", fontsize=9)

    plt.setp(ax_price.get_xticklabels(), visible=False)
    plt.setp(ax_eq.get_xticklabels(), visible=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path


def _style_axis(ax) -> None:
    ax.set_facecolor("#0d1117")
    ax.tick_params(colors="#8b949e", labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    ax.yaxis.label.set_color("#8b949e")
    ax.grid(True, color="#21262d", linewidth=0.5, linestyle="-")
