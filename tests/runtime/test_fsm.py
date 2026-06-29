"""M12 Sprint 2 — FSM state transition tests (15 tests)."""
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.runtime.runtime_state import (
    OrchestratorState,
    TRANSITIONS,
    StateError,
    validate_transition,
    TERMINAL_STATES,
)


class TestOrchestratorStateEnum:
    def test_all_states_exist(self):
        states = {s.value for s in OrchestratorState}
        assert states == {"IDLE", "PLANNING", "QUEUEING", "VALIDATING", "LEARNING", "SYNCING", "ERROR"}

    def test_state_is_string(self):
        assert OrchestratorState.IDLE == "IDLE"
        assert isinstance(OrchestratorState.ERROR, str)

    def test_transitions_dict_has_all_states(self):
        for state in OrchestratorState:
            assert state.value in TRANSITIONS, f"{state} missing from TRANSITIONS"

    def test_terminal_states(self):
        assert "IDLE" in TERMINAL_STATES
        assert "ERROR" in TERMINAL_STATES
        assert "PLANNING" not in TERMINAL_STATES


class TestValidTransitions:
    def test_idle_to_planning(self):
        validate_transition("IDLE", "PLANNING")  # must not raise

    def test_idle_to_error(self):
        validate_transition("IDLE", "ERROR")

    def test_planning_to_queueing(self):
        validate_transition("PLANNING", "QUEUEING")

    def test_planning_to_idle_empty_queue(self):
        # Valid: scheduler found no pending tasks
        validate_transition("PLANNING", "IDLE")

    def test_planning_to_error(self):
        validate_transition("PLANNING", "ERROR")

    def test_queueing_to_validating(self):
        validate_transition("QUEUEING", "VALIDATING")

    def test_validating_to_learning(self):
        validate_transition("VALIDATING", "LEARNING")

    def test_learning_to_syncing(self):
        validate_transition("LEARNING", "SYNCING")

    def test_syncing_to_idle(self):
        validate_transition("SYNCING", "IDLE")

    def test_error_to_idle_recovery(self):
        validate_transition("ERROR", "IDLE")

    def test_all_states_can_reach_error(self):
        # Every state except ERROR itself can transition to ERROR
        for state_name, successors in TRANSITIONS.items():
            if state_name != "ERROR":
                assert "ERROR" in successors, f"{state_name} cannot reach ERROR"


class TestInvalidTransitions:
    def test_idle_cannot_skip_to_validating(self):
        with pytest.raises(StateError):
            validate_transition("IDLE", "VALIDATING")

    def test_planning_cannot_jump_to_syncing(self):
        with pytest.raises(StateError):
            validate_transition("PLANNING", "SYNCING")

    def test_queueing_cannot_return_to_idle_directly(self):
        with pytest.raises(StateError):
            validate_transition("QUEUEING", "IDLE")

    def test_error_cannot_go_to_planning(self):
        with pytest.raises(StateError):
            validate_transition("ERROR", "PLANNING")

    def test_syncing_cannot_go_to_planning(self):
        with pytest.raises(StateError):
            validate_transition("SYNCING", "PLANNING")

    def test_state_error_message_contains_state_names(self):
        with pytest.raises(StateError) as exc_info:
            validate_transition("IDLE", "SYNCING")
        msg = str(exc_info.value)
        assert "IDLE" in msg
        assert "SYNCING" in msg
