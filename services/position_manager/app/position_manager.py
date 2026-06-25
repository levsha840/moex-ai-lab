import psycopg2
import pandas as pd

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "moex_ai",
    "user": "moex",
    "password": "moex_pass",
}

TAKE_PROFIT = 0.10
STOP_LOSS = -0.05

conn = psycopg2.connect(**DB)

positions = pd.read_sql("""
SELECT *
FROM paper_positions
WHERE status='OPEN';
""", conn)

prices = pd.read_sql("""
SELECT DISTINCT ON (ticker)
ticker,
close,
time
FROM features_daily
ORDER BY ticker,time DESC;
""", conn)

cur = conn.cursor()

closed = 0

for _, pos in positions.iterrows():

    p = prices[prices["ticker"] == pos["ticker"]]

    if p.empty:
        continue

    current_price = float(p.iloc[0]["close"])

    pnl_pct = (current_price - float(pos["entry_price"])) / float(pos["entry_price"])
    pnl = pnl_pct * float(pos["quantity"]) * float(pos["entry_price"])

    close_trade = False
    reason = None

    if pnl_pct >= TAKE_PROFIT:
        close_trade = True
        reason = "TAKE_PROFIT"

    if pnl_pct <= STOP_LOSS:
        close_trade = True
        reason = "STOP_LOSS"

    if close_trade:

        cur.execute("""
        UPDATE paper_positions
        SET
            status='CLOSED',
            exit_time=NOW(),
            exit_price=%s,
            pnl=%s,
            pnl_pct=%s,
            close_reason=%s
        WHERE id=%s
        """, (
            current_price,
            pnl,
            pnl_pct,
            reason,
            int(pos["id"])
        ))

        closed += 1

        print(
            f"CLOSE {pos['ticker']} "
            f"{reason} "
            f"PnL={round(pnl,2)} "
            f"({round(pnl_pct*100,2)}%)"
        )

conn.commit()
cur.close()
conn.close()

print(f"Closed positions: {closed}")