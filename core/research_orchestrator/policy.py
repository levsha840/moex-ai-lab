from __future__ import annotations

from .models import FailureAction


class DefaultResearchPolicy:
    """Continue execution; abort only after N consecutive pipeline failures.

    A 'pipeline failure' is an exception raised by ResearchPipeline.run() —
    not a validation FAIL (which is a normal experiment outcome, not an error).
    """

    def __init__(self, max_consecutive_failures: int = 3) -> None:
        if max_consecutive_failures < 1:
            raise ValueError(
                f"max_consecutive_failures must be >= 1, got {max_consecutive_failures}"
            )
        self._max = max_consecutive_failures

    def should_continue(self, completed: int, failed: int, skipped: int) -> bool:
        return True

    def on_task_failure(self, consecutive_failures: int) -> FailureAction:
        if consecutive_failures >= self._max:
            return FailureAction.ABORT
        return FailureAction.CONTINUE
