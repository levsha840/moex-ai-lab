CREATE TABLE IF NOT EXISTS paper_positions (
    id SERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    entry_price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    status TEXT DEFAULT 'OPEN',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id SERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    signal_time TIMESTAMPTZ NOT NULL,
    side TEXT NOT NULL,
    price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    commission NUMERIC DEFAULT 0,
    slippage NUMERIC DEFAULT 0,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_portfolio (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    cash NUMERIC NOT NULL,
    equity NUMERIC NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);