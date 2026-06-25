CREATE TABLE IF NOT EXISTS strategy_stage_history (
 id SERIAL PRIMARY KEY,
 strategy_catalog_id INTEGER REFERENCES strategy_catalog(id),
 stage TEXT NOT NULL,
 result TEXT NOT NULL,
 reason TEXT,
 metrics JSONB DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ DEFAULT now()
);
