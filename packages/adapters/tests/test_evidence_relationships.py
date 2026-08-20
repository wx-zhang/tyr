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
    assert (
        next(
            relationship
            for relationship in normalized.relationships
            if relationship.source_participant_id.startswith("unknown:")
        ).target_participant_id
        == "agent-a"
    )


def test_operation_normalization_maps_tyr_agent_bridge_tool_and_approval_endpoints() -> None:
    from gamr_adapters.tyr.operations import normalize_operation_result

    result = normalize_operation_result(
        {
            "operationId": "operation-1",
            "updatedAt": "2026-08-08T10:00:00Z",
            "executions": [
                {
                    "executionId": "execution-1",
                    "agentId": "agent-1",
                    "agentName": "Worker",
                    "state": "running",
                }
            ],
            "bridges": [
                {
                    "bridgeRequestId": "xmsg-1",
                    "bridgeId": "bridge-1",
                    "peerWorkspaceName": "Joe workspace",
                    "state": "pending",
                }
            ],
            "toolCalls": [{"id": "tool-1", "toolName": "read", "state": "requested"}],
            "pendingApprovals": [{"id": "approval-1", "actorId": "human-1", "state": "pending"}],
        },
        run_id="run-relations",
        starting_sequence=1,
    )

    assert [item.sequence for item in result] == [1, 2, 3, 4]
    by_type = {item.activity_type.value: item for item in result}
    assert set(by_type) == {"execution", "bridge", "tool_call", "approval"}
    assert all(item.run_id == "run-relations" for item in result)
    assert all(item.source_participant_id == "tyr" for item in result)
    assert by_type["execution"].target_participant_id == "agent:agent-1"
    assert by_type["execution"].metadata["_targetParticipantLabel"] == "Worker"
    assert by_type["execution"].metadata["_targetParticipantKind"] == "delegated_agent"
    assert by_type["bridge"].target_participant_id == "bridge:bridge-1"
    assert by_type["bridge"].metadata["_targetParticipantLabel"] == "Joe workspace"
    assert by_type["tool_call"].target_participant_id == "tool:tool-1"
    assert by_type["approval"].target_participant_id == "human:human-1"


def test_operation_normalization_does_not_invent_endpoints_from_labels_alone() -> None:
    from gamr_adapters.tyr.operations import normalize_operation_result

    result = normalize_operation_result(
        {
            "operationId": "operation-2",
            "updatedAt": "2026-08-08T10:00:00Z",
            "executions": [{"state": "running", "agentName": "Nameless"}],
            "bridges": [{"state": "pending"}],
        },
        run_id="run-relations",
        starting_sequence=1,
    )
    assert len(result) == 2
    assert all(item.source_participant_id is None for item in result)
    assert all(item.target_participant_id is None for item in result)


def test_raw_network_projection_dedupes_child_objects_across_poll_snapshots(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "network-run"
    (bundle / "raw").mkdir(parents=True)
    (bundle / "activity.jsonl").write_text(
        json.dumps(
            {
                "id": "activity-1",
                "runId": "network-run",
                "sequence": 1,
                "occurredAt": "2026-08-08T10:00:00Z",
                "activityType": "run_state",
                "status": "running",
                "evidenceType": "event",
                "summary": "Run state is running",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    snapshots = [
        {
            "targetResponse": {
                "operationId": "op-1",
                "state": "completed",
                "updatedAt": "2026-08-08T10:01:00Z",
                "bridges": [
                    {
                        "bridgeRequestId": "xmsg-1",
                        "bridgeId": "bridge-1",
                        "peerWorkspaceName": "Joe workspace",
                        "state": "completed",
                    }
                ],
                "executions": [],
            }
        },
        {
            "targetResponse": {
                "operationId": "op-1",
                "state": "completed",
                "updatedAt": "2026-08-08T10:02:00Z",
                "bridges": [
                    {
                        "bridgeRequestId": "xmsg-1",
                        "bridgeId": "bridge-1",
                        "peerWorkspaceName": "Joe workspace",
                        "state": "completed",
                    },
                    {
                        "bridgeRequestId": "xmsg-2",
                        "bridgeId": "bridge-1",
                        "peerWorkspaceName": "Joe workspace",
                        "state": "completed",
                    },
                ],
                "executions": [
                    {
                        "executionId": "exec-1",
                        "agentId": "agent-1",
                        "agentName": "Alice",
                        "status": "failed",
                    }
                ],
            }
        },
        {
            "targetResponse": {
                "operationId": "op-1",
                "state": "completed",
                "updatedAt": "2026-08-08T10:03:00Z",
                "bridges": [
                    {
                        "bridgeRequestId": "xmsg-1",
                        "bridgeId": "bridge-1",
                        "peerWorkspaceName": "Joe workspace",
                        "state": "completed",
                    },
                    {
                        "bridgeRequestId": "xmsg-2",
                        "bridgeId": "bridge-1",
                        "peerWorkspaceName": "Joe workspace",
                        "state": "completed",
                    },
                ],
                "executions": [
                    {
                        "executionId": "exec-1",
                        "agentId": "agent-1",
                        "agentName": "Alice",
                        "status": "completed",
                    }
                ],
            }
        },
    ]
    for index, snapshot in enumerate(snapshots, 1):
        (bundle / "raw" / f"{index:02d}.json").write_text(json.dumps(snapshot), encoding="utf-8")

    activities = BundleNormalizer().normalize(bundle, run_id="network-run")
    projected = [item for item in activities if item.activity_type.value in {"bridge", "execution"}]
    assert len(projected) == 3
    bridges = [item for item in projected if item.activity_type.value == "bridge"]
    executions = [item for item in projected if item.activity_type.value == "execution"]
    assert len(bridges) == 2
    assert len(executions) == 1
    assert executions[0].target_participant_id == "agent:agent-1"
    assert executions[0].status == "completed"
    assert all(item.source_participant_id == "tyr" for item in projected)
    assert all(item.target_participant_id == "bridge:bridge-1" for item in bridges)

    relationships = BundleNormalizer().normalize_with_relationships(bundle, run_id="network-run")
    pairs = {
        (item.source_participant_id, item.target_participant_id, item.activity_count)
        for item in relationships.relationships
    }
    assert ("tyr", "bridge:bridge-1", 2) in pairs
    assert ("tyr", "agent:agent-1", 1) in pairs


def test_raw_network_projection_ignores_free_text_topology_mentions(tmp_path: Path) -> None:
    bundle = tmp_path / "text-only"
    (bundle / "raw").mkdir(parents=True)
    (bundle / "raw" / "note.json").write_text(
        json.dumps(
            {
                "targetResponse": {
                    "operationId": "op-text",
                    "state": "completed",
                    "message": "Active bridges: Joe workspace and mike server",
                    "executions": [],
                    "bridges": [],
                }
            }
        ),
        encoding="utf-8",
    )
    (bundle / "activity.jsonl").write_text(
        json.dumps(
            {
                "id": "activity-1",
                "runId": "text-only",
                "sequence": 1,
                "occurredAt": "2026-08-08T10:00:00Z",
                "activityType": "tyr_operation",
                "status": "target_completed",
                "evidenceType": "event",
                "summary": "mike server is active",
                "metadata": {"eventType": "target.completed"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    relationships = BundleNormalizer().normalize_with_relationships(bundle, run_id="text-only")
    assert not any(
        "mike" in participant.display_label.casefold() for participant in relationships.participants
    )
    assert not any(item.activity_type.value == "bridge" for item in relationships.activities)
