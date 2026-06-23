import json
import numpy as np
import pandas as pd
import psycopg2

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "moex_ai",
    "user": "moex",
    "password": "moex_pass",
}


def load_data(conn):
    query = """
        SELECT
            f.time,
            f.ticker,
            f.close,
            f.rsi_14,
            f.return_1d,
            f.momentum_20,
            f.sma_20,
            f.sma_50,
            r.regime
        FROM features_daily f
        JOIN market_regimes_daily r
          ON f.time = r.time AND f.ticker = r.ticker
        WHERE f.rsi_14 IS NOT NULL
          AND f.return_1d IS NOT NULL
          AND f.sma_50 IS NOT NULL
        ORDER BY f.ticker, f.time;
    """
    return pd.read_sql(query, conn)


def max_drawdown(equity):
    peak = equity.cummax()
    dd = equity / peak - 1
    return dd.min()


def backtest(df, signal):
    df = df.copy()
    df["position"] = signal.shift(1).fillna(False).astype(int)
    df["strategy_return"] = df["position"] * df["return_1d"]

    equity = (1 + df["strategy_return"].fillna(0)).cumprod()

    total_return = equity.iloc[-1] - 1
    mdd = max_drawdown(equity)

    trades = (df["position"].diff().abs() == 1).sum()
    wins = (df.loc[df["position"] == 1, "strategy_return"] > 0).sum()
    active_days = (df["position"] == 1).sum()
    win_rate = wins / active_days if active_days > 0 else 0

    std = df["strategy_return"].std()
    sharpe = (df["strategy_return"].mean() / std * np.sqrt(252)) if std and std > 0 else 0

    return {
        "total_return": float(total_return),
        "trades_count": int(trades),
        "win_rate": float(win_rate),
        "max_drawdown": float(mdd),
        "sharpe_ratio": float(sharpe),
    }


def save_result(conn, strategy_name, ticker, metrics, regime_filter, params):
    sql = """
    INSERT INTO strategy_results (
        strategy_name, ticker, total_return, trades_count,
        win_rate, max_drawdown, sharpe_ratio, regime_filter, params
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    with conn.cursor() as cur:
        cur.execute(sql, (
            strategy_name,
            ticker,
            metrics["total_return"],
            metrics["trades_count"],
            metrics["win_rate"],
            metrics["max_drawdown"],
            metrics["sharpe_ratio"],
            regime_filter,
            json.dumps(params),
        ))
    conn.commit()


def main():
    conn = psycopg2.connect(**DB)

    strategies = [
        {
            "name": "RSI_OVERSOLD_NOT_DOWNTREND",
            "params": {"rsi_less": 30, "exclude_regime": "TREND_DOWN"},
            "signal": lambda d: (d["rsi_14"] < 30) & (d["regime"] != "TREND_DOWN"),
            "regime_filter": "NOT TREND_DOWN",
        },
        {
            "name": "RSI_25_MOMENTUM_POSITIVE",
            "params": {"rsi_less": 25, "momentum_20_more": 0},
            "signal": lambda d: (d["rsi_14"] < 25) & (d["momentum_20"] > 0),
            "regime_filter": "ANY",
        },
        {
            "name": "TREND_UP_SMA_CONFIRM",
            "params": {"close_above_sma50": True, "regime": "TREND_UP"},
            "signal": lambda d: (d["close"] > d["sma_50"]) & (d["regime"] == "TREND_UP"),
            "regime_filter": "TREND_UP",
        },
    ]

    try:
        df = load_data(conn)

        for ticker, part in df.groupby("ticker"):
            part = part.copy().sort_values("time")
            print(f"\nTicker: {ticker}")

            for s in strategies:
                signal = s["signal"](part)
                metrics = backtest(part, signal)

                save_result(
                    conn,
                    s["name"],
                    ticker,
                    metrics,
                    s["regime_filter"],
                    s["params"],
                )

                print(
                    s["name"],
                    "return=", round(metrics["total_return"], 4),
                    "sharpe=", round(metrics["sharpe_ratio"], 4),
                    "mdd=", round(metrics["max_drawdown"], 4),
                    "trades=", metrics["trades_count"],
                )

    finally:
        conn.close()


if __name__ == "__main__":
    main()