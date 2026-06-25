import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pandas as pd

from core.db.postgres import get_connection
from core.analytics.metrics import profit_factor
from core.strategy.catalog import StrategyCatalog


def main():
    conn = get_connection()

    positions = pd.read_sql("""
        SELECT
            strategy_name,
            ticker,
            pnl
        FROM paper_positions
        WHERE status = 'CLOSED';
    """, conn)

    conn.close()

    if positions.empty:
        print("No closed positions found.")
        return

    stats = positions.groupby(["strategy_name", "ticker"]).agg(
        replay_trades=("pnl", "count"),
        replay_total_pnl=("pnl", "sum"),
        replay_expectancy=("pnl", "mean"),
        replay_win_rate=("pnl", lambda x: (x > 0).mean()),
        replay_profit_factor=("pnl", profit_factor),
    ).reset_index()

    StrategyCatalog().update_replay_stats(stats)

    print("strategy_catalog updated")
    print(stats)


if __name__ == "__main__":
    main()
