import os
from dataclasses import dataclass

@dataclass
class DBSettings:
    host: str = os.getenv("MOEX_DB_HOST", "localhost")
    port: int = int(os.getenv("MOEX_DB_PORT", "5432"))
    dbname: str = os.getenv("MOEX_DB_NAME", "moex_ai")
    user: str = os.getenv("MOEX_DB_USER", "moex")
    password: str = os.getenv("MOEX_DB_PASSWORD", "moex_pass")

@dataclass
class TradingSettings:
    enable_live_trading: bool = os.getenv("MOEX_ENABLE_LIVE_TRADING", "false").lower() == "true"
    t_invest_token: str = os.getenv("T_INVEST_TOKEN", "")
    t_invest_sandbox: bool = os.getenv("T_INVEST_SANDBOX", "true").lower() == "true"

DB_SETTINGS = DBSettings()
TRADING_SETTINGS = TradingSettings()
