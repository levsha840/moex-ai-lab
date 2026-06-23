CREATE TABLE IF NOT EXISTS market_regimes_daily (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    regime TEXT NOT NULL,
    volatility_score NUMERIC,
    trend_score NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, ticker)
);

SELECT create_hypertable('market_regimes_daily', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_market_regimes_ticker_time
ON market_regimes_daily (ticker, time DESC);