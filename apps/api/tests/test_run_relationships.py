import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from gamr_adapters.artifacts.query import ActivityMemoryRepository
from gamr_adapters.config import Settings
from gamr_api.dependencies import get_registry, get_settings
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, RunRecord
from gamr_core import ActivityType, EvidenceQuery, EvidenceType, RunActivity, RunState


def _activity(
    sequence: int,
    *,
    source: str | None = "agent",
    target: str | None = "tyr",
    activity_type: ActivityType = ActivityType.COMMUNICATION,
    status: str = "observed",
    summary: str = "safe relationship evidence",
) -> RunActivity:
    return RunActivity(
        id=f"relationship-activity-{sequence}",
        runId="run-relationships",
        sequence=sequence,
        occurredAt=datetime(2026, 8, 8, 10, 0, sequence, tzinfo=UTC),
        activityType=activity_type,
        status=status,
        caseId="case-a",
        sourceParticipantId=source,
        targetParticipantId=target,
        evidenceType=EvidenceType.EVENT,
        summary=summary,
    )


def test_memory_relationships_filter_and_page_contributing_activity() -> None:
    repository = ActivityMemoryRepository(
        [
            _activity(1),
            _activity(2, status="pending", activity_type=ActivityType.DELEGATION),
            _activity(3, target="tool", activity_type=ActivityType.TOOL_CALL, summary="needle"),
        ]
    )
    projection = repository.aggregate_relationships(
        EvidenceQuery(runId="run-relationships", q="needle")
    )

    relationship = projection.relationships[0]
    assert relationship.activity_count == 1
    assert relationship.id.count(".") == 1
    selected = repository.query(
        EvidenceQuery(runId="run-relationships", relationshipId=relationship.id, limit=10)
    )
    assert [item.sequence for item in selected.items] == [3]


def test_relationship_routes_derive_projection_from_json_bundle(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-relationships"
    bundle.mkdir(parents=True)
    activities = [_activity(1), _activity(2), _activity(3, target="tool")]
    (bundle / "activity.jsonl").write_text(
        "".join(
            json.dumps(item.model_dump(by_alias=True, mode="json")) + "\n"
            for item in activities
        ),
        encoding="utf-8",
    )
    registry = InMemoryRegistry(
        runs={
            "run-relationships": RunRecord(
                "run-relationships", "experiment", "dataset", state=RunState.RUNNING
            )
        }
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(artifact_root))
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/runs/run-relationships/relationships",
            params={"participantId": "agent", "activityType": "communication"},
        )
        assert response.status_code == 200
        relationship_id = next(
            item["id"]
            for item in response.json()["relationships"]
            if item["targetParticipantId"] == "tyr"
        )
        selected = client.get(
            "/api/v1/runs/run-relationships/activity",
            params={"relationshipId": relationship_id, "limit": 1},
        )
        assert selected.status_code == 200
        assert [item["sequence"] for item in selected.json()["items"]] == [1]
        assert client.get("/api/v1/runs/not-authorized/relationships").status_code == 404
    finally:
        app.dependency_overrides.clear()
