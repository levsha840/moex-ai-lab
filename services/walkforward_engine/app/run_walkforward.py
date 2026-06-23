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
    return pd.read_sql("""
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
    """, conn)


def max_drawdown(equity):
    peak = equity.cummax()
    dd = equity / peak - 1
    return float(dd.min()) if len(dd) else 0.0


def backtest(df, signal):
    if df.empty:
        return {"total_return": 0.0, "sharpe": 0.0, "mdd": 0.0, "trades": 0}

    df = df.copy()
    df["position"] = signal.shift(1).fillna(False).astype(int)
    df["strategy_return"] = df["position"] * df["return_1d"]

    equity = (1 + df["strategy_return"].fillna(0)).cumprod()

    total_return = float(equity.iloc[-1] - 1)
    mdd = max_drawdown(equity)

    std = df["strategy_return"].std()
    sharpe = float(df["strategy_return"].mean() / std * np.sqrt(252)) if std and std > 0 else 0.0

    trades = int((df["position"].diff().abs() == 1).sum())

    return {
        "total_return": total_return,
        "sharpe": sharpe,
        "mdd": mdd,
        "trades": trades,
    }


def get_strategies():
    return [
        {
            "name": "RSI_OVERSOLD_NOT_DOWNTREND",
            "params": {"rsi_less": 30, "exclude_regime": "TREND_DOWN"},
            "signal": lambda d: (d["rsi_14"] < 30) & (d["regime"] != "TREND_DOWN"),
        },
        {
            "name": "RSI_25_MOMENTUM_POSITIVE",
            "params": {"rsi_less": 25, "momentum_20_more": 0},
            "signal": lambda d: (d["rsi_14"] < 25) & (d["momentum_20"] > 0),
        },
        {
            "name": "TREND_UP_SMA_CONFIRM",
            "params": {"close_above_sma50": True, "regime": "TREND_UP"},
            "signal": lambda d: (d["close"] > d["sma_50"]) & (d["regime"] == "TREND_UP"),
        },
    ]


def verdict(train, val, oos):
    reasons = []

    if train["trades"] < 4:
        reasons.append("too_few_train_trades")
    if val["trades"] < 2:
        reasons.append("too_few_validation_trades")
    if oos["trades"] < 1:
        reasons.append("too_few_oos_trades")

    if train["sharpe"] <= 0:
        reasons.append("bad_train_sharpe")
    if val["sharpe"] <= 0:
        reasons.append("bad_validation_sharpe")
    if oos["sharpe"] <= 0:
        reasons.append("bad_oos_sharpe")

    if val["total_return"] < -0.05:
        reasons.append("validation_loss_too_large")
    if oos["total_return"] < -0.05:
        reasons.append("oos_loss_too_large")

    if oos["mdd"] < -0.25:
        reasons.append("oos_drawdown_too_large")

    if reasons:
        return "FAIL", ",".join(reasons)

    return "PASS", "stable_enough_v1"


def save_result(conn, strategy_name, ticker, train, val, oos, verdict_value, reason, params):
    sql = """
    INSERT INTO strategy_validation_results (
        strategy_name, ticker,
        train_return, train_sharpe, train_mdd,
        validation_return, validation_sharpe, validation_mdd,
        oos_return, oos_sharpe, oos_mdd,
        verdict, reason, params
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    with conn.cursor() as cur:
        cur.execute(sql, (
            strategy_name,
            ticker,
            train["total_return"], train["sharpe"], train["mdd"],
            val["total_return"], val["sharpe"], val["mdd"],
            oos["total_return"], oos["sharpe"], oos["mdd"],
            verdict_value,
            reason,
            json.dumps(params),
        ))

    conn.commit()


def save_graveyard(conn, strategy_name, ticker, reason, params):
    sql = """
    INSERT INTO strategy_graveyard (
        strategy_name, reason, market_regime, metrics
    )
    VALUES (%s, %s, %s, %s);
    """

    with conn.cursor() as cur:
        cur.execute(sql, (
            f"{strategy_name}:{ticker}",
            reason,
            "WALK_FORWARD_FAIL",
            json.dumps(params),
        ))

    conn.commit()


def main():
    conn = psycopg2.connect(**DB)

    try:
        df = load_data(conn)
        df["time"] = pd.to_datetime(df["time"])

        strategies = get_strategies()

        # чистим старые результаты, чтобы не копить дубли
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE strategy_validation_results;")
            conn.commit()

        for ticker, part in df.groupby("ticker"):
            part = part.copy().sort_values("time")

            train_df = part[part["time"] < "2025-01-01"]
            val_df = part[(part["time"] >= "2025-01-01") & (part["time"] < "2026-01-01")]
            oos_df = part[part["time"] >= "2026-01-01"]

            print(f"\nTicker: {ticker}")
            print(f"rows train={len(train_df)}, val={len(val_df)}, oos={len(oos_df)}")

            for s in strategies:
                train_signal = s["signal"](train_df)
                val_signal = s["signal"](val_df)
                oos_signal = s["signal"](oos_df)

                train_metrics = backtest(train_df, train_signal)
                val_metrics = backtest(val_df, val_signal)
                oos_metrics = backtest(oos_df, oos_signal)

                v, reason = verdict(train_metrics, val_metrics, oos_metrics)

                save_result(
                    conn,
                    s["name"],
                    ticker,
                    train_metrics,
                    val_metrics,
                    oos_metrics,
                    v,
                    reason,
                    s["params"],
                )

                if v == "FAIL":
                    save_graveyard(conn, s["name"], ticker, reason, s["params"])

                print(
                    s["name"],
                    v,
                    "train_sharpe=", round(train_metrics["sharpe"], 3),
                    "val_sharpe=", round(val_metrics["sharpe"], 3),
                    "oos_sharpe=", round(oos_metrics["sharpe"], 3),
                    "reason=", reason,
                )

    finally:
        conn.close()


if __name__ == "__main__":
    main()