"""Feature provider, regime adapter, strategy runner, and provider factory for H-13.

Dependency direction: experiments/ → core/ only. Nothing in core/ imports from here.

AdxContinuationProviderFactory is defined here (not in services/) so the experiment
is self-contained. The Hypothesis Registry YAML references this class by dotted path:
  provider_factory: experiments.h13_adx_continuation.providers.AdxContinuationProviderFactory
"""
from __future__ import annotations

from typing import Any

from core.common import OrderSide
from core.costs.engine import ExecutionCostEngine
from core.costs.models import ExecutionRequest
from core.experiment.models import ExperimentConfig
from core.experiment.protocols import FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner
from core.features.technical_indicators import adx, atr, pct_change, rsi, rolling_std, sma
from core.regime.engine import MarketRegimeEngine
from core.regime.models import RegimeFeatures, RegimeSnapshot, RegimeType
from core.research_pipeline.adapters import ValidationReportAdapter
from core.validation.report import ValidationReportBuilder
from core.walkforward.engine import WalkForwardEngine
from core.walkforward.models import WalkForwardConfig, WalkForwardSummary, WalkForwardWindow
from core.walkforward.window_generator import WalkForwardWindowGenerator
from experiments.h13_adx_continuation.dataset import H13Dataset

# H-13 signal parameters
_ADX_THRESHOLD = 25.0
_RSI_LOW = 40.0
_RSI_HIGH = 60.0
_HOLD_BARS = 5  # bars to hold after entry before next signal check

_SMA_FAST_PERIOD = 20
_SMA_SLOW_PERIOD = 50
_RSI_PERIOD = 14
_ATR_PERIOD = 14
_ADX_PERIOD = 14
_VOL_PERIOD = 20


# ──────────────────────────────────────────────────────────────────────────────
# Feature Provider
# ──────────────────────────────────────────────────────────────────────────────

