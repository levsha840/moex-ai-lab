import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pandas as pd
import psycopg2

from core.db.postgres import DEFAULT_DB_CONFIG
from core.strategy.catalog import StrategyCatalog
from core.strategy.registry import StrategyRegistry
from core.execution.replay_execution_engine import ReplayExecutionEngine
from core.portfolio.portfolio import Portfolio
from core.portfolio.position import Position
from core.risk.risk_manager import RiskManager


def load_market_data(conn):
    data = pd.read_sql("""
        SELECT
            f.time,
            f.ticker,
            f.close,
            f.rsi_14,
            f.sma_50,
            r.regime
        FROM features_daily f
        JOIN market_regimes_daily r
          ON f.time = r.time AND f.ticker = r.ticker
        WHERE f.time >= '2025-01-01'
        ORDER BY f.time, f.ticker;
    """, conn)

    data["time"] = pd.to_datetime(data["time"])
    return data


def main():
    conn = psycopg2.connect(**DEFAULT_DB_CONFIG)

    catalog = StrategyCatalog()
    active_strategies = catalog.get_active_strategies()

    registry = StrategyRegistry()
    execution = ReplayExecutionEngine()
    portfolio = Portfolio(initial_cash=execution.initial_cash)
    risk = RiskManager(
        max_open_positions=10,
        max_positions_per_ticker=2,
        min_trade_value=1000,
        max_cash_usage=0.95,
        min_cash_buffer=10_000,
    )

    data = load_market_data(conn)
    cur = conn.cursor()

    cur.execute("TRUNCATE TABLE paper_trades, paper_positions, paper_portfolio RESTART IDENTITY;")
    conn.commit()

    closed_count = 0
    opened_count = 0
    rejected_count = 0

    for current_time, day_df in data.groupby("time"):
        day_df = day_df.copy()

        # 1. Close existing positions
        for key, pos in list(portfolio.open_positions()):
            row = day_df[day_df["ticker"] == pos.ticker]
            if row.empty:
                continue

            row = row.iloc[0]
            current_price = float(row["close"])
            entry_price = pos.entry_price
            quantity = pos.quantity

            should_close, close_reason, pnl_pct = execution.should_close(entry_price, current_price)

            if should_close:
                exit_calc = execution.calculate_exit(current_price, entry_price, quantity)

                portfolio.release_cash(
                    exit_calc["trade_value"] - exit_calc["commission"] - exit_calc["slippage"]
                )

                cur.execute("""
                    UPDATE paper_positions
                    SET status='CLOSED',
                        exit_time=%s,
                        exit_price=%s,
                        pnl=%s,
                        pnl_pct=%s,
                        close_reason=%s
                    WHERE id=%s;
                """, (
                    current_time,
                    current_price,
                    exit_calc["pnl"],
                    exit_calc["pnl_pct"],
                    close_reason,
                    pos.db_id,
                ))

                cur.execute("""
                    INSERT INTO paper_trades (
                        strategy_name, ticker, signal_time, side, price,
                        quantity, commission, slippage, reason
                    )
                    VALUES (%s, %s, %s, 'SELL', %s, %s, %s, %s, %s);
                """, (
                    pos.strategy_name,
                    pos.ticker,
                    current_time,
                    current_price,
                    quantity,
                    exit_calc["commission"],
                    exit_calc["slippage"],
                    close_reason,
                ))

                portfolio.remove_position(pos.strategy_name, pos.ticker)
                closed_count += 1

        # 2. Open new positions
        for _, strategy_row in active_strategies.iterrows():
            strategy_name = strategy_row["strategy_name"]
            ticker = strategy_row["ticker"]

            row = day_df[day_df["ticker"] == ticker]
            if row.empty:
                continue

            row = row.iloc[0]
            strategy = registry.get(strategy_name)
            signal = strategy.generate_signal(row)

            if signal.action != "BUY":
                continue

            price = float(row["close"])
            trade_value = execution.estimate_trade_value(portfolio.cash)

            allowed, risk_reason = risk.can_open_position(
                portfolio=portfolio,
                strategy_name=strategy_name,
                ticker=ticker,
                trade_value=trade_value,
            )

            if not allowed:
                rejected_count += 1
                continue

            entry_calc = execution.calculate_entry(trade_value, price)
            if entry_calc is None:
                rejected_count += 1
                continue

            portfolio.reserve_cash(entry_calc["trade_value"])

            cur.execute("""
                INSERT INTO paper_positions (
                    strategy_name, ticker, entry_time, entry_price,
                    quantity, status
                )
                VALUES (%s, %s, %s, %s, %s, 'OPEN')
                RETURNING id;
            """, (
                strategy_name,
                ticker,
                current_time,
                price,
                entry_calc["quantity"],
            ))

            db_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO paper_trades (
                    strategy_name, ticker, signal_time, side, price,
                    quantity, commission, slippage, reason
                )
                VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s, %s);
            """, (
                strategy_name,
                ticker,
                current_time,
                price,
                entry_calc["quantity"],
                entry_calc["commission"],
                entry_calc["slippage"],
                signal.reason,
            ))

            portfolio.add_position(Position(
                strategy_name=strategy_name,
                ticker=ticker,
                entry_time=current_time,
                entry_price=price,
                quantity=entry_calc["quantity"],
                db_id=db_id,
            ))

            opened_count += 1

        # 3. Equity
        equity = portfolio.calculate_equity(day_df)

        cur.execute("""
            INSERT INTO paper_portfolio (time, cash, equity, comment)
            VALUES (%s, %s, %s, %s);
        """, (
            current_time,
            portfolio.cash,
            equity,
            f"historical_replay_core_risk_open_positions={portfolio.count_open_positions()}",
        ))

        conn.commit()

    cur.close()
    conn.close()

    print("Historical replay core+risk complete")
    print(f"Opened trades: {opened_count}")
    print(f"Closed trades: {closed_count}")
    print(f"Rejected signals: {rejected_count}")
    print(f"Open positions left: {portfolio.count_open_positions()}")
    print(f"Final cash: {round(portfolio.cash, 2)}")


if __name__ == "__main__":
    main()
