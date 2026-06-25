import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.append(str(ROOT))

from core.db.postgres import get_connection

def score(pf, exp, trades):
    pf = pf or 0; exp = exp or 0; trades = trades or 0
    return min(100, max(0, pf*25 + max(exp,0)/100 + min(trades,100)*0.2))

def main():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id,replay_profit_factor,replay_expectancy,replay_trades FROM strategy_catalog;")
    rows = cur.fetchall()
    for sid,pf,exp,trades in rows:
        cur.execute("UPDATE strategy_catalog SET meta_score=%s, updated_at=now() WHERE id=%s;", (score(pf,exp,trades), sid))
    conn.commit(); cur.close(); conn.close()
    print(f"Meta scores updated for {len(rows)} strategies")

if __name__ == "__main__":
    main()
