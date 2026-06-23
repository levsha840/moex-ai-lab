import pandas as pd
import psycopg2

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "moex_ai",
    "user": "moex",
    "password": "moex_pass",
}


def load_features(conn):
    return pd.read_sql("""
        SELECT time, ticker, close, return_20d, volatility_20d, sma_20, sma_50
        FROM features_daily
        ORDER BY ticker, time;
    """, conn)


def classify_regime(row):
    if pd.isna(row["volatility_20d"]) or pd.isna(row["return_20d"]):
        return "UNKNOWN"

    trend_up = row["close"] > row["sma_20"] > row["sma_50"]
    trend_down = row["close"] < row["sma_20"] < row["sma_50"]

    if row["volatility_20d"] > row["vol_threshold"]:
        return "HIGH_VOLATILITY"

    if trend_up and row["return_20d"] > 0:
        return "TREND_UP"

    if trend_down and row["return_20d"] < 0:
        return "TREND_DOWN"

    return "RANGE"


def save_regimes(conn, df):
    sql = """
    INSERT INTO market_regimes_daily (
        time, ticker, regime, volatility_score, trend_score
    )
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (time, ticker)
    DO UPDATE SET
        regime = EXCLUDED.regime,
        volatility_score = EXCLUDED.volatility_score,
        trend_score = EXCLUDED.trend_score;
    """

    rows = []
    for _, r in df.iterrows():
        rows.append((
            r["time"],
            r["ticker"],
            r["regime"],
            r["volatility_20d"],
            r["return_20d"],
        ))

    with conn.cursor() as cur:
        cur.executemany(sql, rows)

    conn.commit()


def print_summary(df):
    print("\n=== Regime count ===")
    print(df.groupby(["ticker", "regime"]).size().unstack(fill_value=0))

    print("\n=== Volatility ranking ===")
    ranking = (
        df.groupby("ticker")["volatility_20d"]
        .mean()
        .sort_values(ascending=False)
    )
    print(ranking)


def main():
    conn = psycopg2.connect(**DB)

    try:
        df = load_features(conn)

        all_parts = []

        for ticker, part in df.groupby("ticker"):
            part = part.copy()
            part = part.sort_values("time")

            part["vol_threshold"] = part["volatility_20d"].rolling(120, min_periods=30).quantile(0.80)
            part["regime"] = part.apply(classify_regime, axis=1)

            all_parts.append(part)

        result = pd.concat(all_parts)
        result = result.where(pd.notnull(result), None)

        save_regimes(conn, result)
        print_summary(result)

        print(f"\nSaved regimes: {len(result)} rows")

    finally:
        conn.close()


if __name__ == "__main__":
    main()