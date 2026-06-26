"""Feature generation layer for intraday candles."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from core.features.technical_indicators import atr, ema, pct_change, rolling_std, rsi, sma

Candle = dict[str, Any]
FeatureRow = dict[str, Any]


@dataclass(frozen=True)
class FeatureFactoryConfig:
    sma_periods: tuple[int, ...] = (5, 10, 20)
    ema_periods: tuple[int, ...] = (5, 10, 20)
    rsi_period: int = 14
    atr_period: int = 14
    volatility_period: int = 20
    required_columns: tuple[str, ...] = field(
        default=("ticker", "ts", "open", "high", "low", "close", "volume")
    )


class FeatureFactory:
    """Builds deterministic technical features from OHLCV candle rows."""

    def __init__(self, config: FeatureFactoryConfig | None = None) -> None:
        self.config = config or FeatureFactoryConfig()

    def build(self, candles: Iterable[Candle]) -> list[FeatureRow]:
        rows = [dict(candle) for candle in candles]
        if not rows:
            return []

        self._validate(rows)
        rows.sort(key=lambda row: (str(row["ticker"]), row["ts"]))

        result: list[FeatureRow] = []
        for ticker in sorted({str(row["ticker"]) for row in rows}):
            ticker_rows = [row for row in rows if str(row["ticker"]) == ticker]
            result.extend(self._build_for_ticker(ticker_rows))
        return result

    def _validate(self, rows: list[Candle]) -> None:
        for row in rows:
            missing = [column for column in self.config.required_columns if column not in row]
            if missing:
                raise ValueError(f"candle row is missing required columns: {missing}")

    def _build_for_ticker(self, rows: list[Candle]) -> list[FeatureRow]:
        closes = [float(row["close"]) for row in rows]
        highs = [float(row["high"]) for row in rows]
        lows = [float(row["low"]) for row in rows]
        opens = [float(row["open"]) for row in rows]
        volumes = [float(row["volume"]) for row in rows]

        close_returns = pct_change(closes)
        volume_changes = pct_change(volumes)
        atr_values = atr(highs, lows, closes, self.config.atr_period)
        rsi_values = rsi(closes, self.config.rsi_period)
        volatility_values = rolling_std([value or 0.0 for value in close_returns], self.config.volatility_period)

        sma_values = {period: sma(closes, period) for period in self.config.sma_periods}
        ema_values = {period: ema(closes, period) for period in self.config.ema_periods}

        feature_rows: list[FeatureRow] = []
        for index, row in enumerate(rows):
            close = closes[index]
            open_price = opens[index]
            high = highs[index]
            low = lows[index]
            candle_range = high - low

            feature_row: FeatureRow = dict(row)
            feature_row.update(
                {
                    "feature_close_return_1": close_returns[index],
                    "feature_volume_change_1": volume_changes[index],
                    "feature_intrabar_return": None if open_price == 0 else (close / open_price) - 1.0,
                    "feature_range_pct": None if close == 0 else candle_range / close,
                    "feature_rsi": rsi_values[index],
                    "feature_atr": atr_values[index],
                    "feature_volatility": volatility_values[index],
                }
            )

            for period, values in sma_values.items():
                feature_row[f"feature_sma_{period}"] = values[index]
                feature_row[f"feature_close_to_sma_{period}"] = (
                    None if values[index] in (None, 0) else (close / float(values[index])) - 1.0
                )

            for period, values in ema_values.items():
                feature_row[f"feature_ema_{period}"] = values[index]
                feature_row[f"feature_close_to_ema_{period}"] = (
                    None if values[index] in (None, 0) else (close / float(values[index])) - 1.0
                )

            feature_rows.append(feature_row)

        return feature_rows


def build_features(candles: Iterable[Candle], config: FeatureFactoryConfig | None = None) -> list[FeatureRow]:
    return FeatureFactory(config).build(candles)
