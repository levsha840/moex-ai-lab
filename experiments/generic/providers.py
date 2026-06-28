"""Generic provider infrastructure for parameterised hypotheses.

Design:
  GenericProviderFactory (base class)
    signal_type: str   — dispatched to _check_signal()
    hold_bars: int     — time-based exit
    signal_params: dict — signal-specific thresholds

  Subclass example:
    class RsiOversoldProviderFactory(GenericProviderFactory):
        signal_type = "rsi_oversold"
        hold_bars = 5
        signal_params = {"rsi_threshold": 30.0}

  YAML field:
    provider_factory: experiments.h_rsi_oversold.providers.RsiOversoldProviderFactory

Supported signal_types (long-only entries):
  rsi_oversold       — RSI < rsi_threshold
  rsi_momentum       — RSI > rsi_min AND ADX > adx_min
  sma_crossover      — SMA_20 crosses above SMA_50
  momentum_pullback  — close > SMA_50 AND close < SMA_20
  vol_breakout       — realized_vol > vol_threshold AND ADX > adx_min
  trend_strength     — ADX > adx_min AND RSI > rsi_min
  bb_squeeze         — |bb_zscore| < bb_z_max AND RSI > rsi_min
  dual_ma_trend      — SMA_5 > SMA_20 > SMA_50
"""
from __future__ import annotations

from typing import Any

from core.common import OrderSide
from core.costs.engine import ExecutionCostEngine
from core.costs.models import ExecutionRequest
from core.experiment.models import ExperimentConfig
from core.experiment.protocols import FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner
from core.features.technical_indicators import adx, atr, pct_change, rsi, rolling_std, sma
from core.regime.models import RegimeSnapshot, RegimeType
from core.research_pipeline.adapters import ValidationReportAdapter
from core.validation.report import ValidationReportBuilder
from core.walkforward.engine import WalkForwardEngine
from core.walkforward.models import WalkForwardConfig, WalkForwardSummary, WalkForwardWindow
from core.walkforward.window_generator import WalkForwardWindowGenerator
from experiments.generic.dataset import GenericOHLCVDataset

_ADX_PERIOD = 14
_RSI_PERIOD = 14
_ATR_PERIOD = 14
_BB_PERIOD = 20
_VOL_PERIOD = 20
_SMA_FAST = 5
_SMA_MED = 20
_SMA_SLOW = 50
_REGIME_RANGING_ADX = 20.0


# ─────────────────────────────────────────────────────────────────────────────
# Feature Provider
# ─────────────────────────────────────────────────────────────────────────────

