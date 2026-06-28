"""Deterministic Trade Journal Generator.

Post-processing layer: re-simulates strategy signals on OHLCV data to produce
a structured trade journal for visualization. Does NOT touch Research Service.

Signal logic:
  - GenericProviderFactory subclasses: uses signal_type / hold_bars / signal_params
    from the factory class attributes (no code changes needed in those factories)
  - AdxContinuationProviderFactory: ADX > 25 AND RSI in [40, 60]  (hold 5)
  - RevVolRegProviderFactory:       ADX < 20 AND bb_zscore < -2.0 (hold 8)

Uses GenericOHLCVDataset as the unified feature surface for ALL hypotheses —
the generic features (ADX, RSI, SMA, BB zscore) cover all 10 hypothesis signals.

Walk-forward discipline: signals are only generated in TEST windows (no lookahead).
Train window bars [train_start, train_end) are never traded.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from core.walkforward.models import WalkForwardConfig, WalkForwardWindow
from core.walkforward.window_generator import WalkForwardWindowGenerator
from experiments.generic.dataset import GenericOHLCVDataset
from experiments.generic.providers import GenericFeatureProvider, GenericProviderFactory
from services.visual_backtest.models import TradeJournalEntry

# ─────────────────────────────────────────────────────────────────────────────
# Extended signal dispatcher (covers all 10 hypotheses)
# ─────────────────────────────────────────────────────────────────────────────

def _check_signal(
    ds: GenericOHLCVDataset,
    bar: int,
    signal_type: str,
    params: dict,
) -> bool:
    """Pure function: True if signal fires at `bar` given `signal_type` and `params`.

    Uses GenericOHLCVDataset as the unified feature surface.
    Covers all 8 generic signal types + adx_continuation + rev_vol_reg.
    """
    adx_val = ds.adx_values[bar]
    rsi_val = ds.rsi_values[bar]
    sma5    = ds.sma_5_values[bar]
    sma20   = ds.sma_20_values[bar]
    sma50   = ds.sma_50_values[bar]
    bb_z    = ds.bb_zscore_values[bar]
    rv      = ds.realized_vol_values[bar]
    close   = ds.closes[bar]
    p = params

    if signal_type == "rsi_oversold":
        return rsi_val is not None and rsi_val < p.get("rsi_threshold", 30.0)

    if signal_type == "rsi_momentum":
        return (rsi_val is not None and adx_val is not None
                and rsi_val > p.get("rsi_min", 55.0)
                and adx_val > p.get("adx_min", 20.0))

    if signal_type == "sma_crossover":
        if bar == 0:
            return False
        prev20 = ds.sma_20_values[bar - 1]
        prev50 = ds.sma_50_values[bar - 1]
        return (sma20 is not None and sma50 is not None
                and prev20 is not None and prev50 is not None
                and prev20 <= prev50 and sma20 > sma50)

    if signal_type == "momentum_pullback":
        return (sma20 is not None and sma50 is not None
                and close > sma50 and close < sma20)

    if signal_type == "vol_breakout":
        return (rv is not None and adx_val is not None
                and rv > p.get("vol_threshold", 0.010)
                and adx_val > p.get("adx_min", 20.0))

    if signal_type == "trend_strength":
        return (adx_val is not None and rsi_val is not None
                and adx_val > p.get("adx_min", 30.0)
                and rsi_val > p.get("rsi_min", 50.0))

    if signal_type == "bb_squeeze":
        return (bb_z is not None and rsi_val is not None
                and abs(bb_z) < p.get("bb_z_max", 0.5)
                and rsi_val > p.get("rsi_min", 50.0))

    if signal_type == "dual_ma_trend":
        return (sma5 is not None and sma20 is not None and sma50 is not None
                and sma5 > sma20 > sma50)

    # ── Non-generic hypotheses ──────────────────────────────────────────────
    if signal_type == "adx_continuation":
        # H13: ADX > threshold AND RSI in [low, high] (regime=TREND_UP implied by ADX)
        return (adx_val is not None and rsi_val is not None
                and adx_val > p.get("adx_min", 25.0)
                and p.get("rsi_low", 40.0) <= rsi_val <= p.get("rsi_high", 60.0))

    if signal_type == "rev_vol_reg":
        # H-REV-VOL-REG: ADX < threshold (ranging) AND BB z-score deeply oversold
        return (adx_val is not None and bb_z is not None
                and adx_val < p.get("adx_max", 20.0)
                and bb_z < p.get("bb_z_entry", -2.0))

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Factory introspection
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _SignalConfig:
    signal_type: str
    hold_bars: int
    signal_params: dict


def _extract_signal_config(factory: object) -> _SignalConfig:
    """Determine signal_type, hold_bars, and signal_params for any factory."""
    if isinstance(factory, GenericProviderFactory):
        return _SignalConfig(
            signal_type=factory.signal_type,
            hold_bars=factory.hold_bars,
            signal_params=dict(factory.signal_params),
        )

    cls_name = type(factory).__name__

    # AdxContinuationProviderFactory — H13
    if "AdxContinuation" in cls_name:
        return _SignalConfig(
            signal_type="adx_continuation",
            hold_bars=5,
            signal_params={"adx_min": 25.0, "rsi_low": 40.0, "rsi_high": 60.0},
        )

    # RevVolRegProviderFactory — H-REV-VOL-REG
    if "RevVolReg" in cls_name:
        return _SignalConfig(
            signal_type="rev_vol_reg",
            hold_bars=8,
            signal_params={"adx_max": 20.0, "bb_z_entry": -2.0},
        )

    raise ValueError(
        f"Cannot extract signal config from unknown factory: {cls_name}. "
        "Implement a GenericProviderFactory subclass or add a case to _extract_signal_config()."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Trade Journal Generator
# ─────────────────────────────────────────────────────────────────────────────

class TradeJournalGenerator:
    """Re-simulates strategy signals on OHLCV candles to produce a trade journal.

    Walk-forward discipline: trades are only generated in TEST windows.
    Train windows are used for feature warm-up only (no lookahead).

    Usage:
        generator = TradeJournalGenerator()
        journal = generator.generate(
            candles=candles,
            factory=registry.get_provider_factory("tmpl_h_bb_squeeze"),
            wf_config=WalkForwardConfig(train_size=60, test_size=20, step_size=20),
            initial_capital=1_000_000.0,
        )
    """

    def generate(
        self,
        candles: list[dict],
        factory: object,
        wf_config: WalkForwardConfig,
        initial_capital: float = 1_000_000.0,
    ) -> list[TradeJournalEntry]:
        """Generate deterministic trade journal from OHLCV candles.

        Args:
            candles:         List of OHLCV candle dicts with 'ts', 'close' keys.
            factory:         Any ProviderFactory (generic or hypothesis-specific).
            wf_config:       Walk-forward configuration (must match research config).
            initial_capital: Starting capital for equity simulation.

        Returns:
            Ordered list of TradeJournalEntry (one entry per completed trade).
        """
        if not candles:
            return []

        sig_cfg = _extract_signal_config(factory)
        timestamps = [c.get("ts") for c in candles]
        n = len(candles)

        # Build GenericOHLCVDataset — unified feature surface for all hypotheses
        from core.experiment.models import ExperimentConfig
        fp = GenericFeatureProvider(candles)
        exp_cfg = ExperimentConfig(
            experiment_id="vb_journal",
            hypothesis_id=sig_cfg.signal_type,
            dataset_id="",
            strategy_name=sig_cfg.signal_type,
            feature_set=[],
        )
        features: GenericOHLCVDataset = fp.build_features(exp_cfg)

        # Walk-forward windows — only TEST bars are tradeable (no lookahead)
        windows: list[WalkForwardWindow] = WalkForwardWindowGenerator(wf_config).generate(n)
        if not windows:
            return []

        trades: list[TradeJournalEntry] = []
        capital = initial_capital
        hold_until = -1  # last bar still in previous trade

        for window in windows:
            for bar in range(window.test_start, min(window.test_end, n)):
                if bar <= hold_until:
                    continue  # still holding previous trade

                if not _check_signal(features, bar, sig_cfg.signal_type, sig_cfg.signal_params):
                    continue

                entry_price = features.closes[bar]
                exit_bar = min(bar + sig_cfg.hold_bars, window.test_end - 1, n - 1)
                exit_price = features.closes[exit_bar]
                exit_reason = "END_OF_DATA" if exit_bar == n - 1 else "TIME_EXIT"

                entry = TradeJournalEntry.build(
                    trade_id=f"t{len(trades):04d}_{uuid4().hex[:6]}",
                    entry_bar=bar,
                    entry_price=entry_price,
                    exit_bar=exit_bar,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    capital_before=capital,
                    entry_timestamp=timestamps[bar],
                    exit_timestamp=timestamps[exit_bar],
                )
                trades.append(entry)
                capital = entry.capital_after
                hold_until = exit_bar

        return trades
