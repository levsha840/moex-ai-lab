"""
M10 Alpha Discovery — Self-Learning Weight Updater

Updates feature weights based on strategy outcomes (SUCCESS / FAILURE).
Weights are used by AlphaComposer to prioritize features in future drafts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Initial weights derived from M8 + M9 findings
# ---------------------------------------------------------------------------

INITIAL_WEIGHTS: dict[str, float] = {
    "RSI":           0.55,   # moderate (RSI_MOMENTUM viable)
    "BOLLINGER":     0.60,   # good (BB_SQUEEZE best robustness)
    "ATR":           0.70,   # strong (good exit feature)
    "ADX":           0.45,   # weak (ADX_CONTINUATION lowest robustness)
    "EMA":           0.40,   # weak (low robustness in DUAL_MA_TREND)
    "SMA":           0.30,   # weak (SMA_CROSSOVER worst pass rate 9.5%)
    "VWAP":          0.65,   # untested but volume-price theory valid
    "VOLUME":        0.60,   # positive (confirms breakouts)
    "VOLATILITY":    0.55,   # moderate (VOL_BREAKOUT viable)
    "MOMENTUM":      0.55,   # moderate
    "REGIME_FILTER": 0.85,   # CRITICAL: M9 showed regime filtering is essential
    "TIME_FILTER":   0.50,   # moderate (reduces noise)
    "TREND_FILTER":  0.55,   # moderate
}

# Post-M9 adjustments:
# - COMMISSION_DRAG on both → boost REGIME_FILTER (already done above)
# - DUAL_MA_TREND had LOW_PASS_RATE → reduce EMA, SMA (already done above)
# - BB_SQUEEZE had viable gross edge → BOLLINGER stays at 0.60

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class FactorWeights:
    weights: dict[str, float] = field(default_factory=lambda: dict(INITIAL_WEIGHTS))
    last_updated: str = "2026-06-29"
    n_updates: int = 0


# ---------------------------------------------------------------------------
# Self-Learning
# ---------------------------------------------------------------------------

class SelfLearning:
    """
    Updates factor weights based on strategy outcomes.

    Learning rule (additive):
      SUCCESS: weight_i += LEARNING_RATE * (1 - weight_i)   [pull towards 1]
      FAILURE: weight_i -= LEARNING_RATE * weight_i          [pull towards 0]

    With targeted overrides for specific failure categories.
    """

    LEARNING_RATE = 0.15

    def __init__(self) -> None:
        self._state = FactorWeights()
        # Apply M9 post-hoc update immediately
        self._apply_m9_outcomes()

    def _apply_m9_outcomes(self) -> None:
        """Apply M9 paper trading rejection outcomes to initial weights."""
        # BB_SQUEEZE: COMMISSION_DRAG primary cause
        self.update_from_outcome(
            features=["BOLLINGER", "VOLUME", "VOLATILITY"],
            outcome="FAILURE",
            pass_rate=0.333,
            failure_category="COMMISSION_DRAG",
        )
        # DUAL_MA_TREND: LOW_PASS_RATE + COMMISSION_DRAG
        self.update_from_outcome(
            features=["SMA", "EMA", "TREND_FILTER"],
            outcome="FAILURE",
            pass_rate=0.216,
            failure_category="LOW_PASS_RATE",
        )
        self.update_from_outcome(
            features=["SMA", "EMA", "TREND_FILTER"],
            outcome="FAILURE",
            pass_rate=0.216,
            failure_category="COMMISSION_DRAG",
        )

    def update_from_outcome(
        self,
        features: list[str],
        outcome: str,
        pass_rate: float,
        failure_category: str = "",
    ) -> dict[str, float]:
        """
        Update weights based on strategy outcome.

        outcome: "SUCCESS" or "FAILURE"
        failure_category: one of FAILURE_CATEGORIES keys (for targeted updates)

        Returns updated weights dict.
        """
        weights = self._state.weights
        lr = self.LEARNING_RATE

        if outcome == "SUCCESS":
            # Reinforce all features in successful strategy
            for feat in features:
                if feat in weights:
                    weights[feat] += lr * (1.0 - weights[feat])

        elif outcome == "FAILURE":
            # Penalize features in failed strategy
            for feat in features:
                if feat in weights:
                    weights[feat] -= lr * weights[feat]

            # Targeted adjustments based on failure category
            if failure_category == "COMMISSION_DRAG":
                # Regime filtering would have avoided bad trades
                if "REGIME_FILTER" in weights:
                    weights["REGIME_FILTER"] += lr * (1.0 - weights["REGIME_FILTER"])
                # ATR exit helps improve R:R to survive costs
                if "ATR" in weights:
                    weights["ATR"] += lr * 0.5 * (1.0 - weights["ATR"])

            elif failure_category == "LOW_PASS_RATE":
                # SMA/EMA in DUAL_MA_TREND context → reduce further
                for noisy_feat in ["SMA", "EMA"]:
                    if noisy_feat in weights and noisy_feat in features:
                        weights[noisy_feat] -= lr * 0.5 * weights[noisy_feat]
                # Volume confirmation helps raise pass_rate
                if "VOLUME" in weights:
                    weights["VOLUME"] += lr * 0.3 * (1.0 - weights["VOLUME"])

            elif failure_category == "LOW_BREADTH":
                # Volume and VWAP help generalize across instruments
                if "VOLUME" in weights:
                    weights["VOLUME"] += lr * (1.0 - weights["VOLUME"])
                if "VWAP" in weights:
                    weights["VWAP"] += lr * (1.0 - weights["VWAP"])

            elif failure_category == "NOISE_SENSITIVITY":
                # 1H-specific features are problematic
                for short_tf_feat in ["SMA", "EMA", "TREND_FILTER", "ADX"]:
                    if short_tf_feat in weights and short_tf_feat in features:
                        weights[short_tf_feat] -= lr * 0.3 * weights[short_tf_feat]

        # Clamp all weights to [0, 1]
        for feat in weights:
            weights[feat] = round(min(1.0, max(0.0, weights[feat])), 6)

        self._state.n_updates += 1
        return dict(weights)

    def get_weights(self) -> dict[str, float]:
        """Return current weight snapshot."""
        return dict(self._state.weights)

    def save(self, path: Path) -> None:
        """Persist weights to JSON file."""
        data = {
            "weights": self._state.weights,
            "last_updated": self._state.last_updated,
            "n_updates": self._state.n_updates,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, path: Path) -> None:
        """Load weights from JSON file."""
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self._state.weights.update(data.get("weights", {}))
        self._state.last_updated = data.get("last_updated", self._state.last_updated)
        self._state.n_updates = data.get("n_updates", self._state.n_updates)

    def reset_to_initial(self) -> None:
        """Reset weights to initial M8+M9 derived values (for testing)."""
        self._state = FactorWeights()
