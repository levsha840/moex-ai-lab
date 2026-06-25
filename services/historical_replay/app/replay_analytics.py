import pandas as pd
import psycopg2
import numpy as np

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "moex_ai",
    "user": "moex",
    "password": "moex_pass",
}

INITIAL_CASH = 1_000_000


def max_drawdown(equity_series):
    peak = equity_series.cummax()
    drawdown = (equity_series - peak) / peak
    return drawdown.min()


def main():
    conn = psycopg2.connect(**DB)

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

    win_rate = len(wins) / total_trades

    gross_profit = wins["pnl"].sum()
    gross_loss = abs(losses["pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else np.inf

    expectancy = positions["pnl"].mean()
    avg_win = wins["pnl"].mean() if not wins.empty else 0
    avg_loss = losses["pnl"].mean() if not losses.empty else 0

    final_equity = portfolio["equity"].iloc[-1]
    total_return = (final_equity - INITIAL_CASH) / INITIAL_CASH

    daily_returns = portfolio["equity"].pct_change().dropna()
    sharpe = np.sqrt(252) * daily_returns.mean() / daily_returns.std() if daily_returns.std() != 0 else 0

    downside_returns = daily_returns[daily_returns < 0]
    sortino = (
        np.sqrt(252) * daily_returns.mean() / downside_returns.std()
        if downside_returns.std() != 0 else 0
    )

    mdd = max_drawdown(portfolio["equity"])

    print("=" * 60)
    print("REPLAY ANALYTICS v1")
    print("=" * 60)
    print(f"Total trades:       {total_trades}")
    print(f"Wins:               {len(wins)}")
    print(f"Losses:             {len(losses)}")
    print(f"Win rate:           {win_rate:.2%}")
    print(f"Gross profit:       {gross_profit:.2f}")
    print(f"Gross loss:         {gross_loss:.2f}")
    print(f"Profit factor:      {profit_factor:.2f}")
    print(f"Expectancy:         {expectancy:.2f}")
    print(f"Average win:        {avg_win:.2f}")
    print(f"Average loss:       {avg_loss:.2f}")
    print(f"Total return:       {total_return:.2%}")
    print(f"Max drawdown:       {mdd:.2%}")
    print(f"Sharpe:             {sharpe:.2f}")
    print(f"Sortino:            {sortino:.2f}")
    print("=" * 60)

    print("\nBy strategy:")
    strategy_stats = positions.groupby("strategy_name").agg(
        trades=("id", "count"),
        total_pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        win_rate=("pnl", lambda x: (x > 0).mean()),
    ).sort_values("total_pnl", ascending=False)

    print(strategy_stats)

    print("\nBy ticker:")
    ticker_stats = positions.groupby("ticker").agg(
        trades=("id", "count"),
        total_pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        win_rate=("pnl", lambda x: (x > 0).mean()),
    ).sort_values("total_pnl", ascending=False)

    print(ticker_stats)


if __name__ == "__main__":
    main()