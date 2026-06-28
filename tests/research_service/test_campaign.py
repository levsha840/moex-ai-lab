"""Tests for services.research.campaign.CampaignRunner.

Integration tests use synthetic datasets written to tmp_path.
The campaign runner is tested against real Core components
(same pattern as test_runner_e2e.py).
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from services.research.campaign import (
    CampaignResult,
    CampaignRunItem,
    CampaignRunner,
    CampaignRunItem,
    p1_dataset_id,
)
from trading.models import StrategyCandidateStatus


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _write_dataset(data_dir: Path, dataset_id: str, oscillating: bool = True, n: int = 150) -> None:
    ds_dir = data_dir / "datasets" / dataset_id
    ds_dir.mkdir(parents=True)
    ticker = dataset_id.split("_")[0].upper()
    with open(ds_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump({"ticker": ticker, "timeframe": "1h"}, f)
    with open(ds_dir / "ohlcv.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["datetime", "open", "high", "low", "close", "volume"]
        )
        writer.writeheader()
        for i in range(n):
            if oscillating:
                close = 230.0 + 10.0 * math.sin(i * 2 * math.pi / 20.0)
            else:
                close = 200.0 + i * 0.5
            writer.writerow({
                "datetime": f"2023-01-01 {i % 24:02d}:00:00",
                "open": f"{close - 0.3:.2f}",
                "high": f"{close + 1.5:.2f}",
                "low": f"{close - 1.5:.2f}",
                "close": f"{close:.2f}",
                "volume": "500000",
            })


def _make_runner(tmp_path: Path, output_subdir: str = "campaign", verbose: bool = False) -> CampaignRunner:
    return CampaignRunner(
        hypothesis_template_id="tmpl_h_rev_vol_reg",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / output_subdir,
        max_candidates=1,
        train_size=30,
        test_size=10,
        step_size=10,
        verbose=verbose,
    )


# ─── p1_dataset_id ────────────────────────────────────────────────────────────

class TestP1DatasetId:
    def test_standard_format(self):
        assert p1_dataset_id("SBER", "2023") == "sber_1h_2023_main"

    def test_lowercase_ticker(self):
        assert p1_dataset_id("GAZP", "2021") == "gazp_1h_2021_main"

    def test_custom_timeframe(self):
        assert p1_dataset_id("NVTK", "2019", "4h") == "nvtk_4h_2019_main"


# ─── Single-run campaign ──────────────────────────────────────────────────────

class TestCampaignRunnerSingleRun:
    @pytest.fixture
    def result(self, tmp_path) -> CampaignResult:
        _write_dataset(tmp_path / "data", "sber_1h_2023_main", oscillating=True)
        runner = _make_runner(tmp_path)
        return runner.run(["SBER"], ["2023"])

    def test_returns_campaign_result(self, result):
        assert isinstance(result, CampaignResult)

    def test_total_is_1(self, result):
        assert result.total == 1

    def test_items_has_one_entry(self, result):
        assert len(result.items) == 1

    def test_item_has_correct_instrument(self, result):
        assert result.items[0].instrument == "SBER"

    def test_item_has_correct_period(self, result):
        assert result.items[0].period == "2023"

    def test_item_has_pass_rate(self, result):
        # pass_rate may be 0.0 but must be present (no error)
        assert result.items[0].error == ""
        assert result.items[0].pass_rate is not None

    def test_item_has_windows_total(self, result):
        assert result.items[0].windows_total > 0

    def test_item_has_alpha_gate(self, result):
        assert result.items[0].alpha_gate is not None

    def test_campaign_report_written(self, tmp_path, result):
        report_path = tmp_path / "campaign" / "campaign_report.json"
        assert report_path.exists()

    def test_campaign_report_valid_json(self, tmp_path, result):
        report_path = tmp_path / "campaign" / "campaign_report.json"
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "campaign_id" in data
        assert "runs" in data
        assert "candidates" in data
        assert data["hypothesis_template_id"] == "tmpl_h_rev_vol_reg"

    def test_campaign_id_non_empty(self, result):
        assert result.campaign_id != ""

    def test_generated_at_non_empty(self, result):
        assert result.generated_at != ""


# ─── Missing dataset → error item, campaign continues ────────────────────────

class TestCampaignRunnerMissingDataset:
    def test_missing_dataset_produces_error_item(self, tmp_path):
        runner = _make_runner(tmp_path)
        # no datasets written → all will fail with FileNotFoundError
        result = runner.run(["SBER"], ["2023"])
        assert result.items[0].errored is True
        assert result.items[0].error != ""

    def test_campaign_continues_after_error(self, tmp_path):
        data_dir = tmp_path / "data"
        # Only write SBER 2023, not SBER 2021 or 2019
        _write_dataset(data_dir, "sber_1h_2023_main")
        runner = _make_runner(tmp_path)
        result = runner.run(["SBER"], ["2019", "2021", "2023"])
        assert result.total == 3
        # 2023 runs fine, 2019 and 2021 produce errors
        assert result.error_count == 2
        assert result.items[-1].error == ""


# ─── Multi-run campaign ───────────────────────────────────────────────────────

class TestCampaignRunnerMultiRun:
    @pytest.fixture
    def result(self, tmp_path) -> CampaignResult:
        data_dir = tmp_path / "data"
        for ticker in ["SBER", "GAZP"]:
            for period in ["2021", "2023"]:
                _write_dataset(data_dir, p1_dataset_id(ticker, period))
        runner = _make_runner(tmp_path)
        return runner.run(["SBER", "GAZP"], ["2021", "2023"])

    def test_total_is_4(self, result):
        assert result.total == 4

    def test_all_items_present(self, result):
        combos = {(i.instrument, i.period) for i in result.items}
        assert ("SBER", "2021") in combos
        assert ("SBER", "2023") in combos
        assert ("GAZP", "2021") in combos
        assert ("GAZP", "2023") in combos

    def test_error_count_is_0(self, result):
        assert result.error_count == 0

    def test_campaign_report_has_4_runs(self, tmp_path, result):
        report_path = tmp_path / "campaign" / "campaign_report.json"
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["runs"]) == 4


# ─── Alpha gate and StrategyCandidate creation ────────────────────────────────

class TestCampaignCandidateCreation:
    def test_candidate_has_correct_status(self, tmp_path):
        """Any candidate produced must have CANDIDATE_RESEARCH_PASSED status."""
        data_dir = tmp_path / "data"
        _write_dataset(data_dir, "sber_1h_2023_main")
        # Use a very low alpha gate so even marginal pass_rate qualifies
        from services.research.alpha_gate import AlphaLibraryGate
        runner = CampaignRunner(
            hypothesis_template_id="tmpl_h_rev_vol_reg",
            data_dir=data_dir,
            output_dir=tmp_path / "campaign",
            alpha_gate=AlphaLibraryGate(min_pass_rate=0.01, min_windows=1),
            max_candidates=1,
            train_size=30,
            test_size=10,
            step_size=10,
            verbose=False,
        )
        result = runner.run(["SBER"], ["2023"])
        for candidate in result.candidates:
            assert candidate.status == StrategyCandidateStatus.CANDIDATE_RESEARCH_PASSED

    def test_candidate_instrument_matches_run(self, tmp_path):
        from services.research.alpha_gate import AlphaLibraryGate
        data_dir = tmp_path / "data"
        _write_dataset(data_dir, "gazp_1h_2021_main")
        runner = CampaignRunner(
            hypothesis_template_id="tmpl_h_rev_vol_reg",
            data_dir=data_dir,
            output_dir=tmp_path / "campaign",
            alpha_gate=AlphaLibraryGate(min_pass_rate=0.01, min_windows=1),
            max_candidates=1,
            train_size=30,
            test_size=10,
            step_size=10,
            verbose=False,
        )
        result = runner.run(["GAZP"], ["2021"])
        for candidate in result.candidates:
            assert candidate.instrument == "GAZP"
            assert candidate.period == "2021"

    def test_candidate_not_approved_for_paper(self, tmp_path):
        """Research-passed candidates must NOT be APPROVED_FOR_PAPER without risk review."""
        from services.research.alpha_gate import AlphaLibraryGate
        data_dir = tmp_path / "data"
        _write_dataset(data_dir, "sber_1h_2023_main")
        runner = CampaignRunner(
            hypothesis_template_id="tmpl_h_rev_vol_reg",
            data_dir=data_dir,
            output_dir=tmp_path / "campaign",
            alpha_gate=AlphaLibraryGate(min_pass_rate=0.01, min_windows=1),
            max_candidates=1,
            train_size=30,
            test_size=10,
            step_size=10,
            verbose=False,
        )
        result = runner.run(["SBER"], ["2023"])
        for candidate in result.candidates:
            assert candidate.status != StrategyCandidateStatus.APPROVED_FOR_PAPER

    def test_candidate_source_ref_is_dataset_id(self, tmp_path):
        from services.research.alpha_gate import AlphaLibraryGate
        data_dir = tmp_path / "data"
        _write_dataset(data_dir, "sber_1h_2023_main")
        runner = CampaignRunner(
            hypothesis_template_id="tmpl_h_rev_vol_reg",
            data_dir=data_dir,
            output_dir=tmp_path / "campaign",
            alpha_gate=AlphaLibraryGate(min_pass_rate=0.01, min_windows=1),
            max_candidates=1,
            train_size=30,
            test_size=10,
            step_size=10,
            verbose=False,
        )
        result = runner.run(["SBER"], ["2023"])
        for candidate in result.candidates:
            assert candidate.source_ref == "sber_1h_2023_main"

    def test_no_candidate_when_gate_strict(self, tmp_path):
        """With very strict gate (min_pass_rate=1.0), no candidates produced."""
        from services.research.alpha_gate import AlphaLibraryGate
        data_dir = tmp_path / "data"
        _write_dataset(data_dir, "sber_1h_2023_main")
        runner = CampaignRunner(
            hypothesis_template_id="tmpl_h_rev_vol_reg",
            data_dir=data_dir,
            output_dir=tmp_path / "campaign",
            alpha_gate=AlphaLibraryGate(min_pass_rate=1.0, min_windows=1),
            max_candidates=1,
            train_size=30,
            test_size=10,
            step_size=10,
            verbose=False,
        )
        result = runner.run(["SBER"], ["2023"])
        assert len(result.candidates) == 0


# ─── CampaignRunItem ──────────────────────────────────────────────────────────

class TestCampaignRunItem:
    def test_alpha_passed_false_when_no_gate(self):
        item = CampaignRunItem(dataset_id="x", instrument="X", period="2023")
        assert item.alpha_passed is False

    def test_errored_true_when_error_set(self):
        item = CampaignRunItem(dataset_id="x", instrument="X", period="2023", error="oops")
        assert item.errored is True

    def test_errored_false_when_no_error(self):
        item = CampaignRunItem(dataset_id="x", instrument="X", period="2023")
        assert item.errored is False
