import time
import requests
import psycopg2
from datetime import datetime, timedelta, timezone

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "moex_ai",
    "user": "moex",
    "password": "moex_pass",
}

TICKERS = ["AFKS", "MTLR", "OZON", "VKCO", "SMLT", "PIKK", "RNFT", "WUSH", "SELG", "MBNK"]

def fetch_candles(ticker: str, start: str, end: str, retries: int = 5):
    url = f"https://iss.moex.com/iss/engines/stock/markets/shares/securities/{ticker}/candles.json"
    params = {"from": start, "till": end, "interval": 24}

    for attempt in range(1, retries + 1):
        try:
            print(f"{ticker}: request attempt {attempt}/{retries}")
            r = requests.get(url, params=params, timeout=90)
            r.raise_for_status()

            data = r.json()["candles"]
            columns = data["columns"]
            rows = data["data"]

            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            print(f"{ticker}: error on attempt {attempt}: {e}")
            if attempt < retries:
                time.sleep(10 * attempt)
            else:
                print(f"{ticker}: skipped after {retries} failed attempts")
                return []

def save_candles(conn, ticker: str, candles):
    if not candles:
        return

    sql = """
    INSERT INTO candles (time, ticker, timeframe, open, high, low, close, volume, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (time, ticker, timeframe)
    DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume,
        source = EXCLUDED.source;
    """

    with conn.cursor() as cur:
        for c in candles:
            cur.execute(sql, (
                c["begin"],
                ticker,
                "1D",
                c["open"],
                c["high"],
                c["low"],
                c["close"],
                c["volume"],
                "MOEX_ISS",
            ))
    conn.commit()

def main():
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=365 * 3)

    print(f"Loading MOEX candles from {start} to {end}")
    conn = psycopg2.connect(**DB)

    try:
        for ticker in TICKERS:
            print("=" * 60)
            print(f"Loading {ticker}...")
            candles = fetch_candles(ticker, str(start), str(end))
            save_candles(conn, ticker, candles)
            print(f"{ticker}: saved {len(candles)} candles")
            time.sleep(2)
    finally:
        conn.close()

if __name__ == "__main__":
    main()