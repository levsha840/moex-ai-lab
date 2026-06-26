from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WalkForwardConfig:
    train_size: int
    test_size: int
    step_size: int
    min_train_size: int | None = None

    def __post_init__(self) -> None:
        if self.train_size <= 0:
            raise ValueError(f"train_size must be > 0, got {self.train_size}")
        if self.test_size <= 0:
            raise ValueError(f"test_size must be > 0, got {self.test_size}")
        if self.step_size <= 0:
            raise ValueError(f"step_size must be > 0, got {self.step_size}")
        if self.min_train_size is not None:
            if not (0 < self.min_train_size <= self.train_size):
                raise ValueError(
                    f"min_train_size must satisfy 0 < min_train_size <= train_size, "
                    f"got {self.min_train_size} (train_size={self.train_size})"
                )


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
