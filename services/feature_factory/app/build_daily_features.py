import pandas as pd
import psycopg2

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "moex_ai",
    "user": "moex",
    "password": "moex_pass",
}


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def load_candles(conn) -> pd.DataFrame:
    query = """
        SELECT time, ticker, open, high, low, close, volume
        FROM candles
        WHERE timeframe = '1D'
        ORDER BY ticker, time;
    """
    return pd.read_sql(query, conn)


def save_features(conn, df: pd.DataFrame):
    sql = """
    INSERT INTO features_daily (
        time, ticker, close, volume,
        return_1d, return_5d, return_20d,
        volatility_5d, volatility_20d,
        sma_10, sma_20, sma_50,
        rsi_14, atr_14,
        momentum_10, momentum_20
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (time, ticker)
    DO UPDATE SET
        close = EXCLUDED.close,
        volume = EXCLUDED.volume,
        return_1d = EXCLUDED.return_1d,
        return_5d = EXCLUDED.return_5d,
        return_20d = EXCLUDED.return_20d,
        volatility_5d = EXCLUDED.volatility_5d,
        volatility_20d = EXCLUDED.volatility_20d,
        sma_10 = EXCLUDED.sma_10,
        sma_20 = EXCLUDED.sma_20,
        sma_50 = EXCLUDED.sma_50,
        rsi_14 = EXCLUDED.rsi_14,
        atr_14 = EXCLUDED.atr_14,
        momentum_10 = EXCLUDED.momentum_10,
        momentum_20 = EXCLUDED.momentum_20;
    """

    rows = []
    for _, r in df.iterrows():
        rows.append((
            r["time"], r["ticker"], r["close"], r["volume"],
            r["return_1d"], r["return_5d"], r["return_20d"],
            r["volatility_5d"], r["volatility_20d"],
            r["sma_10"], r["sma_20"], r["sma_50"],
            r["rsi_14"], r["atr_14"],
            r["momentum_10"], r["momentum_20"],
        ))

    with conn.cursor() as cur:
        cur.executemany(sql, rows)

    conn.commit()


def main():
    conn = psycopg2.connect(**DB)

    try:
        candles = load_candles(conn)

        all_features = []

        for ticker, df in candles.groupby("ticker"):
            print(f"Building features for {ticker}")

            df = df.copy()
            df = df.sort_values("time")

            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df["return_1d"] = df["close"].pct_change(1)
            df["return_5d"] = df["close"].pct_change(5)
            df["return_20d"] = df["close"].pct_change(20)

            df["volatility_5d"] = df["return_1d"].rolling(5).std()
            df["volatility_20d"] = df["return_1d"].rolling(20).std()

            df["sma_10"] = df["close"].rolling(10).mean()
            df["sma_20"] = df["close"].rolling(20).mean()
            df["sma_50"] = df["close"].rolling(50).mean()

            df["rsi_14"] = rsi(df["close"], 14)
            df["atr_14"] = atr(df, 14)

            df["momentum_10"] = df["close"] / df["close"].shift(10) - 1
            df["momentum_20"] = df["close"] / df["close"].shift(20) - 1

            feature_cols = [
                "time", "ticker", "close", "volume",
                "return_1d", "return_5d", "return_20d",
                "volatility_5d", "volatility_20d",
                "sma_10", "sma_20", "sma_50",
                "rsi_14", "atr_14",
                "momentum_10", "momentum_20",
            ]

            all_features.append(df[feature_cols])

        result = pd.concat(all_features)
        result = result.where(pd.notnull(result), None)

        save_features(conn, result)

        print(f"Saved features: {len(result)} rows")

    finally:
        conn.close()


if __name__ == "__main__":
    main()