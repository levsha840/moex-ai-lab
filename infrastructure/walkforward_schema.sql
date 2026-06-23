CREATE TABLE IF NOT EXISTS strategy_validation_results (
    id SERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    ticker TEXT NOT NULL,

    train_return NUMERIC,
    train_sharpe NUMERIC,
    train_mdd NUMERIC,

    validation_return NUMERIC,
    validation_sharpe NUMERIC,
    validation_mdd NUMERIC,

    oos_return NUMERIC,
    oos_sharpe NUMERIC,
    oos_mdd NUMERIC,

    verdict TEXT NOT NULL,
    reason TEXT,
    params JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_validation_verdict
ON strategy_validation_results (verdict, oos_sharpe DESC);