"""Technical indicators for MOEX AI LAB Feature Factory.

The module intentionally uses only Python standard library types so the feature
layer can be tested and reused before the ML stack is finalized.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

Number = int | float


def _validate_period(period: int) -> None:
    if period <= 0:
        raise ValueError("period must be positive")


def sma(values: Sequence[Number], period: int) -> list[float | None]:
    """Simple moving average."""
    _validate_period(period)
    result: list[float | None] = []
    window_sum = 0.0
    for index, value in enumerate(values):
        window_sum += float(value)
        if index >= period:
            window_sum -= float(values[index - period])
        if index + 1 < period:
            result.append(None)
        else:
            result.append(window_sum / period)
    return result


def ema(values: Sequence[Number], period: int) -> list[float | None]:
    """Exponential moving average initialized from the first SMA window."""
    _validate_period(period)
    if not values:
        return []

    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result

    multiplier = 2.0 / (period + 1)
    previous_ema = sum(float(v) for v in values[:period]) / period
    result[period - 1] = previous_ema

    for index in range(period, len(values)):
        previous_ema = (float(values[index]) - previous_ema) * multiplier + previous_ema
        result[index] = previous_ema

    return result


def rsi(values: Sequence[Number], period: int = 14) -> list[float | None]:
    """Relative Strength Index using Wilder smoothing."""
    _validate_period(period)
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result

    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, period + 1):
        change = float(values[index]) - float(values[index - 1])
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    result[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

    for index in range(period + 1, len(values)):
        change = float(values[index]) - float(values[index - 1])
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        result[index] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

    return result


def true_range(highs: Sequence[Number], lows: Sequence[Number], closes: Sequence[Number]) -> list[float]:
    """True range series used by ATR."""
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows and closes must have the same length")

    result: list[float] = []
    for index, high in enumerate(highs):
        high_f = float(high)
        low_f = float(lows[index])
        if index == 0:
            result.append(high_f - low_f)
            continue
        previous_close = float(closes[index - 1])
        result.append(max(high_f - low_f, abs(high_f - previous_close), abs(low_f - previous_close)))
    return result


def atr(highs: Sequence[Number], lows: Sequence[Number], closes: Sequence[Number], period: int = 14) -> list[float | None]:
    """Average True Range using Wilder smoothing."""
    _validate_period(period)
    ranges = true_range(highs, lows, closes)
    result: list[float | None] = [None] * len(ranges)
    if len(ranges) < period:
        return result

    previous_atr = sum(ranges[:period]) / period
    result[period - 1] = previous_atr
    for index in range(period, len(ranges)):
        previous_atr = ((previous_atr * (period - 1)) + ranges[index]) / period
        result[index] = previous_atr
    return result


def pct_change(values: Sequence[Number]) -> list[float | None]:
    """Percentage change from the previous value."""
    result: list[float | None] = [None]
    for index in range(1, len(values)):
        previous = float(values[index - 1])
        current = float(values[index])
        result.append(None if previous == 0 else (current / previous) - 1.0)
    return result[: len(values)]


def rolling_std(values: Sequence[Number], period: int) -> list[float | None]:
    """Population rolling standard deviation."""
    _validate_period(period)
    result: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < period:
            result.append(None)
            continue
        window = [float(v) for v in values[index - period + 1 : index + 1]]
        mean = sum(window) / period
        variance = sum((value - mean) ** 2 for value in window) / period
        result.append(sqrt(variance))
    return result
