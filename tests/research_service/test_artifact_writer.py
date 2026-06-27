import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.research.config import ServiceConfig
from services.research.dataset import OhlcvDataset
from services.research.persistence import ArtifactWriter


# ─── Minimal stub builders ────────────────────────────────────────────────────

def _make_report(**overrides):
    from core.research_session.models import ResearchSessionStatus
    from core.research_session.report_models import (
        ReportSummary,
        ResearchReport,
    )

    summary = ReportSummary(
        session_id="sess_001",
        description="test",
        status=ResearchSessionStatus.COMPLETED,
        total_hypotheses=1,
        pass_count=1,
        fail_count=0,
        inconclusive_count=0,
        error_count=0,
        skipped_count=0,
        validation_pass_rate=1.0,
        avg_pass_rate=0.90,
        median_pass_rate=0.90,
        kb_entries_created=1,
        duration_seconds=2.5,
        pass_threshold=0.80,
    )
    return ResearchReport(
        report_id="report_001",
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        session_id="sess_001",
        summary=summary,
        findings=(),
        recommendations=(),
    )


def _make_result():
    from unittest.mock import MagicMock
    from core.research_session.models import ResearchSessionStatus

    stats = MagicMock()
    stats.duration_seconds = 2.5
    stats.candidates_generated = 1
    stats.hypotheses_accepted = 1
    stats.tasks_completed = 1
    stats.tasks_failed = 0
    stats.tasks_skipped = 0
    stats.validation_pass = 1
    stats.validation_fail = 0
    stats.validation_inconclusive = 0
    stats.avg_pass_rate = 0.9
    stats.kb_entries_created = 1

    config = MagicMock()
    config.pass_threshold = 0.80
    config.experiment_config.dataset_id = "test_ds"

    result = MagicMock()
    result.session_id = "sess_001"
    result.status = ResearchSessionStatus.COMPLETED
    result.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result.finished_at = datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
    result.statistics = stats
    result.config = config
    return result


def _make_dataset() -> OhlcvDataset:
    return OhlcvDataset(
        dataset_id="test_ds",
        ticker="SBER",
        timeframe="1h",
        candles=(),
    )


def _make_config(tmp_path: Path) -> ServiceConfig:
    return ServiceConfig(dataset_id="test_ds", output_dir=tmp_path)


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestArtifactWriterReport:
    def test_write_report_creates_file(self, tmp_path):
        writer = ArtifactWriter()
        report_dir = tmp_path / "report_dir"
        writer.write_report(_make_report(), report_dir)
        assert (report_dir / "report.json").exists()

    def test_write_report_returns_path(self, tmp_path):
        writer = ArtifactWriter()
        path = writer.write_report(_make_report(), tmp_path / "r")
        assert path == tmp_path / "r" / "report.json"

    def test_write_report_json_structure(self, tmp_path):
        writer = ArtifactWriter()
        report_dir = tmp_path / "r"
        writer.write_report(_make_report(), report_dir)
        with open(report_dir / "report.json", encoding="utf-8") as f:
            data = json.load(f)
        for key in ("report_id", "generated_at", "session_id", "summary", "findings", "recommendations"):
            assert key in data

    def test_write_report_creates_parent_dir(self, tmp_path):
        writer = ArtifactWriter()
        deep_dir = tmp_path / "a" / "b" / "c"
        writer.write_report(_make_report(), deep_dir)
        assert (deep_dir / "report.json").exists()


class TestArtifactWriterSessionMeta:
    def test_write_session_meta_creates_file(self, tmp_path):
        writer = ArtifactWriter()
        session_dir = tmp_path / "sessions" / "sess_001"
        writer.write_session_meta(_make_result(), session_dir)
        assert (session_dir / "session_meta.json").exists()

    def test_write_session_meta_has_session_id(self, tmp_path):
        writer = ArtifactWriter()
        session_dir = tmp_path / "s"
        writer.write_session_meta(_make_result(), session_dir)
        with open(session_dir / "session_meta.json") as f:
            data = json.load(f)
        assert data["session_id"] == "sess_001"


class TestArtifactWriterSummaryTxt:
    def test_write_summary_txt_creates_file(self, tmp_path):
        writer = ArtifactWriter()
        report_dir = tmp_path / "r"
        writer.write_summary_txt(_make_report(), _make_dataset(), report_dir)
        assert (report_dir / "summary.txt").exists()

    def test_summary_txt_contains_session_id(self, tmp_path):
        writer = ArtifactWriter()
        report_dir = tmp_path / "r"
        writer.write_summary_txt(_make_report(), _make_dataset(), report_dir)
        text = (report_dir / "summary.txt").read_text(encoding="utf-8")
        assert "sess_001" in text


class TestArtifactWriterRunMeta:
    def test_write_run_meta_creates_file(self, tmp_path):
        config = _make_config(tmp_path)
        writer = ArtifactWriter()
        t = datetime(2026, 1, 1, tzinfo=timezone.utc)
        path = writer.write_run_meta(config, "sess_001", 0, t, t, tmp_path / "runs")
        assert path.exists()

    def test_write_run_meta_structure(self, tmp_path):
        config = _make_config(tmp_path)
        writer = ArtifactWriter()
        t = datetime(2026, 1, 1, tzinfo=timezone.utc)
        path = writer.write_run_meta(config, "sess_001", 0, t, t, tmp_path / "runs")
        with open(path) as f:
            data = json.load(f)
        assert data["session_id"] == "sess_001"
        assert data["exit_code"] == 0
        assert "config" in data
        assert data["config"]["dataset_id"] == "test_ds"

    def test_run_meta_in_date_subdir(self, tmp_path):
        config = _make_config(tmp_path)
        writer = ArtifactWriter()
        t = datetime(2026, 1, 15, tzinfo=timezone.utc)
        path = writer.write_run_meta(config, "sess_abc", 0, t, t, tmp_path / "runs")
        assert "2026-01-15" in str(path)
        assert "sess_abc" in str(path)
