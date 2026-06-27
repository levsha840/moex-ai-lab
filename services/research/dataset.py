from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

_REQUIRED_COLUMNS = {"datetime", "open", "high", "low", "close", "volume"}


@dataclass(frozen=True)
class OhlcvDataset:
    """Loaded OHLCV dataset ready for injection into feature providers.

    candles: list[dict] with keys {ticker, ts, open, high, low, close, volume}
    Matches the format expected by H13FeatureProvider.
    """

    dataset_id: str
    ticker: str
    timeframe: str
    candles: tuple[dict, ...]

    @property
    def bar_count(self) -> int:
        return len(self.candles)


class DatasetLoader:
    """Loads OHLCV datasets from local filesystem.

    Expected directory structure:
        <data_dir>/datasets/<dataset_id>/ohlcv.csv
        <data_dir>/datasets/<dataset_id>/metadata.json
    """

    def load(self, dataset_id: str, data_dir: Path) -> OhlcvDataset:
        dataset_dir = data_dir / "datasets" / dataset_id

        if not dataset_dir.exists():
            raise FileNotFoundError(
                f"Dataset directory not found: {dataset_dir}"
            )

        meta_path = dataset_dir / "metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"metadata.json not found: {meta_path}")

        csv_path = dataset_dir / "ohlcv.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"ohlcv.csv not found: {csv_path}")

        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)

        ticker: str = meta["ticker"]
        timeframe: str = meta.get("timeframe", "")

        candles: list[dict] = []
        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            headers = set(reader.fieldnames or [])
            missing = _REQUIRED_COLUMNS - headers
            if missing:
                raise ValueError(
                    f"ohlcv.csv missing required columns: {sorted(missing)}"
                )

            for row in reader:
                candles.append(
                    {
                        "ticker": ticker,
                        "ts": row["datetime"],
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": int(float(row["volume"])),
                    }
                )

        return OhlcvDataset(
            dataset_id=dataset_id,
            ticker=ticker,
            timeframe=timeframe,
            candles=tuple(candles),
        )
