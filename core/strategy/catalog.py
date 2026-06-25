import pandas as pd
from core.db.postgres import get_connection


class StrategyCatalog:
    def get_active_strategies(self) -> pd.DataFrame:
        conn = get_connection()
        try:
            return pd.read_sql("""
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
        finally:
            conn.close()

    def update_replay_stats(self, stats: pd.DataFrame) -> None:
        conn = get_connection()
        cur = conn.cursor()
        try:
            for _, row in stats.iterrows():
                cur.execute("""
                    UPDATE strategy_catalog
                    SET
                        last_replay = now(),
                        replay_trades = %s,
                        replay_win_rate = %s,
                        replay_profit_factor = %s,
                        replay_expectancy = %s,
                        replay_total_pnl = %s,
                        updated_at = now()
                    WHERE strategy_name = %s
                      AND ticker = %s
                      AND status = 'active';
                """, (
                    int(row["replay_trades"]),
                    float(row["replay_win_rate"]),
                    float(row["replay_profit_factor"]),
                    float(row["replay_expectancy"]),
                    float(row["replay_total_pnl"]),
                    row["strategy_name"],
                    row["ticker"],
                ))

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
