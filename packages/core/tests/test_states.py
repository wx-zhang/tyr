import pytest
from gamr_core.states import RunState, transition


def test_valid_run_transition() -> None:
    assert transition(RunState.QUEUED, RunState.PREPARING) is RunState.PREPARING


def test_invalid_run_transition_is_rejected() -> None:
    with pytest.raises(ValueError):
        transition(RunState.COMPLETED, RunState.RUNNING)
