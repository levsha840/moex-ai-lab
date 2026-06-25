from core.db.postgres import get_connection


VALID_STATUSES = {
    "candidate",
    "active",
    "watchlist",
    "deprecated",
    "graveyard",
}


class StrategyLifecycleManager:
    def set_status(self, strategy_catalog_id: int, status: str, reason: str = "") -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid strategy status: {status}")

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE strategy_catalog
                SET status = %s,
                    notes = COALESCE(notes, '') || E'\n' || %s,
                    updated_at = now()
                WHERE id = %s;
            """, (status, reason, strategy_catalog_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
