from __future__ import annotations

import pytest

from core.regime import MarketRegimeEngine, RegimeFeatures, RegimeType


def _engine() -> MarketRegimeEngine:
    return MarketRegimeEngine()


def _features(
    *,
    adx: float = 20.0,
    atr_pct: float = 0.01,
    sma_fast: float = 105.0,
    sma_slow: float = 100.0,
    realized_volatility: float = 0.01,
) -> RegimeFeatures:
    return RegimeFeatures(
        adx=adx,
        atr_pct=atr_pct,
        sma_fast=sma_fast,
        sma_slow=sma_slow,
        realized_volatility=realized_volatility,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Regime classification
# ──────────────────────────────────────────────────────────────────────────────

def test_trend_up():
    snapshot = _engine().classify(_features(adx=30.0, sma_fast=110.0, sma_slow=100.0))
    assert snapshot.regime == RegimeType.TREND_UP


def test_trend_down():
    snapshot = _engine().classify(_features(adx=30.0, sma_fast=90.0, sma_slow=100.0))
    assert snapshot.regime == RegimeType.TREND_DOWN


def test_range():
    snapshot = _engine().classify(
        _features(adx=15.0, atr_pct=0.01, sma_fast=101.0, sma_slow=100.0, realized_volatility=0.01)
    )
    assert snapshot.regime == RegimeType.RANGE


def test_high_volatility_by_atr():
    snapshot = _engine().classify(
        _features(adx=10.0, atr_pct=0.05, sma_fast=100.0, sma_slow=100.0, realized_volatility=0.01)
    )
    assert snapshot.regime == RegimeType.HIGH_VOLATILITY


def test_high_volatility_by_realized_volatility():
    snapshot = _engine().classify(
        _features(adx=10.0, atr_pct=0.01, sma_fast=100.0, sma_slow=100.0, realized_volatility=0.05)
    )
    assert snapshot.regime == RegimeType.HIGH_VOLATILITY


def test_high_volatility_by_both_signals():
    snapshot = _engine().classify(
        _features(adx=10.0, atr_pct=0.05, sma_fast=100.0, sma_slow=100.0, realized_volatility=0.06)
    )
    assert snapshot.regime == RegimeType.HIGH_VOLATILITY


def test_trend_takes_priority_over_high_volatility():
    # ADX >= 25 with bullish cross even when volatility is high → TREND_UP
    snapshot = _engine().classify(
        _features(adx=35.0, atr_pct=0.08, sma_fast=110.0, sma_slow=100.0, realized_volatility=0.06)
    )
    assert snapshot.regime == RegimeType.TREND_UP


# ──────────────────────────────────────────────────────────────────────────────
# Invalid input → UNKNOWN
# ──────────────────────────────────────────────────────────────────────────────

def test_invalid_negative_adx():
    snapshot = _engine().classify(_features(adx=-1.0))
    assert snapshot.regime == RegimeType.UNKNOWN


def test_invalid_adx_above_100():
    snapshot = _engine().classify(_features(adx=101.0))
    assert snapshot.regime == RegimeType.UNKNOWN


def test_invalid_negative_atr_pct():
    snapshot = _engine().classify(_features(atr_pct=-0.01))
    assert snapshot.regime == RegimeType.UNKNOWN


def test_invalid_zero_sma_fast():
    snapshot = _engine().classify(_features(sma_fast=0.0))
    assert snapshot.regime == RegimeType.UNKNOWN


def test_invalid_negative_sma_slow():
    snapshot = _engine().classify(_features(sma_slow=-10.0))
    assert snapshot.regime == RegimeType.UNKNOWN


def test_invalid_negative_realized_volatility():
    snapshot = _engine().classify(_features(realized_volatility=-0.01))
    assert snapshot.regime == RegimeType.UNKNOWN


# ──────────────────────────────────────────────────────────────────────────────
# Confidence
# ──────────────────────────────────────────────────────────────────────────────

def test_confidence_generated_for_trend_up():
    snapshot = _engine().classify(_features(adx=30.0, sma_fast=110.0, sma_slow=100.0))
    assert 0.0 < snapshot.confidence <= 1.0


def test_confidence_generated_for_range():
    snapshot = _engine().classify(_features(adx=15.0))
    assert 0.0 < snapshot.confidence <= 1.0


def test_strong_trend_has_higher_confidence_than_weak():
    weak = _engine().classify(_features(adx=26.0, sma_fast=105.0, sma_slow=100.0))
    strong = _engine().classify(_features(adx=45.0, sma_fast=105.0, sma_slow=100.0))
    assert strong.confidence >= weak.confidence


def test_both_volatility_signals_give_higher_confidence_than_one():
    one_signal = _engine().classify(
        _features(adx=10.0, atr_pct=0.05, sma_fast=100.0, sma_slow=100.0, realized_volatility=0.01)
    )
    two_signals = _engine().classify(
        _features(adx=10.0, atr_pct=0.05, sma_fast=100.0, sma_slow=100.0, realized_volatility=0.05)
    )
    assert two_signals.confidence >= one_signal.confidence


def test_unknown_has_zero_confidence():
    snapshot = _engine().classify(_features(adx=-1.0))
    assert snapshot.confidence == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Reasons
# ──────────────────────────────────────────────────────────────────────────────

def test_reasons_generated_for_trend_up():
    snapshot = _engine().classify(_features(adx=30.0, sma_fast=110.0, sma_slow=100.0))
    assert len(snapshot.reasons) > 0
    combined = " ".join(snapshot.reasons).lower()
    assert "adx" in combined
    assert "sma" in combined


def test_reasons_generated_for_high_volatility():
    snapshot = _engine().classify(_features(adx=10.0, atr_pct=0.05, realized_volatility=0.01))
    assert len(snapshot.reasons) > 0
    assert any("atr" in r.lower() for r in snapshot.reasons)


def test_reasons_generated_for_range():
    snapshot = _engine().classify(_features(adx=15.0))
    assert len(snapshot.reasons) > 0


def test_unknown_reasons_mention_invalid():
    snapshot = _engine().classify(_features(adx=-5.0))
    assert len(snapshot.reasons) > 0
    assert any("invalid" in r.lower() for r in snapshot.reasons)


# ──────────────────────────────────────────────────────────────────────────────
# Determinism
# ──────────────────────────────────────────────────────────────────────────────

def test_deterministic_trend_up():
    features = _features(adx=35.0, sma_fast=110.0, sma_slow=100.0)
    engine = _engine()
    a = engine.classify(features)
    b = engine.classify(features)
    assert a.regime == b.regime
    assert a.confidence == b.confidence
    assert a.reasons == b.reasons


def test_deterministic_range():
    features = _features(adx=12.0, atr_pct=0.01, realized_volatility=0.005)
    engine = _engine()
    a = engine.classify(features)
    b = engine.classify(features)
    assert a.regime == b.regime
    assert a.confidence == b.confidence


def test_engine_has_no_state():
    # Calling engine multiple times with different inputs gives independent results
    engine = _engine()
    trend = engine.classify(_features(adx=30.0, sma_fast=110.0, sma_slow=100.0))
    unknown = engine.classify(_features(adx=-1.0))
    range_regime = engine.classify(_features(adx=15.0))

    assert trend.regime == RegimeType.TREND_UP
    assert unknown.regime == RegimeType.UNKNOWN
    assert range_regime.regime == RegimeType.RANGE


# ──────────────────────────────────────────────────────────────────────────────
# Boundary conditions
# ──────────────────────────────────────────────────────────────────────────────

def test_adx_exactly_at_threshold_triggers_trend():
    # ADX == 25.0 exactly → trend rules apply
    snapshot = _engine().classify(_features(adx=25.0, sma_fast=110.0, sma_slow=100.0))
    assert snapshot.regime == RegimeType.TREND_UP


def test_adx_just_below_threshold_does_not_trigger_trend():
    snapshot = _engine().classify(
        _features(adx=24.9, sma_fast=110.0, sma_slow=100.0, atr_pct=0.01, realized_volatility=0.01)
    )
    assert snapshot.regime == RegimeType.RANGE


def test_atr_pct_exactly_at_threshold():
    snapshot = _engine().classify(
        _features(adx=10.0, atr_pct=0.04, sma_fast=100.0, sma_slow=100.0, realized_volatility=0.01)
    )
    assert snapshot.regime == RegimeType.HIGH_VOLATILITY


def test_equal_sma_values_does_not_trigger_trend():
    # sma_fast == sma_slow → neither TREND_UP nor TREND_DOWN
    snapshot = _engine().classify(
        _features(adx=30.0, sma_fast=100.0, sma_slow=100.0, atr_pct=0.01, realized_volatility=0.01)
    )
    assert snapshot.regime == RegimeType.RANGE
