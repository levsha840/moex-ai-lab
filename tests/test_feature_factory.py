from core.features import FeatureFactory, FeatureFactoryConfig, build_features
from core.features.technical_indicators import atr, ema, pct_change, rsi, sma


def _candles(count=30, ticker="SBER"):
    rows = []
    for index in range(count):
        close = 100.0 + index
        rows.append(
            {
                "ticker": ticker,
                "ts": f"2026-01-01 10:{index:02d}:00",
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1000 + index * 10,
            }
        )
    return rows


def test_sma_and_ema():
    values = [1, 2, 3, 4, 5]
    assert sma(values, 3) == [None, None, 2.0, 3.0, 4.0]
    assert ema(values, 3)[2] == 2.0
    assert ema(values, 3)[-1] == 4.0


def test_rsi_atr_and_pct_change_have_expected_shapes():
    values = list(range(1, 20))
    assert len(rsi(values, 14)) == len(values)
    assert rsi(values, 14)[14] == 100.0
    changes = pct_change([100, 110, 121])
    assert changes[0] is None
    assert round(changes[1], 6) == 0.1
    assert round(changes[2], 6) == 0.1
    assert len(atr(values, values, values, 14)) == len(values)


def test_feature_factory_builds_rows_and_core_features():
    rows = build_features(_candles())
    assert len(rows) == 30
    last = rows[-1]
    assert last["ticker"] == "SBER"
    assert last["feature_sma_5"] is not None
    assert last["feature_ema_10"] is not None
    assert last["feature_rsi"] is not None
    assert last["feature_atr"] is not None
    assert last["feature_close_return_1"] is not None
    assert last["feature_volume_change_1"] is not None
    assert last["feature_range_pct"] is not None


def test_feature_factory_keeps_tickers_separate():
    config = FeatureFactoryConfig(sma_periods=(3,), ema_periods=(3,), rsi_period=3, atr_period=3, volatility_period=3)
    rows = _candles(5, "SBER") + _candles(5, "GAZP")
    result = FeatureFactory(config).build(reversed(rows))
    by_ticker = {ticker: [row for row in result if row["ticker"] == ticker] for ticker in {"SBER", "GAZP"}}
    assert by_ticker["SBER"][0]["feature_sma_3"] is None
    assert by_ticker["GAZP"][0]["feature_sma_3"] is None
    assert by_ticker["SBER"][-1]["feature_sma_3"] == 103.0
    assert by_ticker["GAZP"][-1]["feature_sma_3"] == 103.0


def test_feature_factory_rejects_missing_columns():
    try:
        build_features([{"ticker": "SBER"}])
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("ValueError expected")
