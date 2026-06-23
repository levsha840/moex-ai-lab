CREATE TABLE IF NOT EXISTS features_daily (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,

    close NUMERIC,
    volume NUMERIC,

    return_1d NUMERIC,
    return_5d NUMERIC,
    return_20d NUMERIC,

    volatility_5d NUMERIC,
    volatility_20d NUMERIC,

    sma_10 NUMERIC,
    sma_20 NUMERIC,
    sma_50 NUMERIC,

    rsi_14 NUMERIC,
    atr_14 NUMERIC,

    momentum_10 NUMERIC,
    momentum_20 NUMERIC,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (time, ticker)
);

SELECT create_hypertable('features_daily', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_features_daily_ticker_time
ON features_daily (ticker, time DESC);