from core.db.postgres import DEFAULT_DB_CONFIG
from core.strategy.registry import StrategyRegistry
from core.execution.replay_execution_engine import ReplayExecutionEngine
from core.analytics.metrics import profit_factor


def main():
    registry = StrategyRegistry()
    assert registry.get("RSI_OVERSOLD_NOT_DOWNTREND")
    assert registry.get("TREND_UP_SMA_CONFIRM")

    engine = ReplayExecutionEngine()
    assert engine.initial_cash == 1_000_000

    print("Core imports OK")
    print(DEFAULT_DB_CONFIG)


if __name__ == "__main__":
    main()
