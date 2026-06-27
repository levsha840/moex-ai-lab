"""End-to-end integration test — ResearchRunner with real Core components.

Uses synthetic OHLCV data (150 bars of monotonically rising prices).
Resolves TD-003: no end-to-end test for ResearchSession with real components.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from services.research.config import ServiceConfig
from services.research.runner import ResearchRunner, RunResult


# ─── Synthetic dataset fixture ────────────────────────────────────────────────

_BAR_COUNT = 150  # enough for train_size=30, test_size=10 → many windows


def _write_synthetic_dataset(data_dir: Path, dataset_id: str) -> None:
    ds_dir = data_dir / "datasets" / dataset_id
    ds_dir.mkdir(parents=True)

    with open(ds_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump({"ticker": "SBER", "timeframe": "1h"}, f)

    base_price = 230.0
    with open(ds_dir / "ohlcv.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["datetime", "open", "high", "low", "close", "volume"]
        )
        writer.writeheader()
        for i in range(_BAR_COUNT):
            close = base_price + i * 0.5
            writer.writerow(
                {
                    "datetime": f"2023-01-09 {(10 + i // 24) % 24:02d}:{(i % 24) * 2:02d}:00",
                    "open": f"{close - 0.3:.2f}",
                    "high": f"{close + 1.0:.2f}",
                    "low": f"{close - 1.0:.2f}",
                    "close": f"{close:.2f}",
                    "volume": "500000",
                }
            )


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestResearchRunnerE2E:
    @pytest.fixture
    def run_result(self, tmp_path) -> RunResult:
        data_dir = tmp_path / "data"
        _write_synthetic_dataset(data_dir, "sber_test")

        config = ServiceConfig(
            dataset_id="sber_test",
            data_dir=data_dir,
            output_dir=tmp_path,
            max_candidates=2,
            pass_threshold=0.80,
            max_consecutive_failures=3,
            train_size=30,
            test_size=10,
            step_size=10,
            description="E2E integration test",
        )
        return ResearchRunner().run(config)

    def test_exit_code_0_when_tasks_complete(self, run_result):
        # At least 1 COMPLETED task (even FAIL outcome) → exit 0
        assert run_result.exit_code == 0

    def test_report_json_created(self, run_result):
        assert run_result.report_path.exists()

    def test_report_json_is_valid(self, run_result):
        with open(run_result.report_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "report_id" in data
        assert "session_id" in data
        assert "findings" in data
        assert "recommendations" in data
        assert "summary" in data

    def test_session_meta_created(self, run_result):
        assert run_result.session_meta_path.exists()

    def test_session_meta_has_session_id(self, run_result):
        with open(run_result.session_meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["session_id"] == run_result.session_id

    def test_summary_txt_created(self, run_result):
        assert run_result.summary_txt_path.exists()

    def test_run_meta_created(self, run_result):
        assert run_result.run_meta_path.exists()

    def test_knowledge_base_json_created(self, run_result):
        assert run_result.kb_path.exists()

    def test_kb_contains_experiment_entries(self, run_result):
        with open(run_result.kb_path, encoding="utf-8") as f:
            data = json.load(f)
        experiment_entries = [
            e for e in data["entries"] if e["knowledge_type"] == "EXPERIMENT"
        ]
        assert len(experiment_entries) >= 1

    def test_report_has_at_least_one_finding(self, run_result):
        with open(run_result.report_path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["findings"]) >= 1

    def test_session_id_consistent_across_artifacts(self, run_result):
        with open(run_result.report_path, encoding="utf-8") as f:
            report = json.load(f)
        with open(run_result.session_meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert report["session_id"] == run_result.session_id
        assert meta["session_id"] == run_result.session_id

    def test_run_meta_has_correct_exit_code(self, run_result):
        with open(run_result.run_meta_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["exit_code"] == run_result.exit_code


class TestResearchRunnerDatasetErrors:
    def test_missing_dataset_raises_file_not_found(self, tmp_path):
        config = ServiceConfig(
            dataset_id="does_not_exist",
            data_dir=tmp_path / "data",
            output_dir=tmp_path,
        )
        with pytest.raises(FileNotFoundError):
            ResearchRunner().run(config)
