from __future__ import annotations

from typing import Any, Callable

from core.walkforward.models import (
    WalkForwardRunResult,
    WalkForwardSummary,
    WalkForwardWindow,
)
from core.walkforward.window_generator import WalkForwardWindowGenerator


class WalkForwardEngine:
    def __init__(self, generator: WalkForwardWindowGenerator) -> None:
        self.generator = generator

    def run(
        self,
        data_length: int,
        runner: Callable[[WalkForwardWindow], Any],
    ) -> WalkForwardSummary:
        windows = self.generator.generate(data_length)
        runs: list[WalkForwardRunResult] = []
        for window in windows:
            result = runner(window)
            runs.append(WalkForwardRunResult(window=window, result=result))
        return WalkForwardSummary(runs=runs)
