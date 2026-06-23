CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS instruments (
    id SERIAL PRIMARY KEY,
    ticker TEXT UNIQUE NOT NULL,
    name TEXT,
    asset_type TEXT NOT NULL,
    exchange TEXT DEFAULT 'MOEX',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS candles (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, ticker, timeframe)
);

SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_candles_ticker_time
ON candles (ticker, time DESC);

CREATE TABLE IF NOT EXISTS strategy_graveyard (
    id SERIAL PRIMARY KEY,
    strategy_name TEXT,
    reason TEXT,
    market_regime TEXT,
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);