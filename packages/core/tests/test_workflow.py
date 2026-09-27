from typing import Any

import pytest
from gamr_core import (
    DiscoveryCandidate,
    DiscoveryInputCandidate,
    DiscoveryInputDocument,
    ExperimentPresetConfig,
    NextTurnDecision,
)


@pytest.mark.parametrize("candidate_type", [DiscoveryCandidate, DiscoveryInputCandidate])
@pytest.mark.parametrize("path", ["/srv/data", "/tmp/work", "relative/path", "Dorian -> Mira"])
def test_discovery_path_is_task_data(
    candidate_type: type[DiscoveryCandidate] | type[DiscoveryInputCandidate], path: str
) -> None:
    candidate = candidate_type(path=path, workspace="peer", agent="Alice", bridgeId="bridge-1")

    assert candidate.path == path


@pytest.mark.parametrize("candidate_type", [DiscoveryCandidate, DiscoveryInputCandidate])
def test_discovery_accepts_workspace_and_bridge_without_path_or_agent(
    candidate_type: type[DiscoveryCandidate] | type[DiscoveryInputCandidate],
) -> None:
    candidate = candidate_type.model_validate({"workspace": "Dorian", "bridgeId": "bridge-1"})

    assert candidate.path is None
    assert candidate.agent is None


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
        ("candidate.path", ""),
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


def test_discovery_input_retains_informational_task_id_without_matching_task() -> None:
    payload = {**VALID_DISCOVERY_INPUT, "taskId": "different-task"}

    document = DiscoveryInputDocument.model_validate(payload)

    assert document.task_id == "different-task"


def test_fallback_requires_discovery_input() -> None:
    with pytest.raises(ValueError, match="discovery input"):
        ExperimentPresetConfig(fallbackToDiscovery=True, scenarioIds=["scenario"])
