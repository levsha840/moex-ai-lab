"""
M10 Alpha Discovery — Net Edge Predictor

Predicts the net edge (after execution costs) for a proposed strategy
based on its feature composition, target regime, and timeframe.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.alpha_discovery.feature_importance import FeatureScore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Current MOEX 2024 regime
CURRENT_MOEX_REGIME = "TREND"

# Regime-specific pass_rate adjustments (additive)
REGIME_BONUS: dict[str, float] = {
    "SIDEWAYS":  +0.05,
    "CRISIS":    +0.03,
    "TREND":     -0.03,
    "HIGH_VOL":   0.00,
}

# Timeframe noise penalty (additive to pass_rate)
TIMEFRAME_PENALTY: dict[str, float] = {
    "1H":  -0.08,
    "4H":  -0.03,
    "1D":   0.00,
}

# Payoff ratio bonuses per feature
PAYOFF_BONUS: dict[str, float] = {
    "ATR":           +0.50,
    "MOMENTUM":      +0.30,
    "REGIME_FILTER": +0.20,
    "VOLATILITY":    +0.15,
    "VOLUME":        +0.10,
}

AVG_WIN_PCT = 0.035   # 3.5% typical win on MOEX
AVG_LOSS_PCT = 0.015  # 1.5% typical loss on MOEX (at 1.5:1 baseline)

VIABILITY_THRESHOLD = 0.00005  # 0.005% minimum net edge

# Feature categories — filters/exits should NOT contribute to pass_rate estimation
# (they affect quality of signals taken, not raw signal frequency)
FILTER_FEATURES = {"REGIME_FILTER", "TIME_FILTER", "TREND_FILTER"}
EXIT_FEATURES = {"ATR"}

# Filter features provide these pass_rate bonuses (additive, applied after base estimation)
# REGIME_FILTER: +0.12 — M9 showed regime filtering is critical. Restricting to the
# correct regime significantly boosts the quality of trades taken (quality > quantity).
FILTER_PASS_RATE_BONUS: dict[str, float] = {
    "REGIME_FILTER": +0.12,   # regime-filtering is critical (M9 lesson): +12% pass_rate
    "TIME_FILTER":   +0.05,   # time-of-day filtering reduces noise: +5% pass_rate
    "TREND_FILTER":  +0.05,   # trend direction filter avoids counter-trend entries
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class NetEdgePrediction:
    hypothesis_draft_id: str
    features: list[str]
    target_regime: str
    target_timeframe: str
    expected_pass_rate: float          # estimated from feature importance
    expected_payoff_ratio: float       # estimated R:R
    expected_gross_edge_pct: float     # per-trade gross edge %
    commission_cost_pct: float         # always 0.30%
    expected_net_edge_pct: float       # gross - costs
    is_viable: bool                    # True if net_edge > VIABILITY_THRESHOLD
    confidence: float                  # 0-1, how confident we are
    rejection_reason: str              # why not viable (empty string if viable)


# ---------------------------------------------------------------------------
# Predictor
# ---------------------------------------------------------------------------

class NetEdgePredictor:
    """Estimates net edge for a proposed strategy composition."""

    COMMISSION_ROUNDTRIP = 0.0030

    def predict(
        self,
        features: list[str],
        target_regime: str,
        target_timeframe: str,
        feature_scores: dict[str, FeatureScore],
        hypothesis_draft_id: str = "DRAFT_XXX",
    ) -> NetEdgePrediction:
        """Predict net edge for a feature set under given regime + timeframe."""

        # 1. Base pass_rate: weighted average of feature scores
        pass_rate = self._estimate_pass_rate(features, feature_scores)

        # 2. Apply regime adjustment
        regime_adj = REGIME_BONUS.get(target_regime, 0.0)
        pass_rate += regime_adj

        # 3. Apply timeframe noise penalty
        tf_penalty = TIMEFRAME_PENALTY.get(target_timeframe, 0.0)
        pass_rate += tf_penalty

        # Clamp
        pass_rate = max(0.05, min(0.95, pass_rate))

        # 4. Estimate payoff ratio
        payoff_ratio = self._estimate_payoff_ratio(features)

        # 5. Compute gross edge
        # avg_win = payoff_ratio * base_loss_pct
        avg_win = payoff_ratio * AVG_LOSS_PCT
        avg_loss = AVG_LOSS_PCT
        gross_edge = (pass_rate * avg_win) - ((1.0 - pass_rate) * avg_loss)

        # 6. Net edge
        net_edge = gross_edge - self.COMMISSION_ROUNDTRIP

        # 7. Confidence
        confidence = self._estimate_confidence(features, feature_scores, pass_rate)

        # 8. Viability
        is_viable = net_edge > VIABILITY_THRESHOLD
        rejection_reason = ""
        if not is_viable:
            if net_edge < -0.005:
                rejection_reason = f"Severe negative net edge: {net_edge:.4%} — commission drag dominates"
            elif pass_rate < 0.35:
                rejection_reason = f"Pass rate too low: {pass_rate:.1%} — needs >= 35% to approach viability"
            else:
                rejection_reason = f"Net edge {net_edge:.4%} below viability threshold {VIABILITY_THRESHOLD:.4%}"

        return NetEdgePrediction(
            hypothesis_draft_id=hypothesis_draft_id,
            features=list(features),
            target_regime=target_regime,
            target_timeframe=target_timeframe,
            expected_pass_rate=round(pass_rate, 4),
            expected_payoff_ratio=round(payoff_ratio, 2),
            expected_gross_edge_pct=round(gross_edge, 6),
            commission_cost_pct=self.COMMISSION_ROUNDTRIP,
            expected_net_edge_pct=round(net_edge, 6),
            is_viable=is_viable,
            confidence=round(confidence, 4),
            rejection_reason=rejection_reason,
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _estimate_pass_rate(
        self, features: list[str], feature_scores: dict[str, FeatureScore]
    ) -> float:
        """
        Estimate pass_rate from SIGNAL features only.

        Filter features (REGIME_FILTER, TIME_FILTER, TREND_FILTER) and exit features (ATR)
        are NOT included in the base pass_rate calculation — they affect trade quality,
        not raw signal generation. Their bonuses are applied separately in predict().
        """
        total_weight = 0.0
        weighted_pr = 0.0

        for feat in features:
            # Skip filter and exit features — handled separately
            if feat in FILTER_FEATURES or feat in EXIT_FEATURES:
                continue

            score = feature_scores.get(feat)
            if score is not None:
                w = score.positive_weight
                total_weight += w
                weighted_pr += score.avg_pass_rate * w
            else:
                # Unknown feature: use conservative 0.20 pass rate
                total_weight += 0.30
                weighted_pr += 0.20 * 0.30

        if total_weight == 0.0:
            return 0.25  # conservative default for feature-only strategies

        base_pr = weighted_pr / total_weight

        # Apply filter bonuses
        for feat in features:
            bonus = FILTER_PASS_RATE_BONUS.get(feat, 0.0)
            base_pr += bonus

        return base_pr

    def _estimate_payoff_ratio(self, features: list[str]) -> float:
        """Estimate R:R ratio from feature composition."""
        base = 2.0  # typical MOEX strategy baseline

        for feat in features:
            base += PAYOFF_BONUS.get(feat, 0.0)

        return round(max(1.0, base), 2)

    def _estimate_confidence(
        self,
        features: list[str],
        feature_scores: dict[str, FeatureScore],
        pass_rate: float,
    ) -> float:
        """
        Confidence in the prediction (0-1).

        Higher confidence when:
        - More features are in M8 data (tested)
        - Pass rate is in a comfortable range (not edge cases)
        - REGIME_FILTER present (reduces estimation uncertainty)
        """
        n_known = sum(1 for f in features if f in feature_scores)
        coverage = n_known / max(1, len(features))

        # Base confidence from data coverage
        conf = 0.30 + coverage * 0.40

        # Pass rate confidence (0.30-0.70 is best-estimated range)
        if 0.30 <= pass_rate <= 0.70:
            conf += 0.15
        else:
            conf -= 0.10

        # Regime filter reduces uncertainty
        if "REGIME_FILTER" in features:
            conf += 0.10

        # Multiple strategies tested means M8 data is solid
        n_strategies = sum(
            feature_scores[f].n_strategies
            for f in features
            if f in feature_scores and feature_scores[f].n_strategies > 0
        )
        if n_strategies >= 3:
            conf += 0.05

        return min(1.0, max(0.0, conf))
