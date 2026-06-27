from pathlib import Path

import pytest

from services.research.config import ServiceConfig


def _cfg(**kwargs) -> ServiceConfig:
    return ServiceConfig(dataset_id="test_ds", **kwargs)


class TestServiceConfigDefaults:
    def test_defaults(self):
        cfg = _cfg()
        assert cfg.max_candidates == 5
        assert cfg.pass_threshold == 0.80
        assert cfg.max_consecutive_failures == 3
        assert cfg.output_dir == Path(".")
        assert cfg.data_dir == Path("data")
        assert cfg.description == ""
        assert cfg.train_size == 60
        assert cfg.test_size == 20
        assert cfg.step_size == 20

    def test_dataset_id_stored(self):
        cfg = ServiceConfig(dataset_id="sber_1h_2023")
        assert cfg.dataset_id == "sber_1h_2023"


class TestServiceConfigValidation:
    def test_invalid_max_candidates(self):
        with pytest.raises(ValueError, match="max_candidates"):
            _cfg(max_candidates=0)

    def test_negative_max_candidates(self):
        with pytest.raises(ValueError, match="max_candidates"):
            _cfg(max_candidates=-1)

    def test_pass_threshold_zero_raises(self):
        with pytest.raises(ValueError, match="pass_threshold"):
            _cfg(pass_threshold=0.0)

    def test_pass_threshold_above_one_raises(self):
        with pytest.raises(ValueError, match="pass_threshold"):
            _cfg(pass_threshold=1.01)

    def test_pass_threshold_one_ok(self):
        cfg = _cfg(pass_threshold=1.0)
        assert cfg.pass_threshold == 1.0

    def test_invalid_max_consecutive_failures(self):
        with pytest.raises(ValueError, match="max_consecutive_failures"):
            _cfg(max_consecutive_failures=0)

    def test_invalid_train_size(self):
        with pytest.raises(ValueError, match="train_size"):
            _cfg(train_size=0)

    def test_invalid_test_size(self):
        with pytest.raises(ValueError, match="test_size"):
            _cfg(test_size=0)

    def test_invalid_step_size(self):
        with pytest.raises(ValueError, match="step_size"):
            _cfg(step_size=0)


class TestServiceConfigProperties:
    def test_reports_dir(self):
        cfg = _cfg(output_dir=Path("/out"))
        assert cfg.reports_dir == Path("/out/reports")

    def test_sessions_dir(self):
        cfg = _cfg(output_dir=Path("/out"))
        assert cfg.sessions_dir == Path("/out/sessions")

    def test_knowledge_dir(self):
        cfg = _cfg(output_dir=Path("/out"))
        assert cfg.knowledge_dir == Path("/out/knowledge")

    def test_knowledge_db_path(self):
        cfg = _cfg(output_dir=Path("/out"))
        assert cfg.knowledge_db_path == Path("/out/knowledge/knowledge_base.json")

    def test_runs_dir(self):
        cfg = _cfg(output_dir=Path("/out"))
        assert cfg.runs_dir == Path("/out/runs")

    def test_custom_output_dir(self):
        cfg = _cfg(output_dir=Path("/custom"))
        assert cfg.reports_dir == Path("/custom/reports")
