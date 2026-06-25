import pandas as pd
from core.db.postgres import get_connection

class MarketDataRepository:
    def load_daily_features_with_regimes(self, start_date="2025-01-01"):
        conn = get_connection()
        try:
            data = pd.read_sql("""
                SELECT f.time, f.ticker, f.close, f.rsi_14, f.sma_50, r.regime
                FROM features_daily f
                JOIN market_regimes_daily r ON f.time=r.time AND f.ticker=r.ticker
                WHERE f.time >= %s
                ORDER BY f.time, f.ticker;
            """, conn, params=(start_date,))
            data["time"] = pd.to_datetime(data["time"])
            return data
        finally:
            conn.close()
