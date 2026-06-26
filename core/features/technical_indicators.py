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


def adx(
    highs: Sequence[Number],
    lows: Sequence[Number],
    closes: Sequence[Number],
    period: int = 14,
) -> list[float | None]:
    """Average Directional Index using Wilder smoothing.

    Returns None for indices where ADX cannot yet be computed.
    Requires at least 2*period - 1 bars for the first ADX value.
    Consistent with ATR: first smooth initialised at index period-1.
    """
    _validate_period(period)
    n = len(highs)
    if not (n == len(lows) == len(closes)):
        raise ValueError("highs, lows and closes must have the same length")

    result: list[float | None] = [None] * n
    if n < 2 * period - 1:
        return result

    # +DM / -DM: index 0 has no previous bar, so it is always 0.
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up_move = float(highs[i]) - float(highs[i - 1])
        down_move = float(lows[i - 1]) - float(lows[i])
        if up_move > down_move and up_move > 0.0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0.0:
            minus_dm[i] = down_move

    tr_values = true_range(highs, lows, closes)

    # Initialise Wilder smoothing at index period-1 (same convention as ATR).
    smooth_tr = sum(tr_values[:period])
    smooth_plus = sum(plus_dm[:period])
    smooth_minus = sum(minus_dm[:period])

    dx_values: list[float | None] = [None] * n

    for i in range(period - 1, n):
        if i > period - 1:
            smooth_tr = smooth_tr - smooth_tr / period + tr_values[i]
            smooth_plus = smooth_plus - smooth_plus / period + plus_dm[i]
            smooth_minus = smooth_minus - smooth_minus / period + minus_dm[i]

        if smooth_tr == 0.0:
            dx_values[i] = 0.0
            continue

        plus_di = 100.0 * smooth_plus / smooth_tr
        minus_di = 100.0 * smooth_minus / smooth_tr
        di_sum = plus_di + minus_di
        dx_values[i] = 100.0 * abs(plus_di - minus_di) / di_sum if di_sum != 0.0 else 0.0

    # ADX = Wilder smooth of DX.
    # Initialise with the mean of the first period DX values (indices period-1 .. 2*period-2).
    adx_start = 2 * period - 2
    initial_slice = [v for v in dx_values[period - 1 : adx_start + 1] if v is not None]
    adx_value = sum(initial_slice) / period
    result[adx_start] = adx_value

    for i in range(adx_start + 1, n):
        dx = dx_values[i]
        if dx is not None:
            adx_value = (adx_value * (period - 1) + dx) / period
            result[i] = adx_value

    return result
