CREATE TABLE IF NOT EXISTS signal_journal (
 id SERIAL PRIMARY KEY,
 strategy_catalog_id INTEGER,
 strategy_name TEXT NOT NULL,
 ticker TEXT NOT NULL,
 signal_time TIMESTAMPTZ NOT NULL,
 action TEXT NOT NULL,
 confidence DOUBLE PRECISION,
 reason TEXT,
 mode TEXT NOT NULL DEFAULT 'unknown',
 created_at TIMESTAMPTZ DEFAULT now()
);
