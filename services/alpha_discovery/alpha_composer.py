"""
M10 Alpha Discovery — Alpha Composer

Generates new strategy hypotheses by combining features intelligently,
guided by feature importance scores and M9 execution cost lessons.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from services.alpha_discovery.feature_importance import FEATURES, FeatureScore
from services.alpha_discovery.net_edge_predictor import NetEdgePredictor, CURRENT_MOEX_REGIME

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STRATEGY_FEATURES: dict[str, list[str]] = {
    "BB_SQUEEZE":        ["BOLLINGER", "VOLUME", "VOLATILITY"],
    "DUAL_MA_TREND":     ["SMA", "EMA", "TREND_FILTER"],
    "RSI_MOMENTUM":      ["RSI", "MOMENTUM", "VOLUME"],
    "VOL_BREAKOUT":      ["VOLATILITY", "VOLUME", "ATR"],
    "ADX_CONTINUATION":  ["ADX", "TREND_FILTER", "EMA"],
    "MOMENTUM_PULLBACK": ["RSI", "ATR", "TREND_FILTER"],
    "SMA_CROSSOVER":     ["SMA", "EMA"],
    "REV_VOL_REG":       ["VOLATILITY", "REGIME_FILTER", "BOLLINGER"],
    "RSI_OVERSOLD":      ["RSI"],
    "TREND_STRENGTH":    ["ADX", "EMA", "TREND_FILTER"],
}

# Instruments to suggest (diversified across MOEX sectors)
MOEX_INSTRUMENTS: list[str] = [
    "SBER", "GAZP", "LKOH", "NVTK", "GMKN",
    "MGNT", "PLZL", "ROSN", "CHMF", "VTBR",
]

# Target timeframes (1H is noise-sensitive per M9)
PREFERRED_TIMEFRAMES: list[str] = ["1D", "4H"]


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class StrategyDraft:
    draft_id: str                   # e.g. "DRAFT_001"
    status: str                     # always "GENERATED_DRAFT"
    name: str                       # human-readable name
    description: str
    features: list[str]             # all technical factors used
    signal_features: list[str]      # entry signal factors
    filter_features: list[str]      # filter/gate factors
    exit_features: list[str]        # exit logic factors
    target_regimes: list[str]       # ["SIDEWAYS", "CRISIS"] etc.
    target_timeframes: list[str]    # ["1D", "4H"]
    target_instruments: list[str]   # suggested instruments
    expected_pass_rate: float
    expected_payoff_ratio: float
    expected_net_edge_pct: float
    expected_confidence: float      # 0-1
    rationale: str                  # WHY this combination was chosen
    inspired_by: list[str]          # which existing strategies inspired this
    novelty_score: float            # how different from existing strategies (0-1)
    priority_score: float           # higher = run first
    created_from: str               # "alpha_discovery_engine_v1"


# ---------------------------------------------------------------------------
# Pre-defined draft templates
# ---------------------------------------------------------------------------

# Each template: (name, signal_features, filter_features, exit_features,
#                 target_regimes, inspired_by, description)
_DRAFT_TEMPLATES: list[tuple] = [
    (
        "RSI_VOLUME_REGIME",
        ["RSI", "VOLUME"], ["REGIME_FILTER"], ["ATR"],
        ["SIDEWAYS", "CRISIS"],
        ["RSI_MOMENTUM", "BB_SQUEEZE"],
        "RSI momentum with volume confirmation in regime-filtered SIDEWAYS/CRISIS market. "
        "Addresses M9 finding that commission drag is reduced by regime selectivity.",
    ),
    (
        "BB_ATR_ADX_FILTERED",
        ["BOLLINGER"], ["ADX", "REGIME_FILTER"], ["ATR"],
        ["SIDEWAYS"],
        ["BB_SQUEEZE"],
        "Improved BB_SQUEEZE with ADX gate to avoid false squeezes in trending markets "
        "and ATR exit for higher payoff ratio. Directly addresses M9 BB_SQUEEZE failure.",
    ),
    (
        "VOL_BREAKOUT_REGIME",
        ["VOLATILITY", "VOLUME"], ["TREND_FILTER", "REGIME_FILTER"], ["ATR"],
        ["HIGH_VOL", "CRISIS"],
        ["VOL_BREAKOUT"],
        "Filtered volatility breakout restricted to HIGH_VOL and CRISIS regimes. "
        "TREND_FILTER prevents false breakouts in sideways markets.",
    ),
    (
        "RSI_BB_DUAL_OSCILLATOR",
        ["RSI", "BOLLINGER"], ["REGIME_FILTER", "TIME_FILTER"], ["ATR"],
        ["SIDEWAYS", "HIGH_VOL"],
        ["BB_SQUEEZE", "RSI_MOMENTUM"],
        "Dual oscillator system requiring both RSI and Bollinger signals to align. "
        "Higher signal confluence raises expected pass_rate above 40%.",
    ),
    (
        "VWAP_MOMENTUM_TREND",
        ["VWAP", "VOLUME", "MOMENTUM"], ["REGIME_FILTER"], ["ATR"],
        ["TREND", "SIDEWAYS"],
        ["RSI_MOMENTUM"],
        "Volume-weighted momentum using VWAP anchoring. Untested in M8 but strong "
        "theoretical basis for MOEX intraday/daily trading.",
    ),
    (
        "ADX_MOMENTUM_REGIME_TREND",
        ["ADX", "MOMENTUM"], ["REGIME_FILTER"], ["ATR"],
        ["TREND"],
        ["ADX_CONTINUATION", "RSI_MOMENTUM"],
        "ADX trend strength combined with momentum signal, in regime-confirmed TREND market. "
        "Replaces EMA (whipsaw risk from M9) with MOMENTUM for better pass_rate in TREND regime.",
    ),
    (
        "VOLATILITY_CRISIS_ATR",
        ["VOLATILITY", "ATR"], ["REGIME_FILTER"], ["ATR"],
        ["CRISIS", "HIGH_VOL"],
        ["VOL_BREAKOUT", "REV_VOL_REG"],
        "Crisis-specialist strategy using volatility expansion signal. ATR-based dynamic "
        "stops protect capital while capturing large moves in CRISIS regimes.",
    ),
    (
        "RSI_ATR_ADX_MULTI",
        ["RSI", "ATR", "ADX"], ["REGIME_FILTER"], ["ATR"],
        ["SIDEWAYS", "TREND"],
        ["RSI_MOMENTUM", "ADX_CONTINUATION", "MOMENTUM_PULLBACK"],
        "Multi-factor strategy combining momentum (RSI), trend (ADX), and risk (ATR). "
        "Higher feature count increases signal quality and reduces noise.",
    ),
    (
        "BB_VWAP_VOLUME_CONFIRMED",
        ["BOLLINGER", "VWAP", "VOLUME"], ["REGIME_FILTER"], ["ATR"],
        ["SIDEWAYS", "HIGH_VOL"],
        ["BB_SQUEEZE"],
        "Bollinger Band signals confirmed by VWAP position and volume surge. "
        "Volume confirmation was missing from original BB_SQUEEZE causing false signals.",
    ),
    (
        "MOMENTUM_TREND_ATR_COMPOSITE",
        ["MOMENTUM", "TREND_FILTER", "ATR"], ["REGIME_FILTER"], ["ATR"],
        ["TREND"],
        ["RSI_MOMENTUM", "MOMENTUM_PULLBACK"],
        "Momentum with trend direction filter and ATR-sized positions. "
        "High payoff ratio potential due to ATR exit capturing extended trend moves.",
    ),
    (
        "RSI_VWAP_SIDEWAYS",
        ["RSI", "VWAP"], ["REGIME_FILTER", "TIME_FILTER"], ["ATR"],
        ["SIDEWAYS"],
        ["RSI_OVERSOLD", "RSI_MOMENTUM"],
        "Mean-reversion RSI with VWAP anchoring — optimized for SIDEWAYS regime. "
        "Time filter avoids low-liquidity periods to reduce slippage.",
    ),
    (
        "BOLLINGER_MOMENTUM_VOL",
        ["BOLLINGER", "MOMENTUM", "VOLUME"], ["REGIME_FILTER"], ["ATR"],
        ["HIGH_VOL", "SIDEWAYS"],
        ["BB_SQUEEZE", "RSI_MOMENTUM"],
        "Bollinger breakout confirmed by momentum and volume surge. "
        "Three-factor confluence raises pass_rate above the 40% viability threshold.",
    ),
]


# ---------------------------------------------------------------------------
# Composer
# ---------------------------------------------------------------------------

class AlphaComposer:
    """
    Generates strategy drafts from feature importance data.
    Fully deterministic with seed=42.
    """

    SEED = 42

    def compose(
        self,
        feature_scores: dict[str, FeatureScore],
        existing_strategies: list[str],
        net_edge_predictor: NetEdgePredictor,
        n_drafts: int = 10,
    ) -> list[StrategyDraft]:
        """Generate strategy drafts. Returns only drafts with positive net edge."""
        rng = random.Random(self.SEED)

        # Track existing feature combinations to ensure novelty
        existing_combos: set[frozenset] = set()
        for strat_id in existing_strategies:
            feats = STRATEGY_FEATURES.get(strat_id, [])
            if feats:
                existing_combos.add(frozenset(feats))

        drafts: list[StrategyDraft] = []
        draft_counter = 0

        for template in _DRAFT_TEMPLATES:
            name, sig_feats, filt_feats, exit_feats, regimes, inspired_by, desc = template

            all_features = list(sig_feats) + list(filt_feats) + list(exit_feats)
            # Deduplicate while preserving order
            seen_f: set[str] = set()
            unique_features: list[str] = []
            for f in all_features:
                if f not in seen_f:
                    seen_f.add(f)
                    unique_features.append(f)

            draft_counter += 1
            draft_id = f"DRAFT_{draft_counter:03d}"

            # Pick primary regime and timeframe for net edge prediction
            primary_regime = regimes[0]
            primary_tf = "1D"  # prefer 1D by default

            # Predict net edge
            prediction = net_edge_predictor.predict(
                features=unique_features,
                target_regime=primary_regime,
                target_timeframe=primary_tf,
                feature_scores=feature_scores,
                hypothesis_draft_id=draft_id,
            )

            # Skip if net edge is not strictly positive above viability threshold
            # Composer only generates strategies with a real edge above execution costs
            if prediction.expected_net_edge_pct <= 0.00005:
                continue

            # Compute novelty score
            feat_set = frozenset(unique_features)
            novelty = self._compute_novelty(feat_set, existing_combos)

            # Priority score
            priority = self._compute_priority(
                prediction.expected_net_edge_pct,
                prediction.confidence,
                novelty,
                primary_regime,
            )

            # Instrument suggestions (diversified)
            instruments = self._suggest_instruments(regimes, rng)

            drafts.append(StrategyDraft(
                draft_id=draft_id,
                status="GENERATED_DRAFT",
                name=name,
                description=desc,
                features=unique_features,
                signal_features=list(sig_feats),
                filter_features=list(filt_feats),
                exit_features=list(exit_feats),
                target_regimes=list(regimes),
                target_timeframes=list(PREFERRED_TIMEFRAMES),
                target_instruments=instruments,
                expected_pass_rate=prediction.expected_pass_rate,
                expected_payoff_ratio=prediction.expected_payoff_ratio,
                expected_net_edge_pct=prediction.expected_net_edge_pct,
                expected_confidence=prediction.confidence,
                rationale=desc,
                inspired_by=list(inspired_by),
                novelty_score=novelty,
                priority_score=priority,
                created_from="alpha_discovery_engine_v1",
            ))

            # Track for novelty checking in subsequent templates
            existing_combos.add(feat_set)

        # Sort by priority descending
        drafts.sort(key=lambda d: d.priority_score, reverse=True)

        # Ensure we meet minimum count by returning all viable drafts
        return drafts

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_novelty(
        self, feat_set: frozenset, existing_combos: set[frozenset]
    ) -> float:
        """
        Novelty = 1 - max_jaccard_similarity_to_existing.
        Jaccard = |intersection| / |union|.
        """
        if not existing_combos:
            return 1.0

        max_sim = 0.0
        for existing in existing_combos:
            intersection = len(feat_set & existing)
            union = len(feat_set | existing)
            sim = intersection / union if union > 0 else 0.0
            if sim > max_sim:
                max_sim = sim

        return round(1.0 - max_sim, 4)

    def _compute_priority(
        self,
        net_edge_pct: float,
        confidence: float,
        novelty: float,
        target_regime: str,
    ) -> float:
        """
        priority = (net_edge_score × 0.40) + (confidence × 0.25) + (novelty × 0.20)
                 + (regime_timing × 0.15)

        where net_edge_score is normalized 0-1 (0 at <= 0%, 1 at >= 2%)
        regime_timing = 1.0 if target_regime == CURRENT_MOEX_REGIME else 0.5
        """
        net_edge_score = min(1.0, max(0.0, net_edge_pct / 0.02))
        regime_timing = 1.0 if target_regime == CURRENT_MOEX_REGIME else 0.5

        priority = (
            net_edge_score * 0.40
            + confidence * 0.25
            + novelty * 0.20
            + regime_timing * 0.15
        )
        return round(priority, 4)

    def _suggest_instruments(
        self, regimes: list[str], rng: random.Random
    ) -> list[str]:
        """Select 5 diversified instruments based on regime affinity."""
        # Regime-to-instrument mapping based on sector characteristics
        regime_instruments: dict[str, list[str]] = {
            "SIDEWAYS":  ["SBER", "MGNT", "GMKN", "PLZL", "VTBR"],
            "TREND":     ["GAZP", "LKOH", "NVTK", "ROSN", "CHMF"],
            "HIGH_VOL":  ["GMKN", "PLZL", "NVTK", "LKOH", "SBER"],
            "CRISIS":    ["PLZL", "GMKN", "SBER", "GAZP", "ROSN"],
        }

        candidates: list[str] = []
        for regime in regimes:
            candidates.extend(regime_instruments.get(regime, MOEX_INSTRUMENTS))

        # Deduplicate
        seen: set[str] = set()
        unique_candidates: list[str] = []
        for inst in candidates:
            if inst not in seen:
                seen.add(inst)
                unique_candidates.append(inst)

        # Return up to 5
        if len(unique_candidates) >= 5:
            return unique_candidates[:5]
        # Pad with remaining instruments
        for inst in MOEX_INSTRUMENTS:
            if inst not in seen:
                unique_candidates.append(inst)
                seen.add(inst)
            if len(unique_candidates) >= 5:
                break
        return unique_candidates[:5]
