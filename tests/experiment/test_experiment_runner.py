from __future__ import annotations

import pytest

from core.experiment import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentRunner,
    ExperimentStage,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _config(**kwargs) -> ExperimentConfig:
    defaults = dict(
        experiment_id="exp_001",
        hypothesis_id="hyp_001",
        dataset_id="ds_001",
        strategy_name="test_strategy",
        feature_set=["rsi_14", "sma_50"],
    )
    defaults.update(kwargs)
    return ExperimentConfig(**defaults)


class _StubFeatureProvider:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.calls: list = []

    def build_features(self, config):
        self.calls.append(config)
        return self.return_value


class _StubRegimeProvider:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.calls: list = []

    def classify(self, features):
        self.calls.append(features)
        return self.return_value


class _StubStrategyRunner:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.calls: list = []

    def run(self, config, features):
        self.calls.append((config, features))
        return self.return_value


class _StubValidationRunner:
    def __init__(self, return_value=None):
        self.return_value = return_value
        self.calls: list = []

    def validate(self, strategy_result):
        self.calls.append(strategy_result)
        return self.return_value


class _RaisingStrategyRunner:
    def __init__(self, exc: Exception):
        self._exc = exc

    def run(self, config, features):
        raise self._exc


def _make_engine(
    features=None,
    regime=None,
    strategy_result=None,
    validation=None,
    strategy_runner=None,
) -> tuple[ExperimentRunner, _StubFeatureProvider, _StubRegimeProvider, _StubStrategyRunner, _StubValidationRunner]:
    fp = _StubFeatureProvider(return_value=features)
    rp = _StubRegimeProvider(return_value=regime)
    sr = strategy_runner or _StubStrategyRunner(return_value=strategy_result)
    vr = _StubValidationRunner(return_value=validation)
    engine = ExperimentRunner(
        feature_provider=fp,
        regime_provider=rp,
        strategy_runner=sr,
        validation_runner=vr,
    )
    return engine, fp, rp, sr, vr


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline success
# ──────────────────────────────────────────────────────────────────────────────

def test_pipeline_success_returns_result():
    engine, *_ = _make_engine(
        features={"rsi_14": 28.0},
        regime={"type": "TREND_UP"},
        strategy_result={"sharpe": 1.3},
        validation={"status": "PASS"},
    )
    result = engine.run(_config())
    assert isinstance(result, ExperimentResult)


def test_pipeline_success_stage_is_validated():
    engine, *_ = _make_engine()
    result = engine.run(_config())
    assert result.stage == ExperimentStage.VALIDATED


def test_result_contains_original_config():
    config = _config(experiment_id="my_exp")
    engine, *_ = _make_engine()
    result = engine.run(config)
    assert result.config is config


def test_result_contains_regime_from_provider():
    regime_value = {"type": "RANGE"}
    engine, *_ = _make_engine(regime=regime_value)
    result = engine.run(_config())
    assert result.regime is regime_value


def test_result_contains_validation_from_runner():
    validation_value = {"status": "FAIL"}
    engine, *_ = _make_engine(validation=validation_value)
    result = engine.run(_config())
    assert result.validation is validation_value


# ──────────────────────────────────────────────────────────────────────────────
# Providers are called with correct arguments
# ──────────────────────────────────────────────────────────────────────────────

def test_feature_provider_called_with_config():
    config = _config()
    engine, fp, *_ = _make_engine()
    engine.run(config)
    assert len(fp.calls) == 1
    assert fp.calls[0] is config


def test_regime_provider_called_with_features_from_feature_provider():
    features = {"rsi_14": 30.0, "sma_50": 105.0}
    engine, _, rp, *_ = _make_engine(features=features)
    engine.run(_config())
    assert len(rp.calls) == 1
    assert rp.calls[0] is features


def test_strategy_runner_called_with_config_and_features():
    config = _config()
    features = {"rsi_14": 22.0}
    engine, _, _, sr, _ = _make_engine(features=features)
    engine.run(config)
    assert len(sr.calls) == 1
    received_config, received_features = sr.calls[0]
    assert received_config is config
    assert received_features is features


def test_validation_runner_called_with_strategy_result():
    strategy_result = {"trades": 42, "sharpe": 0.95}
    engine, _, _, _, vr = _make_engine(strategy_result=strategy_result)
    engine.run(_config())
    assert len(vr.calls) == 1
    assert vr.calls[0] is strategy_result


# ──────────────────────────────────────────────────────────────────────────────
# Correct execution order
# ──────────────────────────────────────────────────────────────────────────────

def test_correct_order():
    call_log: list[str] = []

    class LoggingFeatureProvider:
        def build_features(self, config):
            call_log.append("features")
            return {}

    class LoggingRegimeProvider:
        def classify(self, features):
            call_log.append("regime")
            return {}

    class LoggingStrategyRunner:
        def run(self, config, features):
            call_log.append("strategy")
            return {}

    class LoggingValidationRunner:
        def validate(self, result):
            call_log.append("validation")
            return {}

    engine = ExperimentRunner(
        feature_provider=LoggingFeatureProvider(),
        regime_provider=LoggingRegimeProvider(),
        strategy_runner=LoggingStrategyRunner(),
        validation_runner=LoggingValidationRunner(),
    )
    engine.run(_config())
    assert call_log == ["features", "regime", "strategy", "validation"]


