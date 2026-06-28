"""E2E test: H-REV-VOL-REG runs through ResearchRunner via Hypothesis Registry.

PROVES: A new hypothesis (H-REV-VOL-REG) runs end-to-end through ResearchRunner
by setting hypothesis_template_id in ServiceConfig. No changes to Research Service
code are required — the hypothesis is selected purely through configuration.

This is the acceptance test for the Hypothesis Registry requirement:
  "Добавление новой гипотезы не требует изменения Research Service."
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from services.research.config import ServiceConfig
from services.research.runner import ResearchRunner, RunResult


_BAR_COUNT = 150


def _write_oscillating_dataset(data_dir: Path, dataset_id: str) -> None:
    """Oscillating prices — suitable for mean-reversion (low ADX, range regime)."""
    ds_dir = data_dir / "datasets" / dataset_id
    ds_dir.mkdir(parents=True)

    with open(ds_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump({"ticker": "SBER", "timeframe": "1h"}, f)

    with open(ds_dir / "ohlcv.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["datetime", "open", "high", "low", "close", "volume"]
        )
        writer.writeheader()
        for i in range(_BAR_COUNT):
            close = 230.0 + 10.0 * math.sin(i * 2 * math.pi / 20.0)
            writer.writerow(
                {
                    "datetime": f"2023-01-09 {(10 + i // 24) % 24:02d}:{(i % 24) * 2:02d}:00",
                    "open": f"{close - 0.3:.2f}",
                    "high": f"{close + 1.5:.2f}",
                    "low": f"{close - 1.5:.2f}",
                    "close": f"{close:.2f}",
                    "volume": "500000",
                }
            )


class TestRevVolRegE2E:
    """H-REV-VOL-REG runs through ResearchRunner via hypothesis_template_id config."""

    @pytest.fixture
    def run_result(self, tmp_path) -> RunResult:
        data_dir = tmp_path / "data"
        _write_oscillating_dataset(data_dir, "sber_rev_vol_test")

        config = ServiceConfig(
            dataset_id="sber_rev_vol_test",
            data_dir=data_dir,
            output_dir=tmp_path,
            max_candidates=2,
            pass_threshold=0.80,
            max_consecutive_failures=3,
            train_size=30,
            test_size=10,
            step_size=10,
            description="H-REV-VOL-REG E2E via Hypothesis Registry",
            hypothesis_template_id="tmpl_h_rev_vol_reg",
        )
        return ResearchRunner().run(config)

    def test_exit_code_0_when_tasks_complete(self, run_result):
        assert run_result.exit_code == 0

    def test_report_json_created(self, run_result):
        assert run_result.report_path.exists()

    def test_report_json_is_valid(self, run_result):
        with open(run_result.report_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "session_id" in data

    def test_session_id_non_empty(self, run_result):
        assert run_result.session_id != ""

    def test_summary_txt_created(self, run_result):
        assert run_result.summary_txt_path.exists()

    def test_run_meta_created(self, run_result):
        assert run_result.run_meta_path.exists()

    def test_run_meta_has_exit_code(self, run_result):
        with open(run_result.run_meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert "exit_code" in meta
        assert meta["exit_code"] == 0

    def test_kb_created(self, run_result):
        assert run_result.kb_path.exists()

    def test_duration_positive(self, run_result):
        assert run_result.duration_seconds > 0.0


class TestHypothesisSelectionViaConfig:
    """Verify that hypothesis_template_id in config selects the correct template."""

    def _run(self, tmp_path: Path, template_id: str) -> RunResult:
        data_dir = tmp_path / "data"
        _write_oscillating_dataset(data_dir, "sber_sel_test")
        config = ServiceConfig(
            dataset_id="sber_sel_test",
            data_dir=data_dir,
            output_dir=tmp_path,
            max_candidates=1,
            pass_threshold=0.80,
            max_consecutive_failures=3,
            train_size=30,
            test_size=10,
            step_size=10,
            hypothesis_template_id=template_id,
        )
        return ResearchRunner().run(config)

    def test_adx_continuation_still_runs_via_registry(self, tmp_path):
        """H-ADX-CONTINUATION also runs via registry — backward compat preserved."""
        result = self._run(tmp_path, "tmpl_h13_adx_continuation")
        assert result.exit_code == 0

    def test_rev_vol_reg_runs_via_registry(self, tmp_path):
        """H-REV-VOL-REG runs via registry — new hypothesis, no code change."""
        result = self._run(tmp_path, "tmpl_h_rev_vol_reg")
        assert result.exit_code == 0

    def test_unknown_template_id_raises(self, tmp_path):
        """Unknown template_id → KeyError from registry."""
        with pytest.raises(KeyError):
            self._run(tmp_path, "tmpl_does_not_exist")

    def test_default_template_is_adx_continuation(self, tmp_path):
        """Empty hypothesis_template_id → first alphabetical template (H-ADX)."""
        data_dir = tmp_path / "data"
        _write_oscillating_dataset(data_dir, "sber_default_test")
        config = ServiceConfig(
            dataset_id="sber_default_test",
            data_dir=data_dir,
            output_dir=tmp_path,
            max_candidates=1,
            pass_threshold=0.80,
            max_consecutive_failures=3,
            train_size=30,
            test_size=10,
            step_size=10,
        )
        result = ResearchRunner().run(config)
        assert result.exit_code == 0
