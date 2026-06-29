"""
M10 Alpha Discovery — Failure Analyzer

Analyzes why strategies failed paper trading or were rejected in M8 stability runs.
Determines root cause categories and generates specific improvement recommendations.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Strategy → Feature mapping
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

# ---------------------------------------------------------------------------
# M8 & M9 data embedded for standalone operation
# ---------------------------------------------------------------------------

M8_ROBUSTNESS: dict[str, dict] = {
    "BB_SQUEEZE":        {"robustness": 43.8, "gi": 81.6, "nss": 23.2, "avg_pr": 0.307, "label": "LEADER"},
    "DUAL_MA_TREND":     {"robustness": 38.4, "gi": 84.7, "nss": 10.3, "avg_pr": 0.268, "label": "VIABLE"},
    "VOL_BREAKOUT":      {"robustness": 37.9, "gi": 67.0, "nss": 70.6, "avg_pr": 0.233, "label": "VIABLE"},
    "MOMENTUM_PULLBACK": {"robustness": 37.1, "gi": 76.9, "nss": 16.2, "avg_pr": 0.200, "label": "VIABLE"},
    "RSI_MOMENTUM":      {"robustness": 36.9, "gi": 85.7, "nss": 12.5, "avg_pr": 0.286, "label": "VIABLE"},
    "SMA_CROSSOVER":     {"robustness": 34.1, "gi": 78.9, "nss": 13.6, "avg_pr": 0.096, "label": "VIABLE"},
    "REV_VOL_REG":       {"robustness": 33.3, "gi": 57.4, "nss": 17.2, "avg_pr": 0.079, "label": "VIABLE"},
    "ADX_CONTINUATION":  {"robustness": 30.4, "gi": 80.2, "nss": 18.6, "avg_pr": 0.153, "label": "VIABLE"},
    "RSI_OVERSOLD":      {"robustness": 30.0, "gi": 66.1, "nss": 15.2, "avg_pr": 0.089, "label": "MARGINAL"},
    "TREND_STRENGTH":    {"robustness": 27.3, "gi": 77.4, "nss": 0.0,  "avg_pr": 0.193, "label": "MARGINAL"},
}

M9_RESULTS: dict[str, dict] = {
    "BB_SQUEEZE":    {
        "pf": 0.741, "win_rate": 0.333, "max_dd": 0.061, "sharpe": -2.17,
        "net_pnl": -56287, "gross_pnl": -10433, "exec_drag": 45854,
        "decision": "REJECTED",
    },
    "DUAL_MA_TREND": {
        "pf": 0.435, "win_rate": 0.216, "max_dd": 0.157, "sharpe": -6.26,
        "net_pnl": -152374, "gross_pnl": -106584, "exec_drag": 45791,
        "decision": "REJECTED",
    },
}

# ---------------------------------------------------------------------------
# Failure category definitions
# ---------------------------------------------------------------------------

FAILURE_CATEGORIES: dict[str, str] = {
    "COMMISSION_DRAG":    "Execution costs exceed gross edge (gross PnL > 0 but net PnL < 0)",
    "LOW_PASS_RATE":      "Pass rate < 0.35 — insufficient signal quality",
    "NOISE_SENSITIVITY":  "High NSS — strategy degrades severely at shorter timeframes",
    "LOW_BREADTH":        "< 3 instruments pass threshold — not generalizable",
    "REGIME_FRAGILITY":   "Near-zero performance in CRISIS — lacks crisis resistance",
    "ALPHA_DECAY":        "Negative slope over years — edge eroding over time",
}

# Feature → regime affinity (regimes where feature contributes positively)
_FEATURE_REGIME_AFFINITY: dict[str, list[str]] = {
    "RSI":           ["SIDEWAYS", "HIGH_VOL"],
    "BOLLINGER":     ["SIDEWAYS", "HIGH_VOL"],
    "ATR":           ["HIGH_VOL", "CRISIS"],
    "ADX":           ["TREND"],
    "EMA":           ["TREND"],
    "SMA":           ["TREND"],
    "VWAP":          ["TREND", "SIDEWAYS"],
    "VOLUME":        ["TREND", "SIDEWAYS", "HIGH_VOL", "CRISIS"],
    "VOLATILITY":    ["HIGH_VOL", "CRISIS"],
    "MOMENTUM":      ["TREND", "SIDEWAYS"],
    "REGIME_FILTER": ["TREND", "SIDEWAYS", "HIGH_VOL", "CRISIS"],
    "TIME_FILTER":   ["TREND", "SIDEWAYS", "HIGH_VOL", "CRISIS"],
    "TREND_FILTER":  ["TREND"],
}

# Features known to contribute noise
_NOISY_FEATURES = {"SMA", "EMA"}

# Features that tend to over-fit at shorter timeframes
_SHORT_TF_SENSITIVE = {"SMA", "EMA", "TREND_FILTER", "ADX"}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class FailureAnalysis:
    canonical_id: str
    decision: str                        # REJECTED / NEEDS_MORE_RESEARCH / VIABLE_WITH_COSTS
    root_causes: list[str]               # list of FAILURE_CATEGORY keys
    helpful_factors: list[str]           # features that contributed positively
    harmful_factors: list[str]           # features that contributed negatively
    gross_edge: float                    # gross PnL before costs (0 if no paper data)
    execution_drag: float                # total execution cost drag
    net_edge: float                      # gross_edge - execution_drag
    recommendations: list[str]           # specific improvement suggestions


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class FailureAnalyzer:
    """Analyzes strategy failures and generates actionable recommendations."""

    # Thresholds
    COMMISSION_DRAG_GROSS_THRESHOLD = -30_000   # gross_pnl better than this
    COMMISSION_DRAG_NET_THRESHOLD = 0           # net_pnl must be negative
    LOW_PASS_RATE_THRESHOLD = 0.35
    NOISE_SENSITIVITY_THRESHOLD = 30.0
    CRISIS_FRAGILITY_THRESHOLD = 0.20

    def analyze(
        self,
        canonical_id: str,
        m8_data: dict,
        m9_data: dict | None,
        strategy_features: list[str],
    ) -> FailureAnalysis:
        """Produce a FailureAnalysis for one strategy."""
        root_causes: list[str] = []

        # Determine gross / net edge from M9 paper data
        gross_edge = 0.0
        execution_drag = 0.0
        net_edge = 0.0
        decision = "NEEDS_MORE_RESEARCH"

        if m9_data is not None:
            gross_pnl = m9_data.get("gross_pnl", 0.0)
            net_pnl = m9_data.get("net_pnl", 0.0)
            exec_drag = m9_data.get("exec_drag", 0.0)
            gross_edge = float(gross_pnl)
            execution_drag = float(exec_drag)
            net_edge = float(net_pnl)
            decision = m9_data.get("decision", "REJECTED")

            # COMMISSION_DRAG: gross was not catastrophically negative but net < 0
            if gross_pnl > self.COMMISSION_DRAG_GROSS_THRESHOLD and net_pnl < self.COMMISSION_DRAG_NET_THRESHOLD:
                root_causes.append("COMMISSION_DRAG")

        # LOW_PASS_RATE from M8
        avg_pr = m8_data.get("avg_pr", 0.0)
        if avg_pr < self.LOW_PASS_RATE_THRESHOLD:
            root_causes.append("LOW_PASS_RATE")

        # NOISE_SENSITIVITY from NSS
        nss = m8_data.get("nss", 0.0)
        if nss > self.NOISE_SENSITIVITY_THRESHOLD:
            root_causes.append("NOISE_SENSITIVITY")

        # REGIME_FRAGILITY — use robustness score as proxy (below 32 = marginal)
        robustness = m8_data.get("robustness", 0.0)
        if robustness < 32.0 and "MARGINAL" in m8_data.get("label", ""):
            root_causes.append("REGIME_FRAGILITY")

        # If no causes found, default to LOW_PASS_RATE as generic
        if not root_causes:
            root_causes.append("LOW_PASS_RATE")

        # Determine helpful vs harmful features
        helpful_factors = self._identify_helpful(strategy_features)
        harmful_factors = self._identify_harmful(strategy_features, root_causes)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            canonical_id, root_causes, strategy_features, m8_data, m9_data
        )

        return FailureAnalysis(
            canonical_id=canonical_id,
            decision=decision,
            root_causes=root_causes,
            helpful_factors=helpful_factors,
            harmful_factors=harmful_factors,
            gross_edge=gross_edge,
            execution_drag=execution_drag,
            net_edge=net_edge,
            recommendations=recommendations,
        )

    def analyze_all(self) -> dict[str, FailureAnalysis]:
        """Run analysis for all 10 M8 strategies."""
        results: dict[str, FailureAnalysis] = {}
        for canonical_id, m8_data in M8_ROBUSTNESS.items():
            m9_data = M9_RESULTS.get(canonical_id)
            features = STRATEGY_FEATURES.get(canonical_id, [])
            results[canonical_id] = self.analyze(canonical_id, m8_data, m9_data, features)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _identify_helpful(self, features: list[str]) -> list[str]:
        """Features with broad regime affinity or known positive contribution."""
        helpful = []
        for f in features:
            affinity = _FEATURE_REGIME_AFFINITY.get(f, [])
            # Helpful if covers 2+ regimes or is an explicit positive signal
            if len(affinity) >= 2 or f in {"BOLLINGER", "RSI", "VOLUME", "ATR", "VOLATILITY", "REGIME_FILTER"}:
                helpful.append(f)
        return helpful

    def _identify_harmful(self, features: list[str], root_causes: list[str]) -> list[str]:
        """Features that likely contributed to identified failures."""
        harmful = []
        for f in features:
            if "NOISE_SENSITIVITY" in root_causes and f in _SHORT_TF_SENSITIVE:
                harmful.append(f)
            elif "LOW_PASS_RATE" in root_causes and f in _NOISY_FEATURES:
                harmful.append(f)
            elif "COMMISSION_DRAG" in root_causes and f in {"SMA", "EMA"}:
                # Trend-following without regime filter → over-trading in choppy markets
                if f not in harmful:
                    harmful.append(f)
        return harmful

    def _generate_recommendations(
        self,
        canonical_id: str,
        root_causes: list[str],
        features: list[str],
        m8_data: dict,
        m9_data: dict | None,
    ) -> list[str]:
        recs: list[str] = []

        if "COMMISSION_DRAG" in root_causes:
            recs += [
                "Increase R:R ratio: target payoff_ratio >= 3:1 instead of current ~2:1",
                "Add regime filter: restrict to SIDEWAYS+CRISIS where pass_rate is highest",
                "Increase holding period from current ~14 days to reduce commission frequency",
                "Consider position size: current 10% cap may be too small for cost amortization",
                "Switch exit logic to ATR-based trailing stop to capture larger moves",
            ]

        if "LOW_PASS_RATE" in root_causes:
            recs += [
                "Tighten entry conditions: require confluence of 2+ signals before entry",
                "Add volume confirmation filter: only trade when volume > 20-day avg",
                "Apply regime filter: restrict to regimes where this strategy historically passes",
            ]

        if "NOISE_SENSITIVITY" in root_causes:
            recs += [
                "Move primary timeframe from 1H to 4H or 1D to reduce noise",
                "Add multi-timeframe filter: require alignment across 1D + 4H before entry",
                "Replace short-period MA with longer-period EMA (50+ vs 20) for stability",
            ]

        if "REGIME_FRAGILITY" in root_causes:
            recs += [
                "Add crisis regime filter: suspend trading when VIX > 30 equivalent",
                "Build separate crisis-mode parameter set with wider stops",
                "Include ATR-based position sizing to adapt to regime volatility",
            ]

        # Strategy-specific recommendations
        if canonical_id == "BB_SQUEEZE":
            recs.append(
                "BB_SQUEEZE specific: add ADX > 20 filter to avoid false squeezes in trending markets"
            )
        elif canonical_id == "DUAL_MA_TREND":
            recs.append(
                "DUAL_MA_TREND specific: replace SMA crossover with EMA+ADX to reduce whipsaws"
            )
        elif canonical_id == "SMA_CROSSOVER":
            recs.append(
                "SMA_CROSSOVER specific: avg_pr=0.096 is critically low — consider full replacement"
            )

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_recs: list[str] = []
        for r in recs:
            if r not in seen:
                seen.add(r)
                unique_recs.append(r)

        return unique_recs
