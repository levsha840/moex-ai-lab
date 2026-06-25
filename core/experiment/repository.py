import json
from core.db.postgres import get_connection

class ExperimentRepository:
    def create(self, name, experiment_type, config):
        conn = get_connection(); cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO experiments(name, experiment_type, status, config, started_at)
                VALUES (%s, %s, 'running', %s::jsonb, now())
                RETURNING id;
            """, (name, experiment_type, json.dumps(config)))
            eid = cur.fetchone()[0]
            conn.commit()
            return eid
        finally:
            cur.close(); conn.close()

    def finish(self, experiment_id, metrics, status="finished"):
        conn = get_connection(); cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE experiments SET status=%s, metrics=%s::jsonb, finished_at=now()
                WHERE id=%s;
            """, (status, json.dumps(metrics), experiment_id))
            conn.commit()
        finally:
            cur.close(); conn.close()
