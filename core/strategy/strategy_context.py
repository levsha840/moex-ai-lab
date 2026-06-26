"""Context passed to strategies during replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Candle = dict[str, Any]
FeatureRow = dict[str, Any]


@dataclass(frozen=True)
class StrategyContext:
    """Immutable strategy input for one replay step."""

    index: int
    candle: Candle
    history: tuple[Candle, ...]
    features: FeatureRow | None = None
    portfolio_state: dict[str, Any] = field(default_factory=dict)

    @property
    def ticker(self) -> str:
        return str(self.candle.get("ticker", ""))

    @property
    def ts(self) -> Any:
        return self.candle.get("ts")

    @property
    def close(self) -> float | None:
        value = self.candle.get("close")
        return None if value is None else float(value)

    @classmethod
    def from_replay_event(
        cls,
        event: Any,
        *,
        portfolio_state: dict[str, Any] | None = None,
    ) -> "StrategyContext":
        return cls(
            index=int(getattr(event, "index")),
            candle=dict(getattr(event, "candle")),
            history=tuple(dict(row) for row in getattr(event, "history")),
            features=None if getattr(event, "features") is None else dict(getattr(event, "features")),
            portfolio_state=portfolio_state or {},
        )
