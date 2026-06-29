"""Synchronous event bus for the autonomous lab pipeline.

Design choices:
- Synchronous (not async): research pipeline runs in subprocess, no concurrent I/O needed
- Handler errors are caught and logged, not propagated — one failed handler doesn't stop the chain
- Handlers can emit new events: chain is built by handlers calling bus.emit()
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable

from .events import LabEvent

log = logging.getLogger(__name__)

HandlerFn = Callable[[LabEvent, "EventBus"], None]


class EventBus:
    def __init__(self, verbose: bool = False) -> None:
        self._handlers: dict[str, list[HandlerFn]] = defaultdict(list)
        self._history: list[LabEvent] = []
        self._verbose = verbose

    def subscribe(self, event_type: str, handler: HandlerFn) -> None:
        self._handlers[event_type].append(handler)

    def emit(self, event: LabEvent) -> None:
        self._history.append(event)
        if self._verbose:
            log.info("[BUS] emit %s", event)

        for handler in self._handlers.get(event.event_type, []):
            try:
                handler(event, self)
            except Exception as exc:
                log.error(
                    "[BUS] handler %s failed for %s: %s",
                    handler.__name__,
                    event.event_type,
                    exc,
                    exc_info=True,
                )

    @property
    def history(self) -> list[LabEvent]:
        return list(self._history)

    def events_of(self, event_type: str) -> list[LabEvent]:
        return [e for e in self._history if e.event_type == event_type]
