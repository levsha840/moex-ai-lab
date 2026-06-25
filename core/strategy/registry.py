from core.strategy.strategies.rsi_oversold_not_downtrend import RSIOversoldNotDowntrend
from core.strategy.strategies.trend_up_sma_confirm import TrendUpSMAConfirm

class StrategyRegistry:
    def __init__(self):
        self._strategies = {}
        self.register(RSIOversoldNotDowntrend())
        self.register(TrendUpSMAConfirm())

    def register(self, strategy):
        self._strategies[strategy.strategy_name] = strategy

    def get(self, strategy_name):
        if strategy_name not in self._strategies:
            raise KeyError(f"Strategy not registered: {strategy_name}")
        return self._strategies[strategy_name]

    def all(self):
        return list(self._strategies.values())

    def names(self):
        return sorted(self._strategies.keys())
