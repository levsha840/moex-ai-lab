CREATE TABLE IF NOT EXISTS experiments (
 id SERIAL PRIMARY KEY,
 name TEXT NOT NULL,
 experiment_type TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'created',
 config JSONB DEFAULT '{}'::jsonb,
 metrics JSONB DEFAULT '{}'::jsonb,
 started_at TIMESTAMPTZ,
 finished_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ DEFAULT now()
);
