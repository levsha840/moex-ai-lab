from core.db.postgres import get_connection

VALID_STATUSES = {"candidate", "active", "watchlist", "deprecated", "graveyard"}

class StrategyLifecycleManager:
    def set_status(self, strategy_catalog_id, status, reason=""):
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE strategy_catalog
                SET status=%s,
                    notes=COALESCE(notes, '') || E'\n' || %s,
                    updated_at=now()
                WHERE id=%s;
            """, (status, reason, strategy_catalog_id))
            cur.execute("""
                INSERT INTO strategy_stage_history(strategy_catalog_id, stage, result, reason)
                VALUES (%s, 'STATUS_CHANGE', %s, %s);
            """, (strategy_catalog_id, status, reason))
            conn.commit()
        finally:
            cur.close()
            conn.close()
