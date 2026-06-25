from core.strategy.registry import StrategyRegistry

def main():
    names = StrategyRegistry().names()
    assert "RSI_OVERSOLD_NOT_DOWNTREND" in names
    assert "TREND_UP_SMA_CONFIRM" in names
    print("Strategy registry OK")
    print(names)

if __name__ == "__main__":
    main()
