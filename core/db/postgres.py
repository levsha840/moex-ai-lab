import os
import psycopg2
from contextlib import contextmanager


DEFAULT_DB_CONFIG = {
    "host": os.getenv("MOEX_DB_HOST", "localhost"),
    "port": int(os.getenv("MOEX_DB_PORT", "5432")),
    "dbname": os.getenv("MOEX_DB_NAME", "moex_ai"),
    "user": os.getenv("MOEX_DB_USER", "moex"),
    "password": os.getenv("MOEX_DB_PASSWORD", "moex_pass"),
}


def get_connection():
    return psycopg2.connect(**DEFAULT_DB_CONFIG)


@contextmanager
def db_cursor(commit: bool = False):
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
