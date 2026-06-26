"""Strategy execution engine integrated with ReplayEngine."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from core.strategy.signal import Signal, SignalAction
from core.strategy.strategy_context import StrategyContext


@dataclass(frozen=True)
class StrategyEngineConfig:
    """Configuration for strategy execution."""

    emit_hold: bool = True
    fail_fast: bool = True
    min_confidence: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class StrategyDecision:
    """Signals produced for one replay event."""

    index: int
    ticker: str
    ts: Any
    signals: tuple[Signal, ...]

    @property
    def has_action(self) -> bool:
        return any(signal.action != SignalAction.HOLD for signal in self.signals)

    @property
    def actionable_signals(self) -> tuple[Signal, ...]:
        return tuple(signal for signal in self.signals if signal.action != SignalAction.HOLD)


@dataclass
class StrategyEngineState:
    """Mutable strategy engine state."""

    events_processed: int = 0
    signals_emitted: int = 0
    errors: list[str] = field(default_factory=list)
    last_decision: StrategyDecision | None = None


class StrategyEngine:
    """Runs registered strategies over replay events or raw contexts."""

    def __init__(
        self,
        strategies: Iterable[Any] | None = None,
        *,
        config: StrategyEngineConfig | None = None,
    ) -> None:
        self.config = config or StrategyEngineConfig()
        self._strategies: list[Any] = []
        self.state = StrategyEngineState()
        for strategy in strategies or []:
            self.register(strategy)

    def register(self, strategy: Any) -> None:
        name = getattr(strategy, "strategy_name", strategy.__class__.__name__)
        if not name:
            raise ValueError("strategy must define non-empty strategy_name")
        self._strategies.append(strategy)

    @property
    def strategies(self) -> tuple[Any, ...]:
        return tuple(self._strategies)

    def reset(self) -> None:
        self.state = StrategyEngineState()

    def on_event(self, event: Any, *, portfolio_state: dict[str, Any] | None = None) -> StrategyDecision:
        context = StrategyContext.from_replay_event(event, portfolio_state=portfolio_state)
        return self.on_context(context)

    def on_context(self, context: StrategyContext) -> StrategyDecision:
        signals: list[Signal] = []
        for strategy in self._strategies:
            try:
                signal = self._call_strategy(strategy, context)
            except Exception as exc:  # pragma: no cover - fail path tested behaviorally
                message = f"{getattr(strategy, 'strategy_name', strategy.__class__.__name__)}: {exc}"
                self.state.errors.append(message)
                if self.config.fail_fast:
                    raise
                continue

            if signal.confidence < self.config.min_confidence:
                continue
            if signal.action == SignalAction.HOLD and not self.config.emit_hold:
                continue
            signals.append(signal)

        decision = StrategyDecision(
            index=context.index,
            ticker=context.ticker,
            ts=context.ts,
            signals=tuple(signals),
        )
        self.state.events_processed += 1
        self.state.signals_emitted += len(signals)
        self.state.last_decision = decision
        return decision

    def run(self, replay_events: Iterable[Any]) -> list[StrategyDecision]:
        return [self.on_event(event) for event in replay_events]

    def _call_strategy(self, strategy: Any, context: StrategyContext) -> Signal:
        if hasattr(strategy, "on_event"):
            raw_signal = strategy.on_event(context)
            return self._normalize_signal(raw_signal, context, strategy)

        if hasattr(strategy, "generate_signal"):
            row = dict(context.candle)
            if context.features:
                row.update(context.features)
            raw_signal = strategy.generate_signal(row)
            return self._normalize_signal(raw_signal, context, strategy)

        raise TypeError("strategy must implement on_event(context) or generate_signal(row)")

    def _normalize_signal(self, raw_signal: Any, context: StrategyContext, strategy: Any) -> Signal:
        if isinstance(raw_signal, Signal):
            return raw_signal

        action_value = getattr(raw_signal, "action", SignalAction.HOLD.value)
        action = SignalAction(str(action_value).upper())
        confidence = float(getattr(raw_signal, "confidence", 1.0))
        reason = str(getattr(raw_signal, "reason", ""))
        strategy_name = str(getattr(strategy, "strategy_name", strategy.__class__.__name__))

        return Signal(
            action=action,
            ticker=context.ticker,
            ts=context.ts,
            strategy_name=strategy_name,
            confidence=confidence,
            reason=reason,
            price=context.close,
            metadata={"adapter": "legacy_generate_signal"},
        )
