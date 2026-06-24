import json
import pandas as pd
import psycopg2

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "moex_ai",
    "user": "moex",
    "password": "moex_pass",
}

INITIAL_CASH = 1_000_000
POSITION_SIZE = 0.10
COMMISSION_RATE = 0.0005
SLIPPAGE_RATE = 0.001


def get_signal(strategy_name, row):
    if strategy_name == "RSI_OVERSOLD_NOT_DOWNTREND":
        return row["rsi_14"] < 30 and row["regime"] != "TREND_DOWN"

    if strategy_name == "TREND_UP_SMA_CONFIRM":
        return row["close"] > row["sma_50"] and row["regime"] == "TREND_UP"

    return False


def main():
    conn = psycopg2.connect(**DB)

    try:
        pass_df = pd.read_sql("""
            SELECT strategy_name, ticker
            FROM strategy_validation_results
            WHERE verdict = 'PASS';
        """, conn)

        data = pd.read_sql("""
            SELECT DISTINCT ON (f.ticker)
                f.time, f.ticker, f.close, f.rsi_14, f.sma_50, r.regime
            FROM features_daily f
            JOIN market_regimes_daily r
              ON f.time = r.time AND f.ticker = r.ticker
            ORDER BY f.ticker, f.time DESC;
        """, conn)

        cur = conn.cursor()

        cur.execute("SELECT cash FROM paper_portfolio ORDER BY time DESC LIMIT 1;")
        row = cur.fetchone()
        cash = float(row[0]) if row else INITIAL_CASH

        opened = 0

        for _, strategy in pass_df.iterrows():
            ticker = strategy["ticker"]
            strategy_name = strategy["strategy_name"]

            latest = data[data["ticker"] == ticker]
            if latest.empty:
                continue

            latest = latest.iloc[0]
            signal = get_signal(strategy_name, latest)

            if not signal:
                continue

            cur.execute("""
                SELECT id FROM paper_positions
                WHERE strategy_name = %s AND ticker = %s AND status = 'OPEN'
                LIMIT 1;
            """, (strategy_name, ticker))

            if cur.fetchone():
                continue

            price = float(latest["close"])
            trade_value = cash * POSITION_SIZE
            slippage = trade_value * SLIPPAGE_RATE
            commission = trade_value * COMMISSION_RATE
            quantity = (trade_value - slippage - commission) / price

            if quantity <= 0:
                continue

            cur.execute("""
                INSERT INTO paper_positions (
                    strategy_name, ticker, entry_time, entry_price, quantity, status
                )
                VALUES (%s, %s, %s, %s, %s, 'OPEN');
            """, (
                strategy_name, ticker, latest["time"], price, quantity
            ))

            cur.execute("""
                INSERT INTO paper_trades (
                    strategy_name, ticker, signal_time, side, price, quantity,
                    commission, slippage, reason
                )
                VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s, %s);
            """, (
                strategy_name, ticker, latest["time"], price, quantity,
                commission, slippage, "PASS strategy signal"
            ))

            cash -= trade_value
            opened += 1

            print(f"BUY {ticker} | {strategy_name} | price={price} | qty={quantity:.4f}")

        cur.execute("""
            INSERT INTO paper_portfolio (time, cash, equity, comment)
            VALUES (NOW(), %s, %s, %s);
        """, (cash, cash, f"opened_positions={opened}"))

        conn.commit()
        cur.close()

        print(f"Paper trading run complete. Opened positions: {opened}. Cash: {cash:.2f}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()