"""Replay engine for deterministic candle-by-candle historical playback."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

Candle = dict[str, Any]
FeatureRow = dict[str, Any]
FeatureBuilder = Callable[[Iterable[Candle]], list[FeatureRow]]


@dataclass(frozen=True)
class ReplayConfig:
    """Configuration for historical replay."""

    warmup_candles: int = 0
    include_features: bool = True
    sort_input: bool = True
    ticker_key: str = "ticker"
    timestamp_key: str = "ts"

    def __post_init__(self) -> None:
        if self.warmup_candles < 0:
            raise ValueError("warmup_candles must be >= 0")


@dataclass(frozen=True)
class ReplayEvent:
    """Single replay step."""

    index: int
    candle: Candle
    history: tuple[Candle, ...]
    features: FeatureRow | None = None

    @property
    def ticker(self) -> str:
        return str(self.candle.get("ticker", ""))

    @property
    def ts(self) -> Any:
        return self.candle.get("ts")


@dataclass
class ReplayState:
    """Mutable replay state."""

    position: int = 0
    events_emitted: int = 0
    is_finished: bool = False
    last_event: ReplayEvent | None = None
    errors: list[str] = field(default_factory=list)


class ReplayEngine:
    """Plays historical OHLCV candles one step at a time.

    The engine is intentionally deterministic:
    - input candles are copied;
    - optional sorting is stable by ticker and timestamp;
    - feature rows are precomputed once per run;
    - every call to ``step`` returns the next immutable ``ReplayEvent``.
    """

    def __init__(
        self,
        candles: Iterable[Candle],
        *,
        feature_builder: FeatureBuilder | None = None,
        config: ReplayConfig | None = None,
    ) -> None:
        self.config = config or ReplayConfig()
        self._candles = [dict(candle) for candle in candles]
        self._validate(self._candles)

        if self.config.sort_input:
            self._candles.sort(
                key=lambda row: (
                    str(row[self.config.ticker_key]),
                    row[self.config.timestamp_key],
                )
            )

        self._features: list[FeatureRow] | None = None
        if self.config.include_features and feature_builder is not None:
            self._features = feature_builder(self._candles)
            if len(self._features) != len(self._candles):
                raise ValueError("feature_builder must return exactly one feature row per candle")

        self.state = ReplayState()

    def __len__(self) -> int:
        return len(self._candles)

    def __iter__(self) -> Iterator[ReplayEvent]:
        while self.has_next():
            event = self.step()
            if event is not None:
                yield event

    @property
    def candles(self) -> tuple[Candle, ...]:
        return tuple(dict(row) for row in self._candles)

    def reset(self) -> None:
        self.state = ReplayState()

    def has_next(self) -> bool:
        return self.state.position < len(self._candles)

    def step(self) -> ReplayEvent | None:
        if not self.has_next():
            self.state.is_finished = True
            return None

        position = self.state.position
        candle = dict(self._candles[position])
        history_start = max(0, position - self.config.warmup_candles)
        history = tuple(dict(row) for row in self._candles[history_start : position + 1])
        features = None if self._features is None else dict(self._features[position])

        event = ReplayEvent(
            index=position,
            candle=candle,
            history=history,
            features=features,
        )

        self.state.position += 1
        self.state.events_emitted += 1
        self.state.last_event = event
        self.state.is_finished = self.state.position >= len(self._candles)
        return event

    def run(self) -> list[ReplayEvent]:
        return list(self)

    def window(self, size: int) -> tuple[Candle, ...]:
        if size <= 0:
            raise ValueError("size must be > 0")
        end = self.state.position
        start = max(0, end - size)
        return tuple(dict(row) for row in self._candles[start:end])

    def _validate(self, candles: list[Candle]) -> None:
        for index, candle in enumerate(candles):
            for key in (self.config.ticker_key, self.config.timestamp_key):
                if key not in candle:
                    raise ValueError(f"candle at index {index} is missing required key: {key}")


def replay(
    candles: Iterable[Candle],
    *,
    feature_builder: FeatureBuilder | None = None,
    config: ReplayConfig | None = None,
) -> list[ReplayEvent]:
    """Convenience helper for full replay."""

    return ReplayEngine(candles, feature_builder=feature_builder, config=config).run()
