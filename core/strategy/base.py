from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Signal:
    action: str  # BUY, SELL, HOLD
    confidence: float = 1.0
    reason: str = ""


class BaseStrategy:
    strategy_name: str = ""
    version: str = "1.0"
    author: str = "human"
    source: str = "manual"

    def generate_signal(self, row) -> Signal:
        raise NotImplementedError

    def metadata(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "version": self.version,
            "author": self.author,
            "source": self.source,
        }
