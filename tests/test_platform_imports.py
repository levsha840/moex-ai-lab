from core.db.postgres import DEFAULT_DB_CONFIG
from core.strategy.registry import StrategyRegistry
from core.execution.replay_execution_engine import ReplayExecutionEngine
from core.broker.adapters import LiveBroker

def main():
    assert DEFAULT_DB_CONFIG["dbname"]
    assert StrategyRegistry().names()
    assert ReplayExecutionEngine().initial_cash == 1_000_000
    assert LiveBroker().place_order("TEST","BUY",1,100)["status"] == "BLOCKED"
    print("Platform imports OK")

if __name__ == "__main__":
    main()
