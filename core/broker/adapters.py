from core.config.settings import TRADING_SETTINGS

class ReplayBroker:
    mode = "replay"
    def place_order(self, ticker, side, quantity, price=None):
        return {"status": "FILLED", "mode": self.mode, "ticker": ticker, "side": side, "quantity": quantity, "price": price}

class PaperBroker:
    mode = "paper"
    def place_order(self, ticker, side, quantity, price=None):
        return {"status": "PAPER_FILLED", "mode": self.mode, "ticker": ticker, "side": side, "quantity": quantity, "price": price}

class TInvestSandboxBroker:
    mode = "t_invest_sandbox"
    def __init__(self):
        self.token = TRADING_SETTINGS.t_invest_token
    def place_order(self, ticker, side, quantity, price=None):
        if not self.token:
            return {"status": "DRY_RUN", "reason": "T_INVEST_TOKEN_NOT_SET", "mode": self.mode}
        return {"status": "SANDBOX_NOT_IMPLEMENTED_YET", "mode": self.mode}

class LiveBroker:
    mode = "live"
    def place_order(self, ticker, side, quantity, price=None):
        if not TRADING_SETTINGS.enable_live_trading:
            return {"status": "BLOCKED", "reason": "LIVE_TRADING_DISABLED", "mode": self.mode}
        raise RuntimeError("Live broker disabled in v1.0")
