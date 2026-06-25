from core.strategy.strategies.rsi_oversold_not_downtrend import RSIOversoldNotDowntrend
from core.strategy.strategies.trend_up_sma_confirm import TrendUpSMAConfirm


class StrategyRegistry:
    def __init__(self):
        self._strategies = {
            RSIOversoldNotDowntrend.strategy_name: RSIOversoldNotDowntrend(),
            TrendUpSMAConfirm.strategy_name: TrendUpSMAConfirm(),
        }

    def get(self, strategy_name: str):
        strategy = self._strategies.get(strategy_name)
        if strategy is None:
            raise KeyError(f"Strategy not registered: {strategy_name}")
        return strategy

    def all(self):
        return list(self._strategies.values())
