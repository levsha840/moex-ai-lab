class ReplayExecutionEngine:
    def __init__(
        self,
        initial_cash: float = 1_000_000,
        position_size: float = 0.10,
        commission_rate: float = 0.0005,
        slippage_rate: float = 0.001,
        take_profit: float = 0.10,
        stop_loss: float = -0.05,
    ):
        self.initial_cash = initial_cash
        self.position_size = position_size
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.take_profit = take_profit
        self.stop_loss = stop_loss

    def should_close(self, entry_price: float, current_price: float):
        pnl_pct = (current_price - entry_price) / entry_price

        if pnl_pct >= self.take_profit:
            return True, "TAKE_PROFIT", pnl_pct

        if pnl_pct <= self.stop_loss:
            return True, "STOP_LOSS", pnl_pct

        return False, None, pnl_pct

    def calculate_entry(self, cash: float, price: float):
        trade_value = cash * self.position_size

        if trade_value < 1000:
            return None

        commission = trade_value * self.commission_rate
        slippage = trade_value * self.slippage_rate
        quantity = (trade_value - commission - slippage) / price

        return {
            "trade_value": trade_value,
            "commission": commission,
            "slippage": slippage,
            "quantity": quantity,
        }

    def calculate_exit(self, current_price: float, entry_price: float, quantity: float):
        trade_value = current_price * quantity
        commission = trade_value * self.commission_rate
        slippage = trade_value * self.slippage_rate
        pnl = (current_price - entry_price) * quantity
        pnl_pct = (current_price - entry_price) / entry_price

        return {
            "trade_value": trade_value,
            "commission": commission,
            "slippage": slippage,
            "pnl": pnl - commission - slippage,
            "pnl_pct": pnl_pct,
        }
