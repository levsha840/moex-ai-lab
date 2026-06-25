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


def profit_factor(series):
    wins = series[series > 0]
    losses = series[series <= 0]

    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())

    if gross_loss == 0:
        return np.inf

    return gross_profit / gross_loss


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

    positions["entry_time"] = pd.to_datetime(positions["entry_time"])
    positions["exit_time"] = pd.to_datetime(positions["exit_time"])
    positions["holding_days"] = (
        positions["exit_time"] - positions["entry_time"]
    ).dt.days

    print("=" * 80)
    print("REPLAY ANALYTICS v2")
    print("=" * 80)

    print("\nClose reasons:")
    print(
        positions.groupby("close_reason").agg(
            trades=("id", "count"),
            total_pnl=("pnl", "sum"),
            avg_pnl=("pnl", "mean"),
            win_rate=("pnl", lambda x: (x > 0).mean()),
            profit_factor=("pnl", profit_factor),
            avg_holding_days=("holding_days", "mean"),
        ).sort_values("total_pnl", ascending=False)
    )

    print("\nBy strategy:")
    print(
        positions.groupby("strategy_name").agg(
            trades=("id", "count"),
            total_pnl=("pnl", "sum"),
            avg_pnl=("pnl", "mean"),
            win_rate=("pnl", lambda x: (x > 0).mean()),
            profit_factor=("pnl", profit_factor),
            avg_holding_days=("holding_days", "mean"),
        ).sort_values("total_pnl", ascending=False)
    )

    print("\nBy ticker:")
    print(
        positions.groupby("ticker").agg(
            trades=("id", "count"),
            total_pnl=("pnl", "sum"),
            avg_pnl=("pnl", "mean"),
            win_rate=("pnl", lambda x: (x > 0).mean()),
            profit_factor=("pnl", profit_factor),
            avg_holding_days=("holding_days", "mean"),
        ).sort_values("total_pnl", ascending=False)
    )

    print("\nStrategy x ticker:")
    matrix = positions.groupby(["strategy_name", "ticker"]).agg(
        trades=("id", "count"),
        total_pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        win_rate=("pnl", lambda x: (x > 0).mean()),
        profit_factor=("pnl", profit_factor),
        avg_holding_days=("holding_days", "mean"),
    ).sort_values("total_pnl", ascending=False)

    print(matrix)

    print("\nWorst trades:")
    print(
        positions[
            [
                "strategy_name",
                "ticker",
                "entry_time",
                "exit_time",
                "pnl",
                "pnl_pct",
                "close_reason",
                "holding_days",
            ]
        ].sort_values("pnl").head(10)
    )

    print("\nBest trades:")
    print(
        positions[
            [
                "strategy_name",
                "ticker",
                "entry_time",
                "exit_time",
                "pnl",
                "pnl_pct",
                "close_reason",
                "holding_days",
            ]
        ].sort_values("pnl", ascending=False).head(10)
    )

    print("=" * 80)


if __name__ == "__main__":
    main()