"""Tests for adx() in core/features/technical_indicators.py."""
from __future__ import annotations

import math

import pytest

from core.features.technical_indicators import adx


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _uptrend_candles(n: int = 60) -> tuple[list[float], list[float], list[float]]:
    """Strongly ascending prices — each bar moves up by 1.5 units."""
    highs = [100.0 + i * 1.5 + 0.5 for i in range(n)]
    lows = [100.0 + i * 1.5 - 0.5 for i in range(n)]
    closes = [100.0 + i * 1.5 for i in range(n)]
    return highs, lows, closes


def _range_candles(n: int = 60) -> tuple[list[float], list[float], list[float]]:
    """Price oscillates; net displacement is near zero."""
    highs = [100.5 + math.sin(i * 0.8) for i in range(n)]
    lows = [99.5 + math.sin(i * 0.8) for i in range(n)]
    closes = [100.0 + math.sin(i * 0.8) for i in range(n)]
    return highs, lows, closes


def _flat_candles(n: int = 30) -> tuple[list[float], list[float], list[float]]:
    """Perfectly flat prices: no movement at all."""
    highs = [100.0] * n
    lows = [100.0] * n
    closes = [100.0] * n
    return highs, lows, closes


# ──────────────────────────────────────────────────────────────────────────────
# Insufficient data
# ──────────────────────────────────────────────────────────────────────────────

def test_adx_insufficient_data_all_none_default_period():
    """Fewer than 2*period-1 bars → all None."""
    h = [100.0] * 10
    l_ = [99.0] * 10
    c = [99.5] * 10
    result = adx(h, l_, c, period=14)
    assert all(v is None for v in result)


def test_adx_insufficient_data_period_3():
    """period=3 requires ≥5 bars; 4 bars returns all None."""
    h = [10.0, 11.0, 10.5, 11.5]
    l_ = [9.0, 9.5, 9.8, 10.0]
    c = [9.5, 10.5, 10.0, 11.0]
    result = adx(h, l_, c, period=3)
    assert all(v is None for v in result)


def test_adx_minimum_bars_yields_exactly_one_value():
    """Exactly 2*period-1 bars → last index is the only non-None value."""
    period = 5
    min_n = 2 * period - 1  # 9
    h, l_, c = _uptrend_candles(min_n)
    result = adx(h, l_, c, period=period)
    non_none = [v for v in result if v is not None]
    assert len(non_none) == 1
    assert result[-1] is not None


# ──────────────────────────────────────────────────────────────────────────────
# Uptrend
# ──────────────────────────────────────────────────────────────────────────────

def test_adx_uptrend_produces_high_values():
    """Strong directional trend → ADX should exceed 25."""
    h, l_, c = _uptrend_candles(60)
    result = adx(h, l_, c, period=14)
    non_none = [v for v in result if v is not None]
    assert len(non_none) > 0
    assert non_none[-1] > 25.0, f"Expected ADX > 25 in strong uptrend, got {non_none[-1]:.2f}"


def test_adx_uptrend_length_matches_input():
    h, l_, c = _uptrend_candles(60)
    result = adx(h, l_, c, period=14)
    assert len(result) == 60


def test_adx_uptrend_first_non_none_at_correct_index():
    """First ADX value appears at index 2*period-2."""
    period = 14
    h, l_, c = _uptrend_candles(60)
    result = adx(h, l_, c, period=period)
    expected_first = 2 * period - 2  # index 26
    assert result[expected_first] is not None
    assert all(v is None for v in result[:expected_first])


# ──────────────────────────────────────────────────────────────────────────────
# Range market
# ──────────────────────────────────────────────────────────────────────────────

def test_adx_range_market_lower_than_uptrend():
    """Ranging market produces lower ADX than a strong trend."""
    h_up, l_up, c_up = _uptrend_candles(60)
    h_rng, l_rng, c_rng = _range_candles(60)

    adx_up = [v for v in adx(h_up, l_up, c_up, period=14) if v is not None]
    adx_rng = [v for v in adx(h_rng, l_rng, c_rng, period=14) if v is not None]

    assert adx_up[-1] > adx_rng[-1], (
        f"Uptrend ADX ({adx_up[-1]:.2f}) should exceed range ADX ({adx_rng[-1]:.2f})"
    )


# ──────────────────────────────────────────────────────────────────────────────
# No division by zero
# ──────────────────────────────────────────────────────────────────────────────

def test_adx_flat_market_no_exception():
    """Perfectly flat prices: TR=0, +DM=-DM=0; must not raise ZeroDivisionError."""
    h, l_, c = _flat_candles(30)
    result = adx(h, l_, c, period=14)  # must not raise
    assert len(result) == 30


def test_adx_flat_market_valid_values_are_zero():
    """With zero TR and zero DM, valid ADX values should be 0.0."""
    h, l_, c = _flat_candles(30)
    result = adx(h, l_, c, period=14)
    non_none = [v for v in result if v is not None]
    assert all(v == 0.0 for v in non_none)


def test_adx_all_values_in_valid_range():
    """ADX must always be in [0, 100]."""
    h, l_, c = _uptrend_candles(100)
    result = adx(h, l_, c, period=14)
    for v in result:
        if v is not None:
            assert 0.0 <= v <= 100.0, f"ADX out of range: {v}"


# ──────────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────────

def test_adx_raises_on_invalid_period():
    with pytest.raises(ValueError):
        adx([1.0], [0.9], [1.0], period=0)


def test_adx_raises_on_mismatched_lengths():
    with pytest.raises(ValueError):
        adx([1.0, 2.0], [0.9], [1.0, 1.5], period=5)
