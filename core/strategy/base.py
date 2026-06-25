from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Signal:
    action: str
    confidence: float = 1.0
    reason: str = ""

class BaseStrategy:
    strategy_name = ""
    version = "1.0"
    author = "human"
    source = "manual"

    def generate_signal(self, row) -> Signal:
        raise NotImplementedError

    def metadata(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "version": self.version,
            "author": self.author,
            "source": self.source,
        }
