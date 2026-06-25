from dataclasses import dataclass
from typing import Optional

@dataclass
class Position:
    strategy_name: str
    ticker: str
    entry_time: object
    entry_price: float
    quantity: float
    db_id: Optional[int] = None
