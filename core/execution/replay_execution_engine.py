class ReplayExecutionEngine:
    def __init__(self, initial_cash=1_000_000, position_size=0.10, commission_rate=0.0005,
                 slippage_rate=0.001, take_profit=0.10, stop_loss=-0.05):
        self.initial_cash = initial_cash
        self.position_size = position_size
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.take_profit = take_profit
        self.stop_loss = stop_loss

    def should_close(self, entry_price, current_price):
        pnl_pct = (current_price - entry_price) / entry_price
        if pnl_pct >= self.take_profit:
            return True, "TAKE_PROFIT", pnl_pct
        if pnl_pct <= self.stop_loss:
            return True, "STOP_LOSS", pnl_pct
        return False, None, pnl_pct

    def estimate_trade_value(self, cash):
        return cash * self.position_size

    def calculate_entry(self, trade_value, price):
        if trade_value < 1000:
            return None
        commission = trade_value * self.commission_rate
        slippage = trade_value * self.slippage_rate
        quantity = (trade_value - commission - slippage) / price
        return {"trade_value": trade_value, "commission": commission, "slippage": slippage, "quantity": quantity}

    def calculate_exit(self, current_price, entry_price, quantity):
        trade_value = current_price * quantity
        commission = trade_value * self.commission_rate
        slippage = trade_value * self.slippage_rate
        pnl = (current_price - entry_price) * quantity
        pnl_pct = (current_price - entry_price) / entry_price
        return {"trade_value": trade_value, "commission": commission, "slippage": slippage, "pnl": pnl - commission - slippage, "pnl_pct": pnl_pct}
