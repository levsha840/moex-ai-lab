from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .models import FailureAction


class ResearchPolicy(Protocol):
    """Controls when the orchestrator continues, pauses, or stops.

    should_continue  — called before each task; return False to abort cleanly.
    on_task_failure  — called after each pipeline exception; return ABORT to
                       stop the session and mark remaining tasks as SKIPPED.
    """

    def should_continue(
        self,
        completed: int,
        failed: int,
        skipped: int,
    ) -> bool: ...

    def on_task_failure(self, consecutive_failures: int) -> "FailureAction": ...
