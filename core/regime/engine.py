from __future__ import annotations

from core.regime.models import RegimeFeatures, RegimeSnapshot, RegimeType

_ADX_TREND_THRESHOLD = 25.0
_ADX_STRONG_THRESHOLD = 40.0
_VOLATILITY_THRESHOLD = 0.04


class MarketRegimeEngine:
    """Deterministic market regime classifier based on pre-computed features.

    Receives already-calculated features; does not access data sources,
    compute indicators, or maintain state between calls.

    Priority order:
      1. TREND_UP / TREND_DOWN  — ADX >= 25 with directional SMA cross
      2. HIGH_VOLATILITY        — ATR_pct or realized_volatility >= 0.04
      3. RANGE                  — residual (no trend, low volatility)
      4. UNKNOWN                — invalid input values
    """

    def classify(self, features: RegimeFeatures) -> RegimeSnapshot:
        if not self._is_valid(features):
            return RegimeSnapshot(
                regime=RegimeType.UNKNOWN,
                confidence=0.0,
                reasons=["invalid input: feature values out of valid range"],
            )

        # Trend rules (highest priority)
        if features.adx >= _ADX_TREND_THRESHOLD:
            if features.sma_fast > features.sma_slow:
                return self._trend_snapshot(RegimeType.TREND_UP, features, "bullish")
            if features.sma_fast < features.sma_slow:
                return self._trend_snapshot(RegimeType.TREND_DOWN, features, "bearish")

        # Volatility rule
        high_atr = features.atr_pct >= _VOLATILITY_THRESHOLD
        high_rvol = features.realized_volatility >= _VOLATILITY_THRESHOLD
        if high_atr or high_rvol:
            confidence = 0.9 if (high_atr and high_rvol) else 0.7
            reasons: list[str] = []
            if high_atr:
                reasons.append(
                    f"ATR_pct={features.atr_pct:.4f} >= {_VOLATILITY_THRESHOLD} (high intraday vol)"
                )
            if high_rvol:
                reasons.append(
                    f"realized_vol={features.realized_volatility:.4f} >= {_VOLATILITY_THRESHOLD}"
                )
            return RegimeSnapshot(
                regime=RegimeType.HIGH_VOLATILITY,
                confidence=confidence,
                reasons=reasons,
            )

        # Residual: range
        return RegimeSnapshot(
            regime=RegimeType.RANGE,
            confidence=0.5,
            reasons=[
                f"ADX={features.adx:.2f} < {_ADX_TREND_THRESHOLD} (no trend)",
                f"ATR_pct={features.atr_pct:.4f} and realized_vol="
                f"{features.realized_volatility:.4f} both < {_VOLATILITY_THRESHOLD} (low volatility)",
            ],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _trend_snapshot(
        self, regime: RegimeType, features: RegimeFeatures, direction: str
    ) -> RegimeSnapshot:
        confidence = 0.9 if features.adx >= _ADX_STRONG_THRESHOLD else 0.7
        reasons = [
            f"ADX={features.adx:.2f} >= {_ADX_TREND_THRESHOLD} (trend detected)",
            f"SMA_fast={features.sma_fast:.4f} {'>' if direction == 'bullish' else '<'} "
            f"SMA_slow={features.sma_slow:.4f} ({direction})",
        ]
        return RegimeSnapshot(regime=regime, confidence=confidence, reasons=reasons)

    @staticmethod
    def _is_valid(features: RegimeFeatures) -> bool:
        return (
            0.0 <= features.adx <= 100.0
            and features.atr_pct >= 0.0
            and features.sma_fast > 0.0
            and features.sma_slow > 0.0
            and features.realized_volatility >= 0.0
        )
