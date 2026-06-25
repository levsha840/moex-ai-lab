import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pandas as pd
import numpy as np

from core.db.postgres import get_connection
from core.analytics.metrics import profit_factor, max_drawdown


INITIAL_CASH = 1_000_000


def main():
    conn = get_connection()

    positions = pd.read_sql("""
        SELECT
            id,
            strategy_name,
            ticker,
            entry_time,
            exit_time,
            entry_price,
            exit_price,
            quantity,
            pnl,
            pnl_pct,
            close_reason
        FROM paper_positions
        WHERE status = 'CLOSED'
        ORDER BY exit_time;
    """, conn)

    portfolio = pd.read_sql("""
        SELECT time, cash, equity
        FROM paper_portfolio
        ORDER BY time;
    """, conn)

    conn.close()

    if positions.empty:
        print("No closed positions found.")
        return

    total_trades = len(positions)
    wins = positions[positions["pnl"] > 0]
    losses = positions[positions["pnl"] <= 0]

    gross_profit = wins["pnl"].sum()
    gross_loss = abs(losses["pnl"].sum())

    daily_returns = portfolio["equity"].pct_change().dropna()
    sharpe = np.sqrt(252) * daily_returns.mean() / daily_returns.std() if daily_returns.std() != 0 else 0

    downside_returns = daily_returns[daily_returns < 0]
    sortino = (
        np.sqrt(252) * daily_returns.mean() / downside_returns.std()
        if downside_returns.std() != 0 else 0
    )

    print("=" * 80)
    print("REPLAY ANALYTICS CORE")
    print("=" * 80)
    print(f"Total trades:       {total_trades}")
    print(f"Wins:               {len(wins)}")
    print(f"Losses:             {len(losses)}")
    print(f"Win rate:           {len(wins) / total_trades:.2%}")
    print(f"Gross profit:       {gross_profit:.2f}")
    print(f"Gross loss:         {gross_loss:.2f}")
    print(f"Profit factor:      {profit_factor(positions['pnl']):.2f}")
    print(f"Expectancy:         {positions['pnl'].mean():.2f}")
    print(f"Total return:       {(portfolio['equity'].iloc[-1] - INITIAL_CASH) / INITIAL_CASH:.2%}")
    print(f"Max drawdown:       {max_drawdown(portfolio['equity']):.2%}")
    print(f"Sharpe:             {sharpe:.2f}")
    print(f"Sortino:            {sortino:.2f}")

    print("\nBy strategy/ticker:")
    print(
        positions.groupby(["strategy_name", "ticker"]).agg(
            trades=("id", "count"),
            total_pnl=("pnl", "sum"),
            avg_pnl=("pnl", "mean"),
            win_rate=("pnl", lambda x: (x > 0).mean()),
            profit_factor=("pnl", profit_factor),
        ).sort_values("total_pnl", ascending=False)
    )


if __name__ == "__main__":
    main()
