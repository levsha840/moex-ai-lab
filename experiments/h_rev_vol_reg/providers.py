"""Feature provider, regime adapter, strategy runner, and factory for H-REV-VOL-REG.

Signal logic:
  - Regime: ADX < 20 (market is ranging, no strong directional trend)
  - Entry: Bollinger Band z-score of price < -2.0 (price 2+ sigma below 20-bar mean)
  - Exit: time-based, after 8 bars

Registered in hypotheses/h_rev_vol_reg.yaml:
  provider_factory: experiments.h_rev_vol_reg.providers.RevVolRegProviderFactory
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
from experiments.h_rev_vol_reg.dataset import RevVolRegDataset

_BB_PERIOD = 20
_ADX_PERIOD = 14
_RSI_PERIOD = 14
_ATR_PERIOD = 14
_VOL_PERIOD = 20

_ADX_RANGING_THRESHOLD = 20.0
_BB_Z_ENTRY = -2.0
_HOLD_BARS = 8


# ─────────────────────────────────────────────────────────────────────────────
# Feature Provider
# ─────────────────────────────────────────────────────────────────────────────

class RevVolRegFeatureProvider:
    """Computes RevVolRegDataset from a list of OHLCV candle dicts.

    Candle dict keys: ticker, ts, open, high, low, close, volume.
    """

    def __init__(self, candles: list[dict]) -> None:
        self._candles = candles

    def build_features(self, config: ExperimentConfig) -> RevVolRegDataset:
        highs = [float(c["high"]) for c in self._candles]
        lows = [float(c["low"]) for c in self._candles]
        closes = [float(c["close"]) for c in self._candles]

        adx_vals = adx(highs, lows, closes, period=_ADX_PERIOD)
        rsi_vals = rsi(closes, period=_RSI_PERIOD)
        atr_vals = atr(highs, lows, closes, period=_ATR_PERIOD)

        # Bollinger Band z-score: (close - SMA_20) / rolling_std_20(price)
        ma20 = sma(closes, period=_BB_PERIOD)
        bb_std = rolling_std(closes, period=_BB_PERIOD)

        bb_zscore: list[float | None] = []
        bb_upper: list[float | None] = []
        bb_lower: list[float | None] = []
        for c, m, s in zip(closes, ma20, bb_std):
            if m is None or s is None or s == 0.0:
                bb_zscore.append(None)
                bb_upper.append(None)
                bb_lower.append(None)
            else:
                bb_zscore.append((c - m) / s)
                bb_upper.append(m + 2.0 * s)
                bb_lower.append(m - 2.0 * s)

        # Realised volatility: rolling std of pct returns
        pct = pct_change(closes)
        safe_pct = [v if v is not None else 0.0 for v in pct]
        realized_vol = rolling_std(safe_pct, period=_VOL_PERIOD)

        return RevVolRegDataset(
            closes=tuple(closes),
            highs=tuple(highs),
            lows=tuple(lows),
            adx_values=tuple(adx_vals),
            rsi_values=tuple(rsi_vals),
            bb_zscore_values=tuple(bb_zscore),
            realized_vol_values=tuple(realized_vol),
            atr_values=tuple(atr_vals),
            bb_upper_values=tuple(bb_upper),
            bb_lower_values=tuple(bb_lower),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Regime Adapter
# ─────────────────────────────────────────────────────────────────────────────

class RevVolRegRegimeProvider:
    """Classifies market regime for H-REV-VOL-REG from the last valid bar.

    Classification rule: ADX < 20 → RANGE; otherwise the bar is trending
    and mean-reversion entries are suppressed.
    """

    def classify(self, features: Any) -> RegimeSnapshot:
        dataset: RevVolRegDataset = features
        n = len(dataset.closes)

        for i in range(n - 1, -1, -1):
            adx_val = dataset.adx_values[i]
            if adx_val is None:
                continue

            if adx_val < _ADX_RANGING_THRESHOLD:
                confidence = 1.0 - (adx_val / _ADX_RANGING_THRESHOLD)
                return RegimeSnapshot(
                    regime=RegimeType.RANGE,
                    confidence=round(confidence, 4),
                    reasons=[f"ADX={adx_val:.1f} < {_ADX_RANGING_THRESHOLD:.0f} (ranging)"],
                )
            else:
                confidence = min(adx_val / 40.0, 1.0)
                return RegimeSnapshot(
                    regime=RegimeType.TREND_UP,
                    confidence=round(confidence, 4),
                    reasons=[f"ADX={adx_val:.1f} >= {_ADX_RANGING_THRESHOLD:.0f} (trending)"],
                )

        return RegimeSnapshot(
            regime=RegimeType.UNKNOWN,
            confidence=0.0,
            reasons=["no valid ADX in RevVolRegDataset"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# Strategy Runner
# ─────────────────────────────────────────────────────────────────────────────

class RevVolRegStrategyRunner:
    """Walk-forward strategy runner for H-REV-VOL-REG.

    Entry signal: ADX < 20 (ranging) AND bb_zscore < -2.0 (oversold) → BUY.
    Exit: time-based after _HOLD_BARS bars.
    Long-only mean-reversion strategy.
    """

    def __init__(
        self,
        wf_engine: WalkForwardEngine,
        cost_engine: ExecutionCostEngine,
    ) -> None:
        self._wf = wf_engine
        self._cost = cost_engine

    def run(self, config: ExperimentConfig, features: Any) -> WalkForwardSummary:
        dataset: RevVolRegDataset = features
        n = len(dataset.closes)

        def _run_window(window: WalkForwardWindow) -> dict:
            trades: list[dict] = []
            hold_until: int = -1

            for bar in range(window.test_start, min(window.test_end, n)):
                if bar <= hold_until:
                    continue

                adx_val = dataset.adx_values[bar]
                bb_z = dataset.bb_zscore_values[bar]
                atr_val = dataset.atr_values[bar]
                close = dataset.closes[bar]

                if any(v is None for v in [adx_val, bb_z, atr_val]):
                    continue

                signal_ok = (
                    adx_val < _ADX_RANGING_THRESHOLD  # type: ignore[operator]
                    and bb_z < _BB_Z_ENTRY  # type: ignore[operator]
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


# ─────────────────────────────────────────────────────────────────────────────
# Provider Factory
# ─────────────────────────────────────────────────────────────────────────────

class RevVolRegProviderFactory:
    """Assembles H-REV-VOL-REG providers from a dataset.

    Registered in hypotheses/h_rev_vol_reg.yaml:
      provider_factory: experiments.h_rev_vol_reg.providers.RevVolRegProviderFactory
    The dataset parameter is duck-typed — any object with a .candles attribute works.
    """

    def create_providers(
        self,
        dataset: Any,
        wf_config: WalkForwardConfig,
    ) -> tuple[FeatureProvider, RegimeProvider, StrategyRunner, ValidationRunner]:
        candles = list(dataset.candles)
        return (
            RevVolRegFeatureProvider(candles),
            RevVolRegRegimeProvider(),
            RevVolRegStrategyRunner(
                wf_engine=WalkForwardEngine(WalkForwardWindowGenerator(wf_config)),
                cost_engine=ExecutionCostEngine(),
            ),
            ValidationReportAdapter(
                builder=ValidationReportBuilder(),
                evaluator=lambda result: result.get("profitable", False),
            ),
        )