class GenericFeatureProvider:
    """Computes GenericOHLCVDataset from raw OHLCV candle dicts."""

    def __init__(self, candles: list[dict]) -> None:
        self._candles = candles

    def build_features(self, config: ExperimentConfig) -> GenericOHLCVDataset:
        highs = [float(c["high"]) for c in self._candles]
        lows = [float(c["low"]) for c in self._candles]
        closes = [float(c["close"]) for c in self._candles]

        adx_vals = adx(highs, lows, closes, period=_ADX_PERIOD)
        rsi_vals = rsi(closes, period=_RSI_PERIOD)
        atr_vals = atr(highs, lows, closes, period=_ATR_PERIOD)
        sma5 = sma(closes, period=_SMA_FAST)
        sma20 = sma(closes, period=_SMA_MED)
        sma50 = sma(closes, period=_SMA_SLOW)

        bb_std = rolling_std(closes, period=_BB_PERIOD)
        bb_zscore: list[float | None] = []
        for c, m, s in zip(closes, sma20, bb_std):
            if m is None or s is None or s == 0.0:
                bb_zscore.append(None)
            else:
                bb_zscore.append((c - m) / s)

        pct = pct_change(closes)
        safe_pct = [v if v is not None else 0.0 for v in pct]
        realized_vol = rolling_std(safe_pct, period=_VOL_PERIOD)

        return GenericOHLCVDataset(
            closes=tuple(closes),
            highs=tuple(highs),
            lows=tuple(lows),
            adx_values=tuple(adx_vals),
            rsi_values=tuple(rsi_vals),
            atr_values=tuple(atr_vals),
            sma_5_values=tuple(sma5),
            sma_20_values=tuple(sma20),
            sma_50_values=tuple(sma50),
            bb_zscore_values=tuple(bb_zscore),
            realized_vol_values=tuple(realized_vol),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Regime Adapter
# ─────────────────────────────────────────────────────────────────────────────

class GenericRegimeProvider:
    """Classifies last valid bar: RANGE if ADX < 20, TREND_UP otherwise."""

    def classify(self, features: Any) -> RegimeSnapshot:
        dataset: GenericOHLCVDataset = features
        for i in range(len(dataset.closes) - 1, -1, -1):
            adx_val = dataset.adx_values[i]
            if adx_val is None:
                continue
            if adx_val < _REGIME_RANGING_ADX:
                return RegimeSnapshot(
                    regime=RegimeType.RANGE,
                    confidence=round(1.0 - adx_val / _REGIME_RANGING_ADX, 4),
                    reasons=[f"ADX={adx_val:.1f} < {_REGIME_RANGING_ADX:.0f}"],
                )
            return RegimeSnapshot(
                regime=RegimeType.TREND_UP,
                confidence=round(min(adx_val / 40.0, 1.0), 4),
                reasons=[f"ADX={adx_val:.1f} >= {_REGIME_RANGING_ADX:.0f}"],
            )
        return RegimeSnapshot(
            regime=RegimeType.UNKNOWN, confidence=0.0, reasons=["no valid ADX"]
        )


# ─────────────────────────────────────────────────────────────────────────────
# Strategy Runner
# ─────────────────────────────────────────────────────────────────────────────

class GenericStrategyRunner:
    """Walk-forward runner parameterised by signal_type and hold_bars.

    All signals are long-only (BUY entry, time-based SELL exit).
    """

    def __init__(
        self,
        signal_type: str,
        hold_bars: int,
        signal_params: dict,
        wf_engine: WalkForwardEngine,
        cost_engine: ExecutionCostEngine,
    ) -> None:
        self._signal_type = signal_type
        self._hold_bars = hold_bars
        self._signal_params = signal_params
        self._wf = wf_engine
        self._cost = cost_engine

    def run(self, config: ExperimentConfig, features: Any) -> WalkForwardSummary:
        dataset: GenericOHLCVDataset = features
        n = len(dataset.closes)

        def _run_window(window: WalkForwardWindow) -> dict:
            trades: list[dict] = []
            hold_until = -1

            for bar in range(window.test_start, min(window.test_end, n)):
                if bar <= hold_until:
                    continue
                if not self._check_signal(dataset, bar):
                    continue

                close = dataset.closes[bar]
                exit_bar = min(bar + self._hold_bars, window.test_end - 1, n - 1)
                exit_close = dataset.closes[exit_bar]

                buy = self._cost.calculate(ExecutionRequest(
                    ticker=config.strategy_name, side=OrderSide.BUY,
                    price=close, quantity=1.0,
                ))
                sell = self._cost.calculate(ExecutionRequest(
                    ticker=config.strategy_name, side=OrderSide.SELL,
                    price=exit_close, quantity=1.0,
                ))
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

    def _check_signal(self, ds: GenericOHLCVDataset, bar: int) -> bool:
        p = self._signal_params
        adx_val = ds.adx_values[bar]
        rsi_val = ds.rsi_values[bar]
        sma5 = ds.sma_5_values[bar]
        sma20 = ds.sma_20_values[bar]
        sma50 = ds.sma_50_values[bar]
        bb_z = ds.bb_zscore_values[bar]
        rv = ds.realized_vol_values[bar]
        close = ds.closes[bar]

        st = self._signal_type

        if st == "rsi_oversold":
            return rsi_val is not None and rsi_val < p.get("rsi_threshold", 30.0)

        if st == "rsi_momentum":
            return (
                rsi_val is not None and adx_val is not None
                and rsi_val > p.get("rsi_min", 55.0)
                and adx_val > p.get("adx_min", 20.0)
            )

        if st == "sma_crossover":
            if bar == 0:
                return False
            prev20 = ds.sma_20_values[bar - 1]
            prev50 = ds.sma_50_values[bar - 1]
            return (
                sma20 is not None and sma50 is not None
                and prev20 is not None and prev50 is not None
                and prev20 <= prev50 and sma20 > sma50
            )

        if st == "momentum_pullback":
            return (
                sma20 is not None and sma50 is not None
                and close > sma50 and close < sma20
            )

        if st == "vol_breakout":
            return (
                rv is not None and adx_val is not None
                and rv > p.get("vol_threshold", 0.010)
                and adx_val > p.get("adx_min", 20.0)
            )

        if st == "trend_strength":
            return (
                adx_val is not None and rsi_val is not None
                and adx_val > p.get("adx_min", 30.0)
                and rsi_val > p.get("rsi_min", 50.0)
            )

        if st == "bb_squeeze":
            return (
                bb_z is not None and rsi_val is not None
                and abs(bb_z) < p.get("bb_z_max", 0.5)
                and rsi_val > p.get("rsi_min", 50.0)
            )

        if st == "dual_ma_trend":
            return (
                sma5 is not None and sma20 is not None and sma50 is not None
                and sma5 > sma20 > sma50
            )

        return False


# ─────────────────────────────────────────────────────────────────────────────
# Base Provider Factory
# ─────────────────────────────────────────────────────────────────────────────

class GenericProviderFactory:
    """Base factory for generic hypotheses. Subclasses set class attributes.

    Subclass pattern (in experiments/h_<name>/providers.py):
        class MyFactory(GenericProviderFactory):
            signal_type = "rsi_oversold"
            hold_bars = 5
            signal_params = {"rsi_threshold": 30.0}

    YAML:
        provider_factory: experiments.h_<name>.providers.MyFactory
    """

    signal_type: str = ""
    hold_bars: int = 5
    signal_params: dict = {}

    def create_providers(
        self,
        dataset: Any,
        wf_config: WalkForwardConfig,
    ) -> tuple[FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner]:
        candles = list(dataset.candles)
        return (
            GenericFeatureProvider(candles),
            GenericRegimeProvider(),
            GenericStrategyRunner(
                signal_type=self.signal_type,
                hold_bars=self.hold_bars,
                signal_params=dict(self.signal_params),
                wf_engine=WalkForwardEngine(WalkForwardWindowGenerator(wf_config)),
                cost_engine=ExecutionCostEngine(),
            ),
            ValidationReportAdapter(
                builder=ValidationReportBuilder(),
                evaluator=lambda result: result.get("profitable", False),
            ),
        )
