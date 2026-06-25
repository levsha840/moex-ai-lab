CREATE TABLE IF NOT EXISTS strategy_stage_history (
    id SERIAL PRIMARY KEY,
    strategy_catalog_id INTEGER REFERENCES strategy_catalog(id),

    stage TEXT NOT NULL,
    result TEXT NOT NULL,
    reason TEXT,

    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ DEFAULT now(),

    metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);
