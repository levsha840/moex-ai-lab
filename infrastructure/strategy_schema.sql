CREATE TABLE IF NOT EXISTS strategy_results (
    id SERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    total_return NUMERIC,
    trades_count INTEGER,
    win_rate NUMERIC,
    max_drawdown NUMERIC,
    sharpe_ratio NUMERIC,
    regime_filter TEXT,
    params JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_results_score
ON strategy_results (total_return DESC);