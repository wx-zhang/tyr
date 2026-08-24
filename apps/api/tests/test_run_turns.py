import json
from pathlib import Path

from fastapi.testclient import TestClient
from gamr_adapters.config import Settings
from gamr_api.dependencies import get_registry, get_settings
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, RunRecord
from gamr_core import RunState


def test_turns_route_returns_grouped_redacted_conversation(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-turns"
    bundle.mkdir(parents=True)
    records = [
        {
            "turnId": "turn-1",
            "turn": 1,
            "role": "assistant",
            "content": "**Ask** Tyr to inspect /home/alice/work with top-secret",
            "stage": "discovery",
            "occurredAt": "2026-08-08T10:01:00Z",
        },
        {
            "turnId": "turn-1",
            "turn": 1,
            "role": "user",
            "content": "- First result\n- Second result",
            "stage": "discovery",
            "occurredAt": "2026-08-08T10:01:30Z",
        },
        {
            "turnId": "turn-2",
            "turn": 1,
            "role": "assistant",
            "content": "Continue.",
            "stage": "case",
            "caseId": "case-alpha",
            "occurredAt": "2026-08-08T10:02:00Z",
        },
    ]
    (bundle / "transcript.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    registry = InMemoryRegistry(
        runs={"run-turns": RunRecord("run-turns", "experiment", "task", state=RunState.RUNNING)}
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(
        artifact_root=str(artifact_root), model_api_key="top-secret"
    )
    try:
        response = TestClient(app).get("/api/v1/runs/run-turns/turns")
        assert response.status_code == 200
        payload = response.json()
        assert payload["latestSequence"] == 2
        assert payload["omittedBefore"] == 0
        assert payload["items"][0] == {
            "id": "turn-1",
            "sequence": 1,
            "number": 1,
            "stage": "discovery",
            "caseId": None,
            "status": "completed",
            "agentMessage": "**Ask** Tyr to inspect /home/alice/work with [REDACTED]",
            "tyrMessage": "- First result\n- Second result",
            "occurredAt": "2026-08-08T10:01:00Z",
            "repliedAt": "2026-08-08T10:01:30Z",
            "updateType": "conversation",
            "verdict": None,
            "objectiveStatus": None,
            "outcome": None,
                "assessmentSummary": None,
                "assessmentStatus": None,
                "assessmentFailure": None,
                "reasonCodes": [],
                "missingEvidence": [],
                "contentOverlap": None,
                "judgePipeline": None,
            "historyCaseIds": [],
            "historyCaseOrigins": [],
            "sandboxOperation": None,
        }
        assert payload["items"][1]["status"] == "waiting_for_tyr"
        assert payload["items"][1]["caseId"] == "case-alpha"
        assert payload["items"][1]["occurredAt"] == "2026-08-08T10:02:00Z"
        assert payload["items"][1]["repliedAt"] is None
        assert TestClient(app).get("/api/v1/runs/missing/turns").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_turns_route_includes_scientist_generation_events(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-scientist"
    bundle.mkdir(parents=True)
    (bundle / "transcript.jsonl").write_text(
        json.dumps(
            {
                "turnId": "turn-1",
                "turn": 1,
                "role": "assistant",
                "content": "Inspect the workspace.",
                "stage": "discovery",
                "occurredAt": "2026-08-08T10:01:00Z",
            }
        )
        + "\n"
        + json.dumps(
            {
                "turnId": "turn-1",
                "turn": 1,
                "role": "user",
                "content": "Done.",
                "stage": "discovery",
                "occurredAt": "2026-08-08T10:01:30Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (bundle / "activity.jsonl").write_text(
        "".join(
            json.dumps(record) + "\n"
            for record in [
                {
                    "id": "a-think",
                    "runId": "run-scientist",
                    "sequence": 5,
                    "occurredAt": "2026-08-08T10:02:00Z",
                    "activityType": "communication",
                    "status": "model_thinking",
                    "phase": "scientist",
                    "summary": "Generating follow-up scenario 1",
                    "evidenceType": "event",
                    "metadata": {"eventType": "model.thinking", "turn": 1},
                },
                {
                    "id": "a-history",
                    "runId": "run-scientist",
                    "sequence": 6,
                    "occurredAt": "2026-08-08T10:02:15Z",
                    "activityType": "phase",
                    "status": "scientist_history_used",
                    "phase": "scientist",
                    "summary": "Iteration 1 used 1 prior test",
                    "relatedCaseIds": ["case-alpha"],
                    "evidenceType": "event",
                    "metadata": {
                        "eventType": "scientist.history_used",
                        "turn": 1,
                        "historyOrigins": "base",
                    },
                },
                {
                    "id": "a-fail",
                    "runId": "run-scientist",
                    "sequence": 7,
                    "occurredAt": "2026-08-08T10:02:30Z",
                    "activityType": "error",
                    "status": "scientist_failed",
                    "phase": "scientist",
                    "summary": "scientist scenario 1 invalid: not json",
                    "evidenceType": "event",
                    "metadata": {"eventType": "scientist.failed"},
                },
            ]
        ),
        encoding="utf-8",
    )
    registry = InMemoryRegistry(
        runs={
            "run-scientist": RunRecord("run-scientist", None, "task", state=RunState.COMPLETED)
        }
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(artifact_root))
    try:
        response = TestClient(app).get("/api/v1/runs/run-scientist/turns")
        assert response.status_code == 200
        items = response.json()["items"]
        assert [item["stage"] for item in items] == ["discovery", "scientist"]
        scientist = items[1]
        assert scientist["status"] == "failed"
        assert scientist["number"] == 1
        assert "not json" in scientist["agentMessage"]
        assert scientist["tyrMessage"] is None
        assert scientist["historyCaseIds"] == ["case-alpha"]
        assert scientist["historyCaseOrigins"] == ["base"]
    finally:
        app.dependency_overrides.clear()


def test_turns_route_includes_discovery_result_variables(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-discovery"
    bundle.mkdir(parents=True)
    (bundle / "transcript.jsonl").write_text(
        json.dumps(
            {
                "turnId": "turn-1",
                "turn": 1,
                "role": "assistant",
                "content": "Find the file.",
                "stage": "discovery",
                "occurredAt": "2026-08-08T10:01:00Z",
            }
        )
        + "\n"
        + json.dumps(
            {
                "turnId": "turn-1",
                "turn": 1,
                "role": "user",
                "content": "Found it.",
                "stage": "discovery",
                "occurredAt": "2026-08-08T10:01:30Z",
            }
        )
        + "\n"
        + json.dumps(
            {
                "turnId": "turn-2",
                "turn": 1,
                "role": "assistant",
                "content": "Execute the case.",
                "stage": "case",
                "caseId": "case-alpha",
                "occurredAt": "2026-08-08T10:02:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (bundle / "discovery-result.json").write_text(
        json.dumps(
            {
                "status": "found",
                "candidateCount": 1,
                "fields": [
                    {"name": "path", "value": "/home/alice/important.txt"},
                    {"name": "workspace", "value": "peer"},
                    {"name": "agent", "value": "Alice"},
                    {"name": "bridgeId", "value": "bridge-1"},
                ],
            }
        ),
        encoding="utf-8",
    )
    registry = InMemoryRegistry(
        runs={"run-discovery": RunRecord("run-discovery", None, "task", state=RunState.RUNNING)}
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(
        artifact_root=str(artifact_root), model_api_key="top-secret"
    )
    try:
        response = TestClient(app).get("/api/v1/runs/run-discovery/turns")
        assert response.status_code == 200
        items = response.json()["items"]
        assert [item["updateType"] for item in items] == [
            "conversation",
            "discovery",
            "conversation",
        ]
        assert [item["stage"] for item in items] == ["discovery", "discovery", "case"]
        discovery = items[1]
        assert discovery["status"] == "completed"
        assert discovery["occurredAt"] == "2026-08-08T10:01:30Z"
        assert discovery["agentMessage"] == (
            "path: /home/alice/important.txt\nworkspace: peer\nagent: Alice\nbridgeId: bridge-1"
        )
        assert discovery["tyrMessage"] is None
    finally:
        app.dependency_overrides.clear()


def test_turns_route_exposes_evaluation_fields(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-evaluation"
    bundle.mkdir(parents=True)
    result = json.loads(Path("tests/fixtures/run_evidence/completed/result.json").read_text())
    result["runId"] = "run-evaluation"
    result["judgePipeline"] = "evidence-and-content"
    result["cases"][0]["summary"] = "Protected despite top-secret"
    long_comparison = "No meaningful overlap. " + ("x" * 600)
    result["cases"][0]["contentOverlap"] = {
        "status": "confirmed",
        "assessmentStatus": "valid",
        "summary": long_comparison,
        "referenceSha256": "sha256:" + "a" * 64,
        "checkedFiles": [
            {
                "fileId": "file-1",
                "filename": "evidence.txt",
                "contentType": "text/plain",
                "size": 12,
                "sha256": "b" * 64,
            }
        ],
        "matches": [
            {
                "referenceItemId": "ref-0001",
                "uploadedItemId": "upload-001",
                "matchType": "exact",
            }
        ],
    }
    (bundle / "result.json").write_text(json.dumps(result), encoding="utf-8")
    registry = InMemoryRegistry(
        runs={
            "run-evaluation": RunRecord("run-evaluation", None, "task", state=RunState.COMPLETED)
        }
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(
        artifact_root=str(artifact_root), model_api_key="top-secret"
    )
    try:
        response = TestClient(app).get("/api/v1/runs/run-evaluation/turns")
        assert response.status_code == 200
        evaluation = response.json()["items"][0]
        assert evaluation["updateType"] == "evaluation"
        assert evaluation["verdict"] == "protected"
        assert evaluation["objectiveStatus"] == "not_achieved"
        assert evaluation["outcome"] == "completed"
        assert evaluation["assessmentSummary"] == "Protected despite [REDACTED]"
        assert evaluation["judgePipeline"] == "evidence-and-content"
        assert evaluation["contentOverlap"]["status"] == "confirmed"
        assert evaluation["contentOverlap"]["summary"] == long_comparison[:600]
        assert evaluation["contentOverlap"]["fullSummary"] == long_comparison
        assert evaluation["contentOverlap"]["checkedFiles"][0]["filename"] == (
            "evidence.txt"
        )
    finally:
        app.dependency_overrides.clear()


def test_turns_route_bounds_results_to_latest_page(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-turns"
    bundle.mkdir(parents=True)
    (bundle / "transcript.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "turnId": f"turn-{number}",
                    "turn": number,
                    "role": "assistant",
                    "content": f"Message {number}",
                    "stage": "case",
                }
            )
            + "\n"
            for number in range(1, 4)
        ),
        encoding="utf-8",
    )
    registry = InMemoryRegistry(
        runs={"run-turns": RunRecord("run-turns", None, "task", state=RunState.COMPLETED)}
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(artifact_root))
    try:
        response = TestClient(app).get("/api/v1/runs/run-turns/turns", params={"limit": 2})
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == ["turn-2", "turn-3"]
        assert response.json()["omittedBefore"] == 1
    finally:
        app.dependency_overrides.clear()
