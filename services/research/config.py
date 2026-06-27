from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ServiceConfig:
    """All parameters for a single Research Service run.

    data_dir:   where to find datasets/<dataset_id>/ohlcv.csv + metadata.json
    output_dir: root for all output artifacts (reports/, sessions/, knowledge/, runs/)
    """

    dataset_id: str
    data_dir: Path = field(default_factory=lambda: Path("data"))
    max_candidates: int = 5
    pass_threshold: float = 0.80
    max_consecutive_failures: int = 3
    output_dir: Path = field(default_factory=lambda: Path("."))
    description: str = ""
    train_size: int = 60
    test_size: int = 20
    step_size: int = 20

    def __post_init__(self) -> None:
        if self.max_candidates <= 0:
            raise ValueError(f"max_candidates must be positive, got {self.max_candidates}")
        if not 0.0 < self.pass_threshold <= 1.0:
            raise ValueError(
                f"pass_threshold must be in (0.0, 1.0], got {self.pass_threshold}"
            )
        if self.max_consecutive_failures <= 0:
            raise ValueError(
                f"max_consecutive_failures must be positive, got {self.max_consecutive_failures}"
            )
        if self.train_size <= 0 or self.test_size <= 0 or self.step_size <= 0:
            raise ValueError("train_size, test_size, step_size must all be positive")

    @property
    def reports_dir(self) -> Path:
        return self.output_dir / "reports"

    @property
    def sessions_dir(self) -> Path:
        return self.output_dir / "sessions"

    @property
    def knowledge_dir(self) -> Path:
        return self.output_dir / "knowledge"

    @property
    def knowledge_db_path(self) -> Path:
        return self.knowledge_dir / "knowledge_base.json"

    @property
    def runs_dir(self) -> Path:
        return self.output_dir / "runs"
