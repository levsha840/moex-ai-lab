from __future__ import annotations

from core.walkforward.models import WalkForwardConfig, WalkForwardWindow


class WalkForwardWindowGenerator:
    def __init__(self, config: WalkForwardConfig) -> None:
        self.config = config

    def generate(self, data_length: int) -> list[WalkForwardWindow]:
        if data_length < 0:
            raise ValueError(f"data_length must be >= 0, got {data_length}")

        windows: list[WalkForwardWindow] = []
        start = 0
        index = 0

        while True:
            train_start = start
            train_end = start + self.config.train_size
            test_start = train_end
            test_end = test_start + self.config.test_size

            if test_end > data_length:
                break

            windows.append(
                WalkForwardWindow(
                    index=index,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )
            start += self.config.step_size
            index += 1

        return windows
