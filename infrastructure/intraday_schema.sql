CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS candles_intraday (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    timeframe TEXT NOT NULL DEFAULT '1m',
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'MOEX',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (time, ticker, timeframe, source)
);

SELECT create_hypertable('candles_intraday', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_candles_intraday_ticker_time
ON candles_intraday (ticker, time DESC);

CREATE INDEX IF NOT EXISTS idx_candles_intraday_timeframe_time
ON candles_intraday (timeframe, time DESC);
