class RiskManager:
    def __init__(self, max_open_positions=10, max_positions_per_ticker=2, min_trade_value=1000,
                 max_cash_usage=0.95, min_cash_buffer=10_000):
        self.max_open_positions = max_open_positions
        self.max_positions_per_ticker = max_positions_per_ticker
        self.min_trade_value = min_trade_value
        self.max_cash_usage = max_cash_usage
        self.min_cash_buffer = min_cash_buffer

    def can_open_position(self, portfolio, strategy_name, ticker, trade_value):
        if portfolio.has_position(strategy_name, ticker):
            return False, "POSITION_ALREADY_OPEN"
        if portfolio.count_open_positions() >= self.max_open_positions:
            return False, "MAX_OPEN_POSITIONS_REACHED"
        ticker_positions = sum(1 for _, pos in portfolio.open_positions() if pos.ticker == ticker)
        if ticker_positions >= self.max_positions_per_ticker:
            return False, "MAX_POSITIONS_PER_TICKER_REACHED"
        if trade_value < self.min_trade_value:
            return False, "TRADE_VALUE_TOO_SMALL"
        if portfolio.cash - trade_value < self.min_cash_buffer:
            return False, "MIN_CASH_BUFFER_VIOLATED"
        used_cash = portfolio.initial_cash - portfolio.cash + trade_value
        if used_cash / portfolio.initial_cash > self.max_cash_usage:
            return False, "MAX_CASH_USAGE_VIOLATED"
        return True, "RISK_OK"
