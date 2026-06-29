"""
M10 Alpha Discovery Engine — Main Orchestrator

Connects FailureAnalyzer, FeatureImportanceCalculator, NetEdgePredictor,
AlphaComposer, DiscoveryQueue, and SelfLearning into a single pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from services.alpha_discovery.failure_analyzer import (
    FailureAnalyzer,
    FailureAnalysis,
    M8_ROBUSTNESS,
    M9_RESULTS,
    STRATEGY_FEATURES,
)
from services.alpha_discovery.feature_importance import (
    FeatureImportanceCalculator,
    FeatureScore,
)
from services.alpha_discovery.net_edge_predictor import NetEdgePredictor, NetEdgePrediction
from services.alpha_discovery.alpha_composer import AlphaComposer, StrategyDraft
from services.alpha_discovery.discovery_queue import DiscoveryQueue, QueueEntry
from services.alpha_discovery.self_learning import SelfLearning


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------

@dataclass
class AlphaDiscoveryReport:
    failure_analyses: dict[str, FailureAnalysis]
    feature_scores: dict[str, FeatureScore]
    strategy_drafts: list[StrategyDraft]
    queue: list[QueueEntry]
    learning_weights: dict[str, float]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AlphaDiscoveryEngine:
    """
    M10 Alpha Discovery Engine.

    Full pipeline:
    1. Load all data sources (embedded + file-based)
    2. Analyze strategy failures
    3. Compute feature importance
    4. Update self-learning weights
    5. Compose new strategy hypotheses
    6. Predict net edge for each
    7. Build discovery queue
    8. Return complete report
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._failure_analyzer = FailureAnalyzer()
        self._feature_importance = FeatureImportanceCalculator()
        self._net_edge_predictor = NetEdgePredictor()
        self._alpha_composer = AlphaComposer()
        self._queue = DiscoveryQueue()
        self._self_learning = SelfLearning()

    def run(self) -> AlphaDiscoveryReport:
        """Execute the full M10 pipeline and return a complete report."""

        # Step 1: Analyze all strategy failures
        failure_analyses = self._failure_analyzer.analyze_all()

        # Step 2: Compute feature importance from M8 data
        feature_scores = self._feature_importance.compute()

        # Step 3: Self-learning already applied M9 outcomes in __init__
        learning_weights = self._self_learning.get_weights()

        # Step 4: Compose new strategy drafts
        existing_strategy_ids = list(STRATEGY_FEATURES.keys())
        strategy_drafts = self._alpha_composer.compose(
            feature_scores=feature_scores,
            existing_strategies=existing_strategy_ids,
            net_edge_predictor=self._net_edge_predictor,
            n_drafts=10,
        )

        # Step 5: Build discovery queue
        queue = DiscoveryQueue()
        for draft in strategy_drafts:
            queue.enqueue(draft)
        ranked_queue = queue.prioritize()

        return AlphaDiscoveryReport(
            failure_analyses=failure_analyses,
            feature_scores=feature_scores,
            strategy_drafts=strategy_drafts,
            queue=ranked_queue,
            learning_weights=learning_weights,
        )
