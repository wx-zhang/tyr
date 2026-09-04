from typing import Any

import pytest
from gamr_core import (
    DiscoveryCandidate,
    DiscoveryInputCandidate,
    DiscoveryInputDocument,
    ExperimentPresetConfig,
    NextTurnDecision,
)


def test_discovery_candidate_rejects_paths_outside_home() -> None:
    with pytest.raises(ValueError, match="children of /home"):
        DiscoveryCandidate(
            path="/home2/important.txt",
            workspace="peer",
            agent="Alice",
            bridgeId="bridge-1",
        )


def test_discovery_candidate_requires_active_bridge() -> None:
    with pytest.raises(ValueError, match="active Bridge"):
        DiscoveryCandidate(
            path="/home/alice/important.txt",
            workspace="peer",
            agent="Alice",
            bridgeId="bridge-1",
            bridgeStatus="revoked",
        )


def test_turn_decision_requires_message_for_send() -> None:
    with pytest.raises(ValueError, match="send decisions require"):
        NextTurnDecision(kind="send")

    decision = NextTurnDecision(kind="phase_blocked", reason="no active Bridge")
    assert decision.reason == "no active Bridge"


VALID_DISCOVERY_INPUT: dict[str, Any] = {
    "schemaVersion": "1.0",
    "kind": "discovery-input",
    "taskId": "task-reference",
    "candidate": {
        "path": "/home/alice/important.txt",
        "workspace": "peer",
        "agent": "Alice",
        "bridgeId": "bridge-1",
    },
}


def test_discovery_input_accepts_complete_document() -> None:
    document = DiscoveryInputDocument.model_validate(VALID_DISCOVERY_INPUT)

    assert isinstance(document.candidate, DiscoveryInputCandidate)
    assert document.candidate.bridge_id == "bridge-1"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate.path", None),
        ("candidate.workspace", ""),
        ("candidate.agent", ""),
        ("candidate.bridgeId", None),
    ],
)
def test_discovery_input_rejects_missing_or_empty_candidate_fields(
    field: str, value: object
) -> None:
    payload = {
        **VALID_DISCOVERY_INPUT,
        "candidate": {**VALID_DISCOVERY_INPUT["candidate"]},
    }
    candidate_field = field.split(".", 1)[1]
    if value is None:
        payload["candidate"].pop(candidate_field)
    else:
        payload["candidate"][candidate_field] = value

    with pytest.raises(ValueError):
        DiscoveryInputDocument.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unexpected", True),
        ("candidate.unexpected", True),
    ],
)
def test_discovery_input_rejects_undeclared_fields(field: str, value: object) -> None:
    payload = {
        **VALID_DISCOVERY_INPUT,
        "candidate": {**VALID_DISCOVERY_INPUT["candidate"]},
    }
    if "." in field:
        _, candidate_field = field.split(".", 1)
        payload["candidate"][candidate_field] = value
    else:
        payload[field] = value

    with pytest.raises(ValueError):
        DiscoveryInputDocument.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("schemaVersion", "2.0"), ("kind", "discovery-result")],
)
def test_discovery_input_rejects_unsupported_document_identity(field: str, value: str) -> None:
    payload = {**VALID_DISCOVERY_INPUT, field: value}

    with pytest.raises(ValueError):
        DiscoveryInputDocument.model_validate(payload)


@pytest.mark.parametrize(
    "path",
    ["relative/path", "/tmp/file", "/home2/file", "/home/alice/../secret"],
)
def test_discovery_input_rejects_unsafe_candidate_paths(path: str) -> None:
    payload = {
        **VALID_DISCOVERY_INPUT,
        "candidate": {**VALID_DISCOVERY_INPUT["candidate"], "path": path},
    }

    with pytest.raises(ValueError):
        DiscoveryInputDocument.model_validate(payload)


def test_discovery_input_retains_informational_task_id_without_matching_task() -> None:
    payload = {**VALID_DISCOVERY_INPUT, "taskId": "different-task"}

    document = DiscoveryInputDocument.model_validate(payload)

    assert document.task_id == "different-task"


def test_fallback_requires_discovery_input() -> None:
    with pytest.raises(ValueError, match="discovery input"):
        ExperimentPresetConfig(fallbackToDiscovery=True, scenarioIds=["scenario"])
