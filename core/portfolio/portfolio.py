class Portfolio:
    def __init__(self, initial_cash):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions = {}

    def make_key(self, strategy_name, ticker):
        return f"{strategy_name}:{ticker}"

    def has_position(self, strategy_name, ticker):
        return self.make_key(strategy_name, ticker) in self.positions

    def add_position(self, position):
        self.positions[self.make_key(position.strategy_name, position.ticker)] = position

    def remove_position(self, strategy_name, ticker):
        return self.positions.pop(self.make_key(strategy_name, ticker))

    def open_positions(self):
        return list(self.positions.items())

    def count_open_positions(self):
        return len(self.positions)

    def reserve_cash(self, amount):
        self.cash -= amount

    def release_cash(self, amount):
        self.cash += amount

    def calculate_equity(self, day_df):
        equity = self.cash
        for _, pos in self.open_positions():
            row = day_df[day_df["ticker"] == pos.ticker]
            equity += pos.entry_price * pos.quantity if row.empty else float(row.iloc[0]["close"]) * pos.quantity
        return equity
