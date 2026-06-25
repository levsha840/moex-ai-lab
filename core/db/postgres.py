import psycopg2
from contextlib import contextmanager
from core.config.settings import DB_SETTINGS

DEFAULT_DB_CONFIG = {
    "host": DB_SETTINGS.host,
    "port": DB_SETTINGS.port,
    "dbname": DB_SETTINGS.dbname,
    "user": DB_SETTINGS.user,
    "password": DB_SETTINGS.password,
}

def get_connection():
    return psycopg2.connect(**DEFAULT_DB_CONFIG)

@contextmanager
def db_cursor(commit=False):
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
