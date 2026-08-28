from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from gamr_adapters.config import Settings
from gamr_api.dependencies import get_registry, get_settings
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, RunRecord
from gamr_core import ExperimentConfig, RunState

RUN_ID = "run-history"


@pytest.fixture
def run_evidence_bundle() -> Callable[[str], Path]:
    root = Path(__file__).parents[3] / "tests" / "fixtures" / "run_evidence"

    def resolve(name: str) -> Path:
        return root / name

    return resolve


@pytest.fixture
def historical_client(
    tmp_path: Path, run_evidence_bundle: Callable[[str], Path]
) -> Iterator[TestClient]:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / RUN_ID
    shutil.copytree(run_evidence_bundle("completed"), bundle)
    for path in bundle.rglob("*.json"):
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "0190a000-0000-7000-8000-000000000002", RUN_ID
            ),
            encoding="utf-8",
        )
    for path in bundle.rglob("*.jsonl"):
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "0190a000-0000-7000-8000-000000000002", RUN_ID
            ),
            encoding="utf-8",
        )
    registry = InMemoryRegistry(
        runs={
            RUN_ID: RunRecord(
                id=RUN_ID,
                experiment_id="experiment-history",
                task="fixture-evidence",
                state=RunState.COMPLETED,
                configuration=ExperimentConfig(),
                created_at=datetime(2026, 8, 8, 10, 1, tzinfo=UTC),
            )
        }
    )
    settings = Settings(artifact_root=str(artifact_root))
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _write_activity_bundle(client: TestClient) -> None:
    settings = app.dependency_overrides[get_settings]()
    root = Path(settings.artifact_root) / "runs" / RUN_ID
    records = [
        {
            "id": f"activity-{index}",
            "runId": RUN_ID,
            "sequence": index,
            "occurredAt": f"2026-08-08T10:01:{index:02d}Z",
            "activityType": "communication" if index == 1 else "error",
            "status": "observed" if index == 1 else "failed",
            "caseId": "case-alpha",
            "sourceParticipantId": "agent-1",
            "targetParticipantId": "tyr-1",
            "evidenceType": "transcript" if index == 1 else "error",
            "summary": "literal%_needle" if index == 1 else f"failure {index}",
            "evidenceRefs": ["evidence-1"],
            "detailAvailability": "available",
        }
        for index in range(1, 4)
    ]
    (root / "activity.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )


def test_historical_visualization_uses_canonical_lifecycle_stages(
    historical_client: TestClient,
) -> None:
    payload = historical_client.get(f"/api/v1/runs/{RUN_ID}/visualization").json()

    assert [phase["id"] for phase in payload["phases"]] == [
        "queued",
        "preparing",
        "discovering",
        "running",
        "scientist",
        "evaluating",
        "reporting",
    ]
    phases = {phase["id"]: phase["state"] for phase in payload["phases"]}
    assert phases["scientist"] == "skipped"
    assert {state for phase_id, state in phases.items() if phase_id != "scientist"} == {"completed"}
    assert payload["run"]["currentPhase"] is not None
    assert payload["run"]["currentPhase"] != "unknown"


def test_historical_visualization_exposes_scientist_phase_and_current_phase(
    historical_client: TestClient,
) -> None:
    settings = app.dependency_overrides[get_settings]()
    root = Path(settings.artifact_root) / "runs" / RUN_ID
    records = [
        {
            "id": "activity-1",
            "runId": RUN_ID,
            "sequence": 1,
            "occurredAt": "2026-08-08T10:01:00Z",
            "activityType": "phase",
            "status": "discovery_completed",
            "phase": "discovery",
            "summary": "1 candidate(s)",
            "evidenceType": "event",
            "detailAvailability": "available",
        },
        {
            "id": "activity-2",
            "runId": RUN_ID,
            "sequence": 2,
            "occurredAt": "2026-08-08T10:02:00Z",
            "activityType": "case",
            "status": "case_completed",
            "phase": "case",
            "caseId": "case-alpha",
            "summary": "completed",
            "evidenceType": "event",
            "detailAvailability": "available",
        },
        {
            "id": "activity-3",
            "runId": RUN_ID,
            "sequence": 3,
            "occurredAt": "2026-08-08T10:03:00Z",
            "activityType": "error",
            "status": "scientist_failed",
            "phase": "scientist",
            "summary": "scientist scenario 1 invalid: missing objective",
            "evidenceType": "event",
            "detailAvailability": "available",
            "metadata": {"eventType": "scientist.failed"},
        },
        {
            "id": "activity-4",
            "runId": RUN_ID,
            "sequence": 4,
            "occurredAt": "2026-08-08T10:03:10Z",
            "activityType": "phase",
            "status": "scientist_completed",
            "phase": "scientist",
            "summary": "0 scenario(s)",
            "evidenceType": "event",
            "detailAvailability": "available",
        },
        {
            "id": "activity-5",
            "runId": RUN_ID,
            "sequence": 5,
            "occurredAt": "2026-08-08T10:04:00Z",
            "activityType": "run_state",
            "status": "completed",
            "summary": "Run state is completed",
            "evidenceType": "event",
            "detailAvailability": "available",
        },
    ]
    (root / "activity.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    payload = historical_client.get(f"/api/v1/runs/{RUN_ID}/visualization").json()

    assert payload["run"]["state"] == "completed"
    assert payload["run"]["currentPhase"] == "scientist"
    phases = {phase["id"]: phase["state"] for phase in payload["phases"]}
    assert phases["scientist"] == "completed"
    assert phases["running"] == "completed"
    executions = {
        execution["scenarioExecutionId"]: execution["state"]
        for execution in payload["scenarioExecutions"]
    }
    assert executions["case-alpha"] == "completed"


def test_historical_visualization_marks_scientist_skipped_when_unused(
    historical_client: TestClient,
) -> None:
    settings = app.dependency_overrides[get_settings]()
    root = Path(settings.artifact_root) / "runs" / RUN_ID
    records = [
        {
            "id": "activity-1",
            "runId": RUN_ID,
            "sequence": 1,
            "occurredAt": "2026-08-08T10:01:00Z",
            "activityType": "phase",
            "status": "discovery_completed",
            "phase": "discovery",
            "summary": "1 candidate(s)",
            "evidenceType": "event",
            "detailAvailability": "available",
        },
        {
            "id": "activity-2",
            "runId": RUN_ID,
            "sequence": 2,
            "occurredAt": "2026-08-08T10:02:00Z",
            "activityType": "case",
            "status": "case_completed",
            "phase": "case",
            "caseId": "case-alpha",
            "summary": "completed",
            "evidenceType": "event",
            "detailAvailability": "available",
        },
        {
            "id": "activity-3",
            "runId": RUN_ID,
            "sequence": 3,
            "occurredAt": "2026-08-08T10:04:00Z",
            "activityType": "run_state",
            "status": "completed",
            "summary": "Run state is completed",
            "evidenceType": "event",
            "detailAvailability": "available",
        },
    ]
    (root / "activity.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    payload = historical_client.get(f"/api/v1/runs/{RUN_ID}/visualization").json()

    phases = {phase["id"]: phase["state"] for phase in payload["phases"]}
    assert phases["scientist"] == "skipped"
    assert phases["running"] == "completed"
    assert phases["evaluating"] == "completed"


def test_activity_search_filters_cursor_and_omitted_counts(historical_client: TestClient) -> None:
    _write_activity_bundle(historical_client)
    response = historical_client.get(
        f"/api/v1/runs/{RUN_ID}/activity",
        params={
            "q": "literal%_needle",
            "caseId": "case-alpha",
            "participantId": "agent-1",
            "activityType": "communication",
            "status": "observed",
            "evidenceType": "transcript",
            "occurredFrom": "2026-08-08T10:01:00Z",
            "occurredTo": "2026-08-08T10:01:59Z",
            "limit": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["summary"] for item in payload["items"]] == ["literal%_needle"]
    assert payload["latestSequence"] >= 3
    assert payload["omittedAfter"] == 0

    first = historical_client.get(f"/api/v1/runs/{RUN_ID}/activity", params={"limit": 1}).json()
    assert first["omittedAfter"] >= 2
    assert first["latestSequence"] == first["omittedAfter"] + 1
    second = historical_client.get(
        f"/api/v1/runs/{RUN_ID}/activity", params={"limit": 1, "cursor": first["nextCursor"]}
    ).json()
    assert second["items"][0]["sequence"] == 2


def test_activity_rejects_oversized_page_and_summary_reveal_is_explicit(
    historical_client: TestClient,
) -> None:
    _write_activity_bundle(historical_client)
    assert (
        historical_client.get(f"/api/v1/runs/{RUN_ID}/activity", params={"limit": 201}).status_code
        == 400
    )
    summary = historical_client.get(f"/api/v1/runs/{RUN_ID}/evidence/evidence-1")
    assert summary.status_code == 200
    assert "content" not in summary.json()
    content = historical_client.get(f"/api/v1/runs/{RUN_ID}/evidence/evidence-1/content")
    assert content.status_code == 200
    assert content.json()["redacted"] is False
    download = historical_client.get(f"/api/v1/runs/{RUN_ID}/evidence/evidence-1/download")
    assert download.status_code == 200
    assert "/" not in download.headers["content-disposition"].split('filename="', 1)[-1].rstrip('"')


def test_activity_and_sse_preserve_typed_sandbox_event(historical_client: TestClient) -> None:
    settings = app.dependency_overrides[get_settings]()
    root = Path(settings.artifact_root) / "runs" / RUN_ID
    records = [
        {
            "id": "sandbox-activity",
            "runId": RUN_ID,
            "sequence": 1,
            "occurredAt": "2026-08-08T10:01:00Z",
            "activityType": "execution",
            "status": "execution_started",
            "phase": "case",
            "caseId": "case-alpha",
            "operationId": "operation-1",
            "summary": "Sandbox execution started",
            "evidenceType": "event",
            "detailAvailability": "available",
            "sandboxEvent": {
                "operationId": "operation-1",
                "owner": "evidence-and-content",
                "state": "execution_started",
                "generation": 1,
                "attempt": 1,
                "programSha256": "a" * 64,
                "source": {"state": "captured", "value": "print('ok')"},
            },
        }
    ]
    root.joinpath("activity.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    activity = historical_client.get(f"/api/v1/runs/{RUN_ID}/activity").json()
    assert activity["items"][0]["sandboxEvent"]["state"] == "execution_started"
    assert activity["items"][0]["sandboxEvent"]["operationId"] == "operation-1"
