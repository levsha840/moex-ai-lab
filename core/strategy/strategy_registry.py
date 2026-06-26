"""Lightweight registry for Strategy Engine v1.4 strategies."""

from __future__ import annotations

from typing import Any


class EngineStrategyRegistry:
    """Registry that stores strategy instances by ``strategy_name``.

    This class intentionally does not replace the legacy ``StrategyRegistry`` in
    ``core.strategy.registry``. It is used by the new StrategyEngine layer.
    """

    def __init__(self) -> None:
        self._strategies: dict[str, Any] = {}

    def register(self, strategy: Any) -> None:
        name = str(getattr(strategy, "strategy_name", ""))
        if not name:
            raise ValueError("strategy must define strategy_name")
        if name in self._strategies:
            raise ValueError(f"strategy already registered: {name}")
        self._strategies[name] = strategy

    def get(self, strategy_name: str) -> Any:
        if strategy_name not in self._strategies:
            raise KeyError(f"Strategy not registered: {strategy_name}")
        return self._strategies[strategy_name]

    def all(self) -> list[Any]:
        return list(self._strategies.values())

    def names(self) -> list[str]:
        return sorted(self._strategies)
