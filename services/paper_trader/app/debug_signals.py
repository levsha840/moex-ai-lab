import pandas as pd
import psycopg2

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "moex_ai",
    "user": "moex",
    "password": "moex_pass",
}

def get_signal(strategy_name, row):
    if strategy_name == "RSI_OVERSOLD_NOT_DOWNTREND":
        return row["rsi_14"] < 30 and row["regime"] != "TREND_DOWN"

    if strategy_name == "TREND_UP_SMA_CONFIRM":
        return row["close"] > row["sma_50"] and row["regime"] == "TREND_UP"

    return False

conn = psycopg2.connect(**DB)

pass_df = pd.read_sql("""
    SELECT strategy_name, ticker
    FROM strategy_validation_results
    WHERE verdict = 'PASS'
    ORDER BY ticker, strategy_name;
""", conn)

data = pd.read_sql("""
    SELECT DISTINCT ON (f.ticker)
        f.time, f.ticker, f.close, f.rsi_14, f.sma_50, r.regime
    FROM features_daily f
    JOIN market_regimes_daily r
      ON f.time = r.time AND f.ticker = r.ticker
    ORDER BY f.ticker, f.time DESC;
""", conn)

for _, s in pass_df.iterrows():
    latest = data[data["ticker"] == s["ticker"]].iloc[0]
    signal = get_signal(s["strategy_name"], latest)

    print(
        s["ticker"],
        s["strategy_name"],
        "time=", latest["time"],
        "close=", round(float(latest["close"]), 2),
        "rsi=", round(float(latest["rsi_14"]), 2),
        "sma50=", round(float(latest["sma_50"]), 2),
        "regime=", latest["regime"],
        "SIGNAL=", signal
    )

conn.close()