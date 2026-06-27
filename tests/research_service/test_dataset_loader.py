import csv
import json
from pathlib import Path

import pytest

from services.research.dataset import DatasetLoader, OhlcvDataset


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _write_dataset(tmp_path: Path, dataset_id: str, rows: list[dict], meta: dict) -> Path:
    ds_dir = tmp_path / "datasets" / dataset_id
    ds_dir.mkdir(parents=True)

    with open(ds_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f)

    csv_path = ds_dir / "ohlcv.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["datetime", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)

    return tmp_path


def _sample_rows(n: int = 5) -> list[dict]:
    return [
        {
            "datetime": f"2023-01-09 {10 + i}:00:00",
            "open": str(230.0 + i),
            "high": str(235.0 + i),
            "low": str(228.0 + i),
            "close": str(232.0 + i),
            "volume": str(500_000 + i * 1000),
        }
        for i in range(n)
    ]


def _sample_meta(ticker: str = "SBER", timeframe: str = "1h") -> dict:
    return {"ticker": ticker, "timeframe": timeframe}


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestDatasetLoaderHappyPath:
    def test_loads_ohlcv_dataset(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(3), _sample_meta())
        result = DatasetLoader().load("ds1", tmp_path)
        assert isinstance(result, OhlcvDataset)
        assert result.dataset_id == "ds1"

    def test_bar_count_matches_csv_rows(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(7), _sample_meta())
        result = DatasetLoader().load("ds1", tmp_path)
        assert result.bar_count == 7

    def test_ticker_comes_from_metadata(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(2), _sample_meta(ticker="GAZP"))
        result = DatasetLoader().load("ds1", tmp_path)
        assert result.ticker == "GAZP"

    def test_timeframe_comes_from_metadata(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(2), _sample_meta(timeframe="4h"))
        result = DatasetLoader().load("ds1", tmp_path)
        assert result.timeframe == "4h"

    def test_candle_has_required_keys(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(1), _sample_meta())
        result = DatasetLoader().load("ds1", tmp_path)
        candle = result.candles[0]
        for key in ("ticker", "ts", "open", "high", "low", "close", "volume"):
            assert key in candle, f"Missing key: {key}"

    def test_ticker_injected_into_each_candle(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(3), _sample_meta(ticker="LKOH"))
        result = DatasetLoader().load("ds1", tmp_path)
        assert all(c["ticker"] == "LKOH" for c in result.candles)

    def test_datetime_column_mapped_to_ts(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(1), _sample_meta())
        result = DatasetLoader().load("ds1", tmp_path)
        assert result.candles[0]["ts"] == "2023-01-09 10:00:00"

    def test_ohlc_are_float(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(1), _sample_meta())
        result = DatasetLoader().load("ds1", tmp_path)
        c = result.candles[0]
        for key in ("open", "high", "low", "close"):
            assert isinstance(c[key], float), f"{key} should be float"

    def test_volume_is_int(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(1), _sample_meta())
        result = DatasetLoader().load("ds1", tmp_path)
        assert isinstance(result.candles[0]["volume"], int)

    def test_candles_is_tuple(self, tmp_path):
        _write_dataset(tmp_path, "ds1", _sample_rows(2), _sample_meta())
        result = DatasetLoader().load("ds1", tmp_path)
        assert isinstance(result.candles, tuple)


class TestDatasetLoaderErrors:
    def test_missing_dataset_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Dataset directory"):
            DatasetLoader().load("nonexistent", tmp_path)

    def test_missing_metadata_raises(self, tmp_path):
        ds_dir = tmp_path / "datasets" / "ds1"
        ds_dir.mkdir(parents=True)
        (ds_dir / "ohlcv.csv").write_text("datetime,open,high,low,close,volume\n")
        with pytest.raises(FileNotFoundError, match="metadata.json"):
            DatasetLoader().load("ds1", tmp_path)

    def test_missing_csv_raises(self, tmp_path):
        ds_dir = tmp_path / "datasets" / "ds1"
        ds_dir.mkdir(parents=True)
        (ds_dir / "metadata.json").write_text('{"ticker":"SBER","timeframe":"1h"}')
        with pytest.raises(FileNotFoundError, match="ohlcv.csv"):
            DatasetLoader().load("ds1", tmp_path)

    def test_missing_column_raises(self, tmp_path):
        ds_dir = tmp_path / "datasets" / "ds1"
        ds_dir.mkdir(parents=True)
        (ds_dir / "metadata.json").write_text('{"ticker":"SBER","timeframe":"1h"}')
        # Missing 'volume' column
        with open(ds_dir / "ohlcv.csv", "w") as f:
            f.write("datetime,open,high,low,close\n")
            f.write("2023-01-09 10:00:00,230,235,228,232\n")
        with pytest.raises(ValueError, match="volume"):
            DatasetLoader().load("ds1", tmp_path)