class H13FeatureProvider:
    """Computes H13Dataset from a list of OHLCV candle dicts.

    Candle dict keys: ticker, ts, open, high, low, close, volume.
    Data is injected via constructor so build_features() satisfies FeatureProvider protocol.
    """

    def __init__(self, candles: list[dict]) -> None:
        self._candles = candles

    def build_features(self, config: ExperimentConfig) -> H13Dataset:
        highs = [float(c["high"]) for c in self._candles]
        lows = [float(c["low"]) for c in self._candles]
        closes = [float(c["close"]) for c in self._candles]

        adx_vals = adx(highs, lows, closes, period=_ADX_PERIOD)
        rsi_vals = rsi(closes, period=_RSI_PERIOD)
        atr_vals = atr(highs, lows, closes, period=_ATR_PERIOD)
        sma_fast = sma(closes, period=_SMA_FAST_PERIOD)
        sma_slow = sma(closes, period=_SMA_SLOW_PERIOD)

        pct = pct_change(closes)
        safe_pct = [v if v is not None else 0.0 for v in pct]
        realized_vol = rolling_std(safe_pct, period=_VOL_PERIOD)

        return H13Dataset(
            closes=tuple(closes),
            highs=tuple(highs),
            lows=tuple(lows),
            adx_values=tuple(adx_vals),
            rsi_values=tuple(rsi_vals),
            atr_values=tuple(atr_vals),
            sma_fast_values=tuple(sma_fast),
            sma_slow_values=tuple(sma_slow),
            realized_vol_values=tuple(realized_vol),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Regime Adapter (H-13 specific: extracts last valid bar from H13Dataset)
# ──────────────────────────────────────────────────────────────────────────────

class H13RegimeProvider:
    """Classifies the last valid bar of an H13Dataset as a RegimeSnapshot.

    A new adapter is needed here because RegimeEngineAdapter passes its input
    directly to MarketRegimeEngine.classify(), which expects RegimeFeatures —
    not H13Dataset. This adapter extracts the last valid bar and bridges the gap.
    """

    def __init__(self) -> None:
        self._engine = MarketRegimeEngine()

    def classify(self, features: Any) -> RegimeSnapshot:
        dataset: H13Dataset = features
        n = len(dataset.closes)

        for i in range(n - 1, -1, -1):
            adx_val = dataset.adx_values[i]
            atr_val = dataset.atr_values[i]
            sma_f = dataset.sma_fast_values[i]
            sma_s = dataset.sma_slow_values[i]
            rv = dataset.realized_vol_values[i]
            close = dataset.closes[i]

            if any(v is None for v in [adx_val, atr_val, sma_f, sma_s, rv]):
                continue

            atr_pct = atr_val / close if close > 0.0 else 0.0  # type: ignore[operator]
            regime_features = RegimeFeatures(
                adx=adx_val,  # type: ignore[arg-type]
                atr_pct=atr_pct,
                sma_fast=sma_f,  # type: ignore[arg-type]
                sma_slow=sma_s,  # type: ignore[arg-type]
                realized_volatility=rv,  # type: ignore[arg-type]
            )
            return self._engine.classify(regime_features)

        return RegimeSnapshot(
            regime=RegimeType.UNKNOWN,
            confidence=0.0,
            reasons=["no valid indicators in H13Dataset"],
        )


# ──────────────────────────────────────────────────────────────────────────────
# Strategy Runner
# ──────────────────────────────────────────────────────────────────────────────

class H13StrategyRunner:
    """Walk-forward strategy runner for H-13 ADX Continuation.

    Signal: regime=TREND_UP AND ADX > 25 AND RSI ∈ [40, 60] → BUY.
    Hold: _HOLD_BARS bars after entry, then SELL.
    Evaluator key: "profitable" (bool) — True if window net PnL > 0.
    """

    def __init__(
        self,
        wf_engine: WalkForwardEngine,
        cost_engine: ExecutionCostEngine,
    ) -> None:
        self._wf = wf_engine
        self._cost = cost_engine
        self._regime_engine = MarketRegimeEngine()

    def run(self, config: ExperimentConfig, features: Any) -> WalkForwardSummary:
        dataset: H13Dataset = features
        n = len(dataset.closes)

        def _run_window(window: WalkForwardWindow) -> dict:
            trades: list[dict] = []
            hold_until: int = -1

            for bar in range(window.test_start, min(window.test_end, n)):
                if bar <= hold_until:
                    continue

                adx_val = dataset.adx_values[bar]
                rsi_val = dataset.rsi_values[bar]
                atr_val = dataset.atr_values[bar]
                sma_f = dataset.sma_fast_values[bar]
                sma_s = dataset.sma_slow_values[bar]
                rv = dataset.realized_vol_values[bar]
                close = dataset.closes[bar]

                if any(v is None for v in [adx_val, rsi_val, atr_val, sma_f, sma_s, rv]):
                    continue

                atr_pct = atr_val / close if close > 0.0 else 0.0  # type: ignore[operator]
                rf = RegimeFeatures(
                    adx=adx_val,  # type: ignore[arg-type]
                    atr_pct=atr_pct,
                    sma_fast=sma_f,  # type: ignore[arg-type]
                    sma_slow=sma_s,  # type: ignore[arg-type]
                    realized_volatility=rv,  # type: ignore[arg-type]
                )
                snapshot = self._regime_engine.classify(rf)

                signal_ok = (
                    snapshot.regime == RegimeType.TREND_UP
                    and adx_val > _ADX_THRESHOLD  # type: ignore[operator]
                    and _RSI_LOW <= rsi_val <= _RSI_HIGH  # type: ignore[operator]
                )
                if not signal_ok:
                    continue

                exit_bar = min(bar + _HOLD_BARS, window.test_end - 1, n - 1)
                exit_close = dataset.closes[exit_bar]

                buy = self._cost.calculate(
                    ExecutionRequest(
                        ticker=config.strategy_name,
                        side=OrderSide.BUY,
                        price=close,
                        quantity=1.0,
                    )
                )
                sell = self._cost.calculate(
                    ExecutionRequest(
                        ticker=config.strategy_name,
                        side=OrderSide.SELL,
                        price=exit_close,
                        quantity=1.0,
                    )
                )
                pnl = sell.effective_price - buy.effective_price
                trades.append({"pnl": pnl, "profitable": pnl > 0.0})
                hold_until = exit_bar

            total_pnl = sum(t["pnl"] for t in trades)
            return {
                "trades_count": len(trades),
                "total_pnl": total_pnl,
                "profitable": total_pnl > 0.0,
            }

        return self._wf.run(data_length=n, runner=_run_window)


class AdxContinuationProviderFactory:
    """Assembles H-13 ADX Continuation providers from a dataset.

    Registered in hypotheses/h_adx_continuation.yaml:
      provider_factory: experiments.h13_adx_continuation.providers.AdxContinuationProviderFactory
    The dataset parameter is duck-typed — any object with a .candles attribute works.
    """

    def create_providers(
        self,
        dataset: Any,
        wf_config: WalkForwardConfig,
    ) -> tuple[FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner]:
        candles = list(dataset.candles)
        return (
            H13FeatureProvider(candles),
            H13RegimeProvider(),
            H13StrategyRunner(
                wf_engine=WalkForwardEngine(WalkForwardWindowGenerator(wf_config)),
                cost_engine=ExecutionCostEngine(),
            ),
            ValidationReportAdapter(
                builder=ValidationReportBuilder(),
                evaluator=lambda result: result.get("profitable", False),
            ),
        )