# ──────────────────────────────────────────────────────────────────────────────
# Dependency injection only (no concrete imports in engine)
# ──────────────────────────────────────────────────────────────────────────────

def test_engine_does_not_import_concrete_engines():
    import inspect
    import core.experiment.engine as engine_module

    source = inspect.getsource(engine_module)
    # The engine must not reference concrete research/domain implementations
    forbidden = [
        "from core.regime",
        "from core.validation",
        "from core.paper",
        "from core.allocation",
        "from core.costs",
        "from core.walkforward",
        "from core.risk",
        "from core.strategy",
        "MarketRegimeEngine",
        "ValidationReportBuilder",
        "WalkForwardEngine",
    ]
    for token in forbidden:
        assert token not in source, f"engine.py must not reference '{token}'"


# ──────────────────────────────────────────────────────────────────────────────
# Determinism
# ──────────────────────────────────────────────────────────────────────────────

def test_deterministic_same_result_on_repeated_calls():
    config = _config()
    features = {"rsi_14": 29.5}
    regime = {"type": "TREND_DOWN"}
    strategy_result = {"pnl": -50.0}
    validation = {"status": "FAIL"}

    engine, *_ = _make_engine(
        features=features,
        regime=regime,
        strategy_result=strategy_result,
        validation=validation,
    )

    result_a = engine.run(config)
    result_b = engine.run(config)

    assert result_a.stage == result_b.stage
    assert result_a.regime is result_b.regime
    assert result_a.validation is result_b.validation


# ──────────────────────────────────────────────────────────────────────────────
# Exception propagation
# ──────────────────────────────────────────────────────────────────────────────

def test_exception_from_feature_provider_propagates():
    class FailingFeatureProvider:
        def build_features(self, config):
            raise RuntimeError("feature build failed")

    engine = ExperimentRunner(
        feature_provider=FailingFeatureProvider(),
        regime_provider=_StubRegimeProvider(),
        strategy_runner=_StubStrategyRunner(),
        validation_runner=_StubValidationRunner(),
    )
    with pytest.raises(RuntimeError, match="feature build failed"):
        engine.run(_config())


def test_exception_from_regime_provider_propagates():
    class FailingRegimeProvider:
        def classify(self, features):
            raise ValueError("regime classification error")

    engine = ExperimentRunner(
        feature_provider=_StubFeatureProvider(),
        regime_provider=FailingRegimeProvider(),
        strategy_runner=_StubStrategyRunner(),
        validation_runner=_StubValidationRunner(),
    )
    with pytest.raises(ValueError, match="regime classification error"):
        engine.run(_config())


def test_exception_from_strategy_runner_propagates():
    engine, *_ = _make_engine(
        strategy_runner=_RaisingStrategyRunner(RuntimeError("strategy crashed")),
    )
    with pytest.raises(RuntimeError, match="strategy crashed"):
        engine.run(_config())


def test_exception_from_validation_runner_propagates():
    class FailingValidationRunner:
        def validate(self, strategy_result):
            raise TypeError("invalid result type")

    engine = ExperimentRunner(
        feature_provider=_StubFeatureProvider(),
        regime_provider=_StubRegimeProvider(),
        strategy_runner=_StubStrategyRunner(),
        validation_runner=FailingValidationRunner(),
    )
    with pytest.raises(TypeError, match="invalid result type"):
        engine.run(_config())


def test_exception_preserves_original_type_and_message():
    class CustomError(Exception):
        pass

    class FailingRunner:
        def run(self, config, features):
            raise CustomError("original message")

    engine, *_ = _make_engine(strategy_runner=FailingRunner())
    with pytest.raises(CustomError, match="original message"):
        engine.run(_config())


# ──────────────────────────────────────────────────────────────────────────────
# Failed stage: subsequent stages are not executed after failure
# ──────────────────────────────────────────────────────────────────────────────

def test_validation_not_called_when_strategy_runner_fails():
    vr = _StubValidationRunner(return_value={"status": "PASS"})
    engine = ExperimentRunner(
        feature_provider=_StubFeatureProvider(),
        regime_provider=_StubRegimeProvider(),
        strategy_runner=_RaisingStrategyRunner(RuntimeError("crash")),
        validation_runner=vr,
    )
    with pytest.raises(RuntimeError):
        engine.run(_config())
    assert vr.calls == []


def test_strategy_and_validation_not_called_when_regime_fails():
    sr = _StubStrategyRunner()
    vr = _StubValidationRunner()

    class FailingRegime:
        def classify(self, features):
            raise RuntimeError("regime error")

    engine = ExperimentRunner(
        feature_provider=_StubFeatureProvider(),
        regime_provider=FailingRegime(),
        strategy_runner=sr,
        validation_runner=vr,
    )
    with pytest.raises(RuntimeError):
        engine.run(_config())

    assert sr.calls == []
    assert vr.calls == []


def test_each_provider_called_exactly_once_on_success():
    engine, fp, rp, sr, vr = _make_engine()
    engine.run(_config())
    assert len(fp.calls) == 1
    assert len(rp.calls) == 1
    assert len(sr.calls) == 1
    assert len(vr.calls) == 1
