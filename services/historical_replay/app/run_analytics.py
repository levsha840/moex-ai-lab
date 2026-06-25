import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.append(str(ROOT))

import pandas as pd
from core.db.postgres import get_connection
from core.analytics.replay_report import ReplayReport
from core.analytics.metrics import profit_factor

def main():
    conn = get_connection()
    positions = pd.read_sql("SELECT * FROM paper_positions WHERE status='CLOSED' ORDER BY exit_time;", conn)
    portfolio = pd.read_sql("SELECT time,cash,equity FROM paper_portfolio ORDER BY time;", conn)
    conn.close()
    report = ReplayReport().build(positions, portfolio)
    print("="*80); print("MOEX AI LAB v1 Replay Analytics"); print("="*80)
    for k,v in report.items():
        print(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")
    if not positions.empty:
        print("\nBy strategy/ticker:")
        print(positions.groupby(["strategy_name","ticker"]).agg(
            trades=("id","count"), total_pnl=("pnl","sum"), avg_pnl=("pnl","mean"),
            win_rate=("pnl", lambda x: (x>0).mean()), profit_factor=("pnl", profit_factor)
        ).sort_values("total_pnl", ascending=False))

if __name__ == "__main__":
    main()
