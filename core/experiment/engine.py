from __future__ import annotations

from core.experiment.models import ExperimentConfig, ExperimentResult, ExperimentStage
from core.experiment.protocols import (
    FeatureProvider,
    RegimeProvider,
    StrategyRunner,
    ValidationRunner,
)


class ExperimentRunner:
    """Orchestrates the research experiment pipeline via injected protocols.

    Does not know about MOEX, brokers, databases, or concrete strategy
    implementations. All behaviour is provided through dependency injection.
    """

    def __init__(
        self,
        feature_provider: FeatureProvider,
        regime_provider: RegimeProvider,
        strategy_runner: StrategyRunner,
        validation_runner: ValidationRunner,
    ) -> None:
        self._feature_provider = feature_provider
        self._regime_provider = regime_provider
        self._strategy_runner = strategy_runner
        self._validation_runner = validation_runner

    def run(self, config: ExperimentConfig) -> ExperimentResult:
        """Execute the full experiment pipeline and return a result.

        If any stage raises, the stage is marked FAILED and the exception
        propagates unchanged — nothing is suppressed.
        """
        stage = ExperimentStage.INITIALIZED
        regime = None
        validation = None

        try:
            features = self._feature_provider.build_features(config)
            stage = ExperimentStage.FEATURES_READY

            regime = self._regime_provider.classify(features)
            stage = ExperimentStage.REGIME_CLASSIFIED

            strategy_result = self._strategy_runner.run(config, features)
            stage = ExperimentStage.STRATEGY_EXECUTED

            validation = self._validation_runner.validate(strategy_result)
            stage = ExperimentStage.VALIDATED

        except Exception:
            stage = ExperimentStage.FAILED
            raise

        return ExperimentResult(
            config=config,
            stage=stage,
            regime=regime,
            validation=validation,
            metadata={},
        )
