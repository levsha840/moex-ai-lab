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
TAKE_PROFIT = 0.10
STOP_LOSS = -0.05


def get_signal(strategy_name, row):
    if strategy_name == "RSI_OVERSOLD_NOT_DOWNTREND":
        return row["rsi_14"] < 30 and row["regime"] != "TREND_DOWN"

    if strategy_name == "TREND_UP_SMA_CONFIRM":
        return row["close"] > row["sma_50"] and row["regime"] == "TREND_UP"

    return False


def main():
    conn = psycopg2.connect(**DB)

    pass_df = pd.read_sql("""
        SELECT
            id AS strategy_catalog_id,
            strategy_name,
            ticker,
            version,
            status
        FROM strategy_catalog
        WHERE status = 'active'
        ORDER BY ticker, strategy_name;
    """, conn)

    data = pd.read_sql("""
        SELECT
            f.time,
            f.ticker,
            f.close,
            f.rsi_14,
            f.sma_50,
            r.regime
        FROM features_daily f
        JOIN market_regimes_daily r
          ON f.time = r.time AND f.ticker = r.ticker
        WHERE f.time >= '2025-01-01'
        ORDER BY f.time, f.ticker;
    """, conn)

    data["time"] = pd.to_datetime(data["time"])

    cur = conn.cursor()

    cur.execute("TRUNCATE TABLE paper_trades, paper_positions, paper_portfolio RESTART IDENTITY;")
    conn.commit()

    cash = INITIAL_CASH
    positions = {}
    closed_count = 0
    opened_count = 0

    for current_time, day_df in data.groupby("time"):
        day_df = day_df.copy()

        # 1. First check open positions for exit
        for key in list(positions.keys()):
            pos = positions[key]
            ticker = pos["ticker"]

            row = day_df[day_df["ticker"] == ticker]
            if row.empty:
                continue

            row = row.iloc[0]
            current_price = float(row["close"])
            entry_price = pos["entry_price"]
            quantity = pos["quantity"]

            pnl_pct = (current_price - entry_price) / entry_price
            pnl = (current_price - entry_price) * quantity

            close_reason = None
            if pnl_pct >= TAKE_PROFIT:
                close_reason = "TAKE_PROFIT"
            elif pnl_pct <= STOP_LOSS:
                close_reason = "STOP_LOSS"

            if close_reason:
                trade_value = current_price * quantity
                commission = trade_value * COMMISSION_RATE
                slippage = trade_value * SLIPPAGE_RATE
                cash += trade_value - commission - slippage

                cur.execute("""
                    UPDATE paper_positions
                    SET status='CLOSED',
                        exit_time=%s,
                        exit_price=%s,
                        pnl=%s,
                        pnl_pct=%s,
                        close_reason=%s
                    WHERE id=%s;
                """, (
                    current_time,
                    current_price,
                    pnl - commission - slippage,
                    pnl_pct,
                    close_reason,
                    pos["db_id"],
                ))

                cur.execute("""
                    INSERT INTO paper_trades (
                        strategy_name, ticker, signal_time, side, price,
                        quantity, commission, slippage, reason
                    )
                    VALUES (%s, %s, %s, 'SELL', %s, %s, %s, %s, %s);
                """, (
                    pos["strategy_name"],
                    ticker,
                    current_time,
                    current_price,
                    quantity,
                    commission,
                    slippage,
                    close_reason,
                ))

                del positions[key]
                closed_count += 1

        # 2. Then search for new entries
        for _, strategy in pass_df.iterrows():
            strategy_name = strategy["strategy_name"]
            ticker = strategy["ticker"]
            key = f"{strategy_name}:{ticker}"

            if key in positions:
                continue

            row = day_df[day_df["ticker"] == ticker]
            if row.empty:
                continue

            row = row.iloc[0]

            if not get_signal(strategy_name, row):
                continue

            price = float(row["close"])
            trade_value = cash * POSITION_SIZE

            if trade_value < 1000:
                continue

            commission = trade_value * COMMISSION_RATE
            slippage = trade_value * SLIPPAGE_RATE
            quantity = (trade_value - commission - slippage) / price

            cash -= trade_value

            cur.execute("""
                INSERT INTO paper_positions (
                    strategy_name, ticker, entry_time, entry_price,
                    quantity, status
                )
                VALUES (%s, %s, %s, %s, %s, 'OPEN')
                RETURNING id;
            """, (
                strategy_name,
                ticker,
                current_time,
                price,
                quantity,
            ))

            db_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO paper_trades (
                    strategy_name, ticker, signal_time, side, price,
                    quantity, commission, slippage, reason
                )
                VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s, %s);
            """, (
                strategy_name,
                ticker,
                current_time,
                price,
                quantity,
                commission,
                slippage,
                "HISTORICAL_REPLAY_SIGNAL",
            ))

            positions[key] = {
                "db_id": db_id,
                "strategy_name": strategy_name,
                "ticker": ticker,
                "entry_price": price,
                "quantity": quantity,
            }

            opened_count += 1

        # 3. Calculate equity
        equity = cash
        for pos in positions.values():
            row = day_df[day_df["ticker"] == pos["ticker"]]
            if row.empty:
                equity += pos["entry_price"] * pos["quantity"]
            else:
                equity += float(row.iloc[0]["close"]) * pos["quantity"]

        cur.execute("""
            INSERT INTO paper_portfolio (time, cash, equity, comment)
            VALUES (%s, %s, %s, %s);
        """, (
            current_time,
            cash,
            equity,
            f"historical_replay_open_positions={len(positions)}",
        ))

        conn.commit()

    cur.close()
    conn.close()

    print("Historical replay complete")
    print(f"Opened trades: {opened_count}")
    print(f"Closed trades: {closed_count}")
    print(f"Open positions left: {len(positions)}")
    print(f"Final cash: {round(cash, 2)}")


if __name__ == "__main__":
    main()