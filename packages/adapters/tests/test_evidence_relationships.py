import json
from pathlib import Path

from gamr_adapters.artifacts.evidence import BundleNormalizer


def test_normalizer_preserves_explicit_identity_direction_and_relationship_kinds(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "relationships"
    bundle.mkdir()
    records = [
        {
            "id": "activity-communication",
            "runId": "run-relations",
            "sequence": 1,
            "occurredAt": "2026-08-08T10:00:01Z",
            "activityType": "communication",
            "status": "sent",
            "evidenceType": "transcript",
            "summary": "Agent sent a redacted request",
            "sourceParticipantId": "agent-a",
            "targetParticipantId": "gamr",
            "sourceParticipant": {"kind": "model_agent", "label": "Agent"},
            "targetParticipant": {"kind": "gamr", "label": "Agent"},
        },
        {
            "id": "activity-operation",
            "runId": "run-relations",
            "sequence": 2,
            "occurredAt": "2026-08-08T10:00:02Z",
            "activityType": "tyr_operation",
            "status": "started",
            "evidenceType": "event",
            "summary": "Tyr operation observed",
            "operationId": "operation-1",
            "sourceParticipantId": "gamr",
            "targetParticipantId": "tyr",
            "sourceParticipant": {"kind": "gamr", "label": "GAMR"},
            "targetParticipant": {"kind": "tyr_agent", "label": "Tyr"},
        },
        {
            "id": "activity-execution",
            "runId": "run-relations",
            "sequence": 3,
            "occurredAt": "2026-08-08T10:00:03Z",
            "activityType": "execution",
            "status": "running",
            "evidenceType": "event",
            "summary": "Execution observed",
            "sourceParticipantId": "tyr",
            "targetParticipantId": "delegated-1",
            "sourceParticipant": {"kind": "tyr_agent", "label": "Tyr"},
            "targetParticipant": {"kind": "delegated_agent", "label": "Worker"},
        },
        {
            "id": "activity-delegation",
            "runId": "run-relations",
            "sequence": 4,
            "occurredAt": "2026-08-08T10:00:04Z",
            "activityType": "delegation",
            "status": "pending",
            "evidenceType": "event",
            "summary": "Delegation observed",
            "sourceParticipantId": "tyr",
            "targetParticipantId": "delegated-1",
            "sourceParticipant": {"kind": "tyr_agent", "label": "Tyr"},
            "targetParticipant": {"kind": "delegated_agent", "label": "Worker"},
        },
        {
            "id": "activity-bridge",
            "runId": "run-relations",
            "sequence": 5,
            "occurredAt": "2026-08-08T10:00:05Z",
            "activityType": "bridge",
            "status": "pending",
            "evidenceType": "event",
            "summary": "Bridge observed",
            "sourceParticipantId": "tyr",
            "targetParticipantId": "bridge-1",
            "sourceParticipant": {"kind": "tyr_agent", "label": "Tyr"},
            "targetParticipant": {"kind": "bridge", "label": "Bridge"},
        },
        {
            "id": "activity-tool",
            "runId": "run-relations",
            "sequence": 6,
            "occurredAt": "2026-08-08T10:00:06Z",
            "activityType": "tool_call",
            "status": "waiting_for_approval",
            "evidenceType": "event",
            "summary": "Tool request observed",
            "sourceParticipantId": "tyr",
            "targetParticipantId": "tool-1",
            "sourceParticipant": {"kind": "tyr_agent", "label": "Tyr"},
            "targetParticipant": {"kind": "tool", "label": "Tool"},
        },
        {
            "id": "activity-approval",
            "runId": "run-relations",
            "sequence": 7,
            "occurredAt": "2026-08-08T10:00:07Z",
            "activityType": "approval",
            "status": "approved",
            "evidenceType": "approval",
            "summary": "Human approval observed",
            "approvalId": "approval-1",
            "sourceParticipantId": "human-1",
            "targetParticipantId": "tool-1",
            "sourceParticipant": {"kind": "human", "label": "Reviewer"},
            "targetParticipant": {"kind": "tool", "label": "Tool"},
        },
        {
            "id": "activity-unknown",
            "runId": "run-relations",
            "sequence": 8,
            "occurredAt": "2026-08-08T10:00:08Z",
            "activityType": "communication",
            "status": "received",
            "evidenceType": "transcript",
            "summary": "Message from an unknown actor",
            "targetParticipantId": "agent-a",
            "targetParticipant": {"kind": "model_agent", "label": "Agent"},
        },
        {
            "id": "activity-no-topology",
            "runId": "run-relations",
            "sequence": 9,
            "occurredAt": "2026-08-08T10:00:09Z",
            "activityType": "tyr_operation",
            "status": "observed",
            "evidenceType": "event",
            "summary": "An operation without observed endpoints",
            "operationId": "operation-unrelated",
        },
    ]
    (bundle / "events.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    normalized = BundleNormalizer().normalize_with_relationships(bundle, run_id="run-relations")

    assert normalized.activities[0].source_participant_id == "agent-a"
    assert normalized.activities[0].target_participant_id == "gamr"
    participants = {participant.id: participant for participant in normalized.participants}
    assert participants["agent-a"].display_label == "Agent"
    assert participants["gamr"].kind.value == "gamr"
    assert participants["agent-a"].id != participants["gamr"].id
    assert sum(participant.display_label == "Agent" for participant in normalized.participants) == 2
    assert any(participant.kind.value == "unknown" for participant in normalized.participants)

    relationship_types = {
        relationship_type
        for relationship in normalized.relationships
        for relationship_type in relationship.relationship_types
    }
    assert relationship_types >= {
        "communication",
        "operation",
        "execution",
        "delegation",
        "bridge",
        "tool",
        "approval",
    }
    assert not any(
        relationship.source_participant_id == "operation-unrelated"
        for relationship in normalized.relationships
    )
    assert next(
        relationship
        for relationship in normalized.relationships
        if relationship.source_participant_id.startswith("unknown:")
    ).target_participant_id == "agent-a"


def test_operation_normalization_is_deterministic_and_only_uses_observed_endpoints() -> None:
    from gamr_adapters.tyr.operations import normalize_operation_result

    result = normalize_operation_result(
        {
            "operationId": "operation-1",
            "updatedAt": "2026-08-08T10:00:00Z",
            "executions": [
                {
                    "id": "execution-1",
                    "agentId": "agent-1",
                    "agentName": "Worker",
                    "state": "running",
                }
            ],
            "bridges": [{"id": "bridge-1", "bridgeId": "bridge-1", "state": "pending"}],
            "toolCalls": [{"id": "tool-1", "toolName": "read", "state": "requested"}],
            "pendingApprovals": [{"id": "approval-1", "actorId": "human-1", "state": "pending"}],
        },
        run_id="run-relations",
        starting_sequence=1,
    )

    assert [item.sequence for item in result] == [1, 2, 3, 4]
    assert {item.activity_type.value for item in result} == {
        "execution",
        "bridge",
        "tool_call",
        "approval",
    }
    assert all(item.run_id == "run-relations" for item in result)
    assert all(item.source_participant_id is None for item in result)
