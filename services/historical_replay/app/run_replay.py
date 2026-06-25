import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.append(str(ROOT))

from core.db.postgres import get_connection
from core.strategy.catalog import StrategyCatalog
from core.strategy.registry import StrategyRegistry
from core.execution.replay_execution_engine import ReplayExecutionEngine
from core.portfolio.portfolio import Portfolio
from core.portfolio.position import Position
from core.risk.risk_manager import RiskManager
from core.market.market_data import MarketDataRepository

def main():
    conn = get_connection()
    cur = conn.cursor()
    active = StrategyCatalog().get_active_strategies()
    registry = StrategyRegistry()
    execution = ReplayExecutionEngine()
    portfolio = Portfolio(execution.initial_cash)
    risk = RiskManager()
    data = MarketDataRepository().load_daily_features_with_regimes("2025-01-01")
    cur.execute("TRUNCATE TABLE paper_trades, paper_positions, paper_portfolio RESTART IDENTITY;")
    conn.commit()
    opened = closed = rejected = 0
    for current_time, day_df in data.groupby("time"):
        day_df = day_df.copy()
        for _, pos in list(portfolio.open_positions()):
            row = day_df[day_df["ticker"] == pos.ticker]
            if row.empty: continue
            row = row.iloc[0]; price = float(row["close"])
            should_close, reason, _ = execution.should_close(pos.entry_price, price)
            if not should_close: continue
            ex = execution.calculate_exit(price, pos.entry_price, pos.quantity)
            portfolio.release_cash(ex["trade_value"] - ex["commission"] - ex["slippage"])
            cur.execute("""
                UPDATE paper_positions SET status='CLOSED', exit_time=%s, exit_price=%s, pnl=%s, pnl_pct=%s, close_reason=%s WHERE id=%s;
            """, (current_time, price, ex["pnl"], ex["pnl_pct"], reason, pos.db_id))
            cur.execute("""
                INSERT INTO paper_trades(strategy_name,ticker,signal_time,side,price,quantity,commission,slippage,reason)
                VALUES (%s,%s,%s,'SELL',%s,%s,%s,%s,%s);
            """, (pos.strategy_name, pos.ticker, current_time, price, pos.quantity, ex["commission"], ex["slippage"], reason))
            portfolio.remove_position(pos.strategy_name, pos.ticker); closed += 1
        for _, srow in active.iterrows():
            strategy_name = srow["strategy_name"]; ticker = srow["ticker"]
            row = day_df[day_df["ticker"] == ticker]
            if row.empty: continue
            row = row.iloc[0]
            signal = registry.get(strategy_name).generate_signal(row)
            if signal.action != "BUY": continue
            price = float(row["close"]); trade_value = execution.estimate_trade_value(portfolio.cash)
            allowed, rr = risk.can_open_position(portfolio, strategy_name, ticker, trade_value)
            if not allowed: rejected += 1; continue
            en = execution.calculate_entry(trade_value, price)
            if en is None: rejected += 1; continue
            portfolio.reserve_cash(en["trade_value"])
            cur.execute("""
                INSERT INTO paper_positions(strategy_name,ticker,entry_time,entry_price,quantity,status)
                VALUES (%s,%s,%s,%s,%s,'OPEN') RETURNING id;
            """, (strategy_name, ticker, current_time, price, en["quantity"]))
            db_id = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO paper_trades(strategy_name,ticker,signal_time,side,price,quantity,commission,slippage,reason)
                VALUES (%s,%s,%s,'BUY',%s,%s,%s,%s,%s);
            """, (strategy_name, ticker, current_time, price, en["quantity"], en["commission"], en["slippage"], signal.reason))
            portfolio.add_position(Position(strategy_name, ticker, current_time, price, en["quantity"], db_id)); opened += 1
        equity = portfolio.calculate_equity(day_df)
        cur.execute("INSERT INTO paper_portfolio(time,cash,equity,comment) VALUES (%s,%s,%s,%s);", (current_time, portfolio.cash, equity, f"v1_open_positions={portfolio.count_open_positions()}"))
        conn.commit()
    cur.close(); conn.close()
    print("MOEX AI LAB v1 replay complete")
    print(f"Opened trades: {opened}")
    print(f"Closed trades: {closed}")
    print(f"Rejected signals: {rejected}")
    print(f"Open positions left: {portfolio.count_open_positions()}")
    print(f"Final cash: {round(portfolio.cash, 2)}")

if __name__ == "__main__":
    main()
