"""M12 Sprint 2 — Orchestrator FSM state definitions.

OrchestratorState is the canonical FSM for the autonomous runtime loop.
All transitions are declared explicitly; invalid transitions raise StateError.
"""
from __future__ import annotations

from enum import Enum


class OrchestratorState(str, Enum):
    IDLE       = "IDLE"
    PLANNING   = "PLANNING"
    QUEUEING   = "QUEUEING"
    VALIDATING = "VALIDATING"
    LEARNING   = "LEARNING"
    SYNCING    = "SYNCING"
    ERROR      = "ERROR"


# Each state maps to its allowed successor states.
TRANSITIONS: dict[str, list[str]] = {
    "IDLE":       ["PLANNING", "ERROR"],
    "PLANNING":   ["QUEUEING", "IDLE", "ERROR"],  # IDLE path = queue was empty
    "QUEUEING":   ["VALIDATING", "ERROR"],
    "VALIDATING": ["LEARNING", "ERROR"],
    "LEARNING":   ["SYNCING", "ERROR"],
    "SYNCING":    ["IDLE", "ERROR"],
    "ERROR":      ["IDLE"],                        # recovery
}

# States from which the orchestrator can safely stop without leaving work in flight
TERMINAL_STATES = {"IDLE", "ERROR"}


class StateError(Exception):
    """Raised when a state transition is not allowed."""


def validate_transition(from_state: str, to_state: str) -> None:
    """Raise StateError if the transition is not in TRANSITIONS."""
    allowed = TRANSITIONS.get(from_state, [])
    if to_state not in allowed:
        raise StateError(
            f"Invalid FSM transition: {from_state} → {to_state}. "
            f"Allowed from {from_state}: {allowed}"
        )
