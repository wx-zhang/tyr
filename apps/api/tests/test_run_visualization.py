import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from gamr_adapters.config import Settings
from gamr_api.dependencies import get_registry, get_settings
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, RunRecord
from gamr_core import ExperimentPresetConfig, RunActivity, RunState


def _registry_with_run() -> tuple[InMemoryRegistry, str]:
    registry = InMemoryRegistry()
    experiment = registry.create_experiment("visualization", "tasks/exfiltrate-important-txt")
    run = registry.create_run(experiment.id, experiment.task)
    return registry, run.id


def _client(registry: InMemoryRegistry) -> TestClient:
    app.dependency_overrides[get_registry] = lambda: registry
    return TestClient(app)


def _activity(
    run_id: str,
    sequence: int,
    *,
    activity_type: str = "case",
    status: str = "active",
    phase: str | None = None,
    case_id: str | None = None,
    scenario_id: str | None = None,
    scenario_execution_id: str | None = None,
    summary: str = "Case is active",
    operation_id: str | None = None,
) -> RunActivity:
    return RunActivity.model_validate(
        {
            "id": f"activity-{sequence}",
            "runId": run_id,
            "sequence": sequence,
            "occurredAt": datetime(2026, 8, 8, 10, 0, sequence, tzinfo=UTC),
            "activityType": activity_type,
            "status": status,
            "phase": phase,
            "caseId": case_id,
            "scenarioId": scenario_id,
            "scenarioExecutionId": scenario_execution_id,
            "operationId": operation_id,
            "evidenceType": "event",
            "summary": summary,
        }
    )


def test_visualization_returns_typed_progress_with_counts_and_current_work() -> None:
    registry, run_id = _registry_with_run()
    run = registry.runs[run_id]
    registry.set_state(run, RunState.PREPARING)
    registry.set_state(run, RunState.DISCOVERING)
    registry.set_state(run, RunState.RUNNING)
    registry.activities[run_id] = [
        _activity(run_id, 3, phase="running", case_id="case-1"),
        _activity(run_id, 4, status="completed", phase="running", case_id="case-1"),
        _activity(run_id, 5, status="active", phase="running", case_id="case-2"),
    ]
    registry.case_runs[run_id] = [
        {"caseId": "case-1", "order": 0, "status": "completed", "verdict": "protected"},
        {"caseId": "case-2", "order": 1, "status": "active", "verdict": None},
        {"caseId": "case-3", "order": 2, "status": "pending", "verdict": None},
    ]

    try:
        response = _client(registry).get(f"/api/v1/runs/{run_id}/visualization")
        assert response.status_code == 200
        payload = response.json()
        assert payload["run"]["state"] == "running"
        assert payload["run"]["actionMode"] == "read_only"
        assert payload["run"]["currentPhase"] == "running"
        assert payload["run"]["currentScenarioExecutionIds"] == ["case-2"]
        assert payload["counts"] == {
            "totalKnown": True,
            "totalScenarioExecutions": 3,
            "completedScenarioExecutions": 1,
        }
        assert payload["scenarioExecutions"][0]["state"] == "completed"
        assert payload["scenarioExecutions"][1]["state"] == "active"
        assert payload["latestSequence"] == 5
    finally:
        app.dependency_overrides.clear()

def test_visualization_preserves_distinct_scenario_and_execution_ids() -> None:
    registry, run_id = _registry_with_run()
    run = registry.runs[run_id]
    registry.set_state(run, RunState.PREPARING)
    registry.set_state(run, RunState.DISCOVERING)
    registry.set_state(run, RunState.RUNNING)
    registry.activities[run_id] = [
        _activity(
            run_id,
            1,
            phase="running",
            scenario_id="scenario-1",
            scenario_execution_id="execution-1",
        )
    ]
    registry.scenario_executions[run_id] = [
        {
            "scenarioId": "scenario-1",
            "scenarioExecutionId": "execution-1",
            "order": 0,
            "status": "active",
        }
    ]

    try:
        response = _client(registry).get(f"/api/v1/runs/{run_id}/visualization")
        assert response.status_code == 200
        execution = response.json()["scenarioExecutions"][0]
        assert execution["scenarioId"] == "scenario-1"
        assert execution["scenarioExecutionId"] == "execution-1"
        assert "caseId" not in execution
    finally:
        app.dependency_overrides.clear()


def test_visualization_states_unknown_totals_and_concurrent_cases_without_false_completion() -> (
    None
):
    registry, run_id = _registry_with_run()
    run = registry.runs[run_id]
    registry.set_state(run, RunState.PREPARING)
    registry.set_state(run, RunState.DISCOVERING)
    registry.set_state(run, RunState.RUNNING)
    registry.activities[run_id] = [
        _activity(run_id, 2, case_id="case-a", status="active"),
        _activity(run_id, 3, case_id="case-b", status="active"),
    ]

    try:
        payload = _client(registry).get(f"/api/v1/runs/{run_id}/visualization").json()
        assert payload["counts"] == {
            "totalKnown": False,
            "totalScenarioExecutions": None,
            "completedScenarioExecutions": 0,
        }
        assert payload["run"]["currentScenarioExecutionIds"] == ["case-a", "case-b"]
        assert {case["state"] for case in payload["scenarioExecutions"]} == {"active"}
    finally:
        app.dependency_overrides.clear()


def test_visualization_exposes_blockers_approvals_and_unsettled_tyr_work() -> None:
    registry, run_id = _registry_with_run()
    run = registry.runs[run_id]
    registry.set_state(run, RunState.PREPARING)
    registry.set_state(run, RunState.DISCOVERING)
    registry.set_state(run, RunState.RUNNING)
    registry.set_state(run, RunState.WAITING_FOR_APPROVAL)
    registry.activities[run_id] = [
        _activity(
            run_id,
            2,
            activity_type="approval",
            status="pending",
            summary="Human approval is pending",
        ),
        _activity(
            run_id,
            3,
            activity_type="tyr_operation",
            status="pending",
            summary="Waiting for Tyr operation to settle",
            operation_id="operation-1",
        ),
    ]

    try:
        payload = _client(registry).get(f"/api/v1/runs/{run_id}/visualization").json()
        assert payload["attention"] == {
            "pendingApprovalCount": 1,
            "blockers": ["Human approval is pending", "Waiting for Tyr operation to settle"],
            "unsettledTyrWork": True,
        }
        assert payload["run"]["state"] == "waiting_for_approval"
    finally:
        app.dependency_overrides.clear()


def test_visualization_preserves_terminal_history_and_marks_terminal_outcome() -> None:
    registry, run_id = _registry_with_run()
    run = registry.runs[run_id]
    registry.set_state(run, RunState.PREPARING)
    registry.set_state(run, RunState.FAILED)
    registry.activities[run_id] = [
        _activity(run_id, 3, phase="preparing", status="failed", summary="Preparation failed")
    ]

    try:
        payload = _client(registry).get(f"/api/v1/runs/{run_id}/visualization").json()
        assert payload["run"]["state"] == "failed"
        assert payload["run"]["outcome"] == "failed"
        assert payload["run"]["finishedAt"] is not None
        assert payload["latestSequence"] == 3
        assert any(phase["state"] == "failed" for phase in payload["phases"])
    finally:
        app.dependency_overrides.clear()


def test_visualization_does_not_disclose_an_unknown_run() -> None:
    registry, _ = _registry_with_run()
    try:
        response = _client(registry).get("/api/v1/runs/missing/visualization")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_visualization_marks_scientist_active_while_run_state_is_running() -> None:
    registry, run_id = _registry_with_run()
    run = registry.runs[run_id]
    run.configuration = run.configuration.model_copy(
        update={"scenario_ids": [], "research_iterations": 1}
    )
    registry.set_state(run, RunState.PREPARING)
    registry.set_state(run, RunState.DISCOVERING)
    registry.set_state(run, RunState.RUNNING)
    registry.activities[run_id] = [
        _activity(run_id, 3, phase="case", case_id="case-1", status="completed"),
        _activity(
            run_id,
            4,
            activity_type="phase",
            phase="scientist",
            status="scientist_started",
            summary="1 iteration(s)",
        ),
        _activity(
            run_id,
            5,
            phase="scientist",
            case_id="scientist-1",
            status="active",
            summary="Scientist case active",
        ),
    ]

    try:
        payload = _client(registry).get(f"/api/v1/runs/{run_id}/visualization").json()
        assert payload["run"]["state"] == "running"
        assert payload["run"]["currentPhase"] == "scientist"
        assert payload["run"]["executionMode"] == "scientist_only"
        phases = {phase["id"]: phase["state"] for phase in payload["phases"]}
        assert phases["running"] == "completed"
        assert phases["scientist"] == "active"
        assert phases["evaluating"] == "pending"
    finally:
        app.dependency_overrides.clear()


def test_visualization_marks_scientist_skipped_when_disabled() -> None:
    registry, run_id = _registry_with_run()
    run = registry.runs[run_id]
    run.configuration = run.configuration.model_copy(update={"scientistIterations": 0})
    registry.set_state(run, RunState.PREPARING)
    registry.set_state(run, RunState.DISCOVERING)
    registry.set_state(run, RunState.RUNNING)
    registry.activities[run_id] = [
        _activity(run_id, 3, phase="case", case_id="case-1", status="active"),
    ]

    try:
        payload = _client(registry).get(f"/api/v1/runs/{run_id}/visualization").json()
        phases = {phase["id"]: phase["state"] for phase in payload["phases"]}
        assert payload["run"]["currentPhase"] == "running"
        assert phases["scientist"] == "skipped"
        assert phases["running"] == "active"
    finally:
        app.dependency_overrides.clear()


def test_visualization_concurrent_case_states_and_redaction() -> None:
    registry, run_id = _registry_with_run()
    run = registry.runs[run_id]
    registry.set_state(run, RunState.PREPARING)
    registry.set_state(run, RunState.DISCOVERING)
    registry.set_state(run, RunState.RUNNING)
    registry.activities[run_id] = [
        _activity(
            run_id, 1, phase="case", case_id="case-1", status="active", summary="Case 1 active"
        ),
        _activity(
            run_id, 2, phase="case", case_id="case-2", status="active", summary="Case 2 active"
        ),
        _activity(
            run_id,
            3,
            phase="assessment",
            case_id="case-1",
            status="assessing",
            summary="Case 1 assessing",
        ),
        _activity(
            run_id, 4, phase="case", case_id="case-3", status="active", summary="Case 3 active"
        ),
        _activity(
            run_id,
            5,
            phase="case",
            case_id="case-2",
            status="completed",
            summary="Case 2 completed",
        ),
    ]
    registry.case_runs[run_id] = [
        {"caseId": "case-1", "order": 0, "status": "pending", "verdict": None},
        {"caseId": "case-2", "order": 1, "status": "pending", "verdict": None},
        {"caseId": "case-3", "order": 2, "status": "pending", "verdict": None},
        {"caseId": "case-4", "order": 3, "status": "pending", "verdict": None},
    ]

    try:
        response = _client(registry).get(f"/api/v1/runs/{run_id}/visualization")
        assert response.status_code == 200
        payload = response.json()
        # Nonterminal active cases include case-1 (assessing), case-3 (active)
        assert set(payload["run"]["currentScenarioExecutionIds"]) == {"case-1", "case-3"}
        execution_map = {
            item["scenarioExecutionId"]: item
            for item in payload["scenarioExecutions"]
        }
        assert execution_map["case-1"]["state"] == "assessing"
        assert execution_map["case-2"]["state"] == "completed"
        assert execution_map["case-3"]["state"] == "active"
        assert execution_map["case-4"]["state"] == "pending"

        # Check browser redaction - protected checkpoint or operation keys shouldn't leak
        raw_text = json.dumps(payload)
        assert "idempotencyKey" not in raw_text
        assert "operationId" not in raw_text or payload.get("operationId") is None
    finally:
        app.dependency_overrides.clear()

        app.dependency_overrides.clear()


def test_visualization_keeps_precise_case_lifecycle_through_intermediate_activity() -> None:
    registry, run_id = _registry_with_run()
    run = registry.runs[run_id]
    registry.set_state(run, RunState.PREPARING)
    registry.set_state(run, RunState.DISCOVERING)
    registry.set_state(run, RunState.RUNNING)
    registry.case_runs[run_id] = [
        {"caseId": f"case-{index}", "order": index, "status": "pending"} for index in range(1, 6)
    ]
    registry.activities[run_id] = [
        _activity(run_id, 1, status="case_queued", case_id="case-1"),
        _activity(run_id, 2, status="case_started", case_id="case-2"),
        _activity(
            run_id,
            3,
            activity_type="communication",
            status="model_thinking",
            case_id="case-2",
        ),
        _activity(run_id, 4, status="case_started", case_id="case-3"),
        _activity(
            run_id,
            5,
            activity_type="finding",
            status="assessment_started",
            case_id="case-3",
        ),
        _activity(
            run_id,
            6,
            activity_type="finding",
            status="assessment_completed",
            case_id="case-3",
        ),
        _activity(run_id, 7, status="case_started", case_id="case-4"),
        _activity(run_id, 8, status="case_completed", case_id="case-4"),
    ]

    try:
        payload = _client(registry).get(f"/api/v1/runs/{run_id}/visualization").json()
        execution_states = {
            item["scenarioExecutionId"]: item["state"]
            for item in payload["scenarioExecutions"]
        }
        assert execution_states == {
            "case-1": "queued",
            "case-2": "active",
            "case-3": "assessing",
            "case-4": "completed",
            "case-5": "pending",
        }
        assert set(payload["run"]["currentScenarioExecutionIds"]) == {"case-2", "case-3"}
    finally:
        app.dependency_overrides.clear()


def test_visualization_includes_discovery_result_with_peer_paths(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-discovery"
    bundle.mkdir(parents=True)
    (bundle / "run.json").write_text(
        json.dumps(
            {
                "id": "run-discovery",
                "state": "running",
                "task": "tasks/exfiltrate-important-txt",
                "actionMode": "read_only",
                "startedAt": "2026-08-08T10:00:00Z",
                "updatedAt": "2026-08-08T10:02:00Z",
            }
        ),
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
    (bundle / "activity.jsonl").write_text("", encoding="utf-8")
    registry = InMemoryRegistry(
        runs={
            "run-discovery": RunRecord(
                "run-discovery", None, "tasks/exfiltrate-important-txt", RunState.RUNNING
            )
        }
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(
        artifact_root=str(artifact_root), model_api_key="top-secret"
    )
    try:
        response = TestClient(app).get("/api/v1/runs/run-discovery/visualization")
        assert response.status_code == 200
        discovery = response.json()["discoveryResult"]
        assert discovery["status"] == "found"
        assert discovery["candidateCount"] == 1
        assert discovery["fields"] == [
            {"name": "path", "value": "/home/alice/important.txt"},
            {"name": "workspace", "value": "peer"},
            {"name": "agent", "value": "Alice"},
            {"name": "bridgeId", "value": "bridge-1"},
        ]
    finally:
        app.dependency_overrides.clear()


def test_visualization_preserves_secrets_in_discovery_result(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-discovery-secret"
    bundle.mkdir(parents=True)
    (bundle / "run.json").write_text(
        json.dumps(
            {
                "id": "run-discovery-secret",
                "state": "running",
                "task": "tasks/exfiltrate-important-txt",
                "actionMode": "read_only",
                "startedAt": "2026-08-08T10:00:00Z",
                "updatedAt": "2026-08-08T10:02:00Z",
            }
        ),
        encoding="utf-8",
    )
    (bundle / "discovery-result.json").write_text(
        json.dumps(
            {
                "status": "found",
                "candidateCount": 1,
                "fields": [
                    {"name": "path", "value": "/home/alice/top-secret.txt"},
                    {"name": "workspace", "value": "peer"},
                    {"name": "agent", "value": "Alice"},
                    {"name": "bridgeId", "value": "bridge-1"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (bundle / "activity.jsonl").write_text("", encoding="utf-8")
    registry = InMemoryRegistry(
        runs={
            "run-discovery-secret": RunRecord(
                "run-discovery-secret", None, "tasks/exfiltrate-important-txt", RunState.RUNNING
            )
        }
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(
        artifact_root=str(artifact_root), model_api_key="top-secret"
    )
    try:
        response = TestClient(app).get("/api/v1/runs/run-discovery-secret/visualization")
        assert response.status_code == 200
        fields = {
            item["name"]: item["value"] for item in response.json()["discoveryResult"]["fields"]
        }
        assert fields["path"] == "/home/alice/top-secret.txt"
        assert fields["workspace"] == "peer"
    finally:
        app.dependency_overrides.clear()


def test_historical_visualization_merges_canonical_case_results(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    source = Path("tests/fixtures/run_evidence/completed")
    bundle = artifact_root / "runs" / "run-results"
    bundle.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file():
            (bundle / path.name).write_bytes(path.read_bytes())
    run_document = json.loads((bundle / "run.json").read_text())
    run_document["id"] = "run-results"
    run_document["runId"] = "run-results"
    (bundle / "run.json").write_text(json.dumps(run_document))
    result = json.loads((bundle / "result.json").read_text())
    result["runId"] = "run-results"
    (bundle / "result.json").write_text(json.dumps(result))
    registry = InMemoryRegistry(
        runs={"run-results": RunRecord("run-results", None, "task", RunState.COMPLETED)}
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(artifact_root))
    try:
        response = TestClient(app).get("/api/v1/runs/run-results/visualization")
        assert response.status_code == 200
        execution = response.json()["scenarioExecutions"][0]
        assert execution["verdict"] == "protected"
        assert execution["objectiveStatus"] == "not_achieved"
        assert execution["outcome"] == "completed"
        assert execution["summary"] == "The observed request was rejected by the target"
    finally:
        app.dependency_overrides.clear()


def test_visualization_includes_content_overlap_and_decoding_provenance(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-vis-dec"
    bundle.mkdir(parents=True)
    (bundle / "run.json").write_text(
        json.dumps(
            {
                "id": "run-vis-dec",
                "state": "completed",
                "task": "tasks/exfiltrate-important-txt",
                "actionMode": "read_only",
                "startedAt": "2026-08-08T10:00:00Z",
                "finishedAt": "2026-08-08T10:05:00Z",
            }
        ),
        encoding="utf-8",
    )
    result_payload = {
        "runId": "run-vis-dec",
        "judgePipeline": "evidence-and-content",
        "task": {"id": "exfil", "version": "1.0", "digest": "sha256:" + "0" * 64},
        "startedAt": "2026-08-08T10:00:00Z",
        "finishedAt": "2026-08-08T10:05:00Z",
        "outcome": "completed",
        "configuration": {"actionMode": "read_only"},
        "summary": {"vulnerable": 0, "protected": 0, "inconclusive": 1},
        "cases": [
            {
                "scenarioId": "case-dec-failed",
                "outcome": "completed",
                "objectiveStatus": "partial",
                "verdict": "inconclusive",
                "summary": "Decoding failed with timeout.",
                "evidence": [],
                "assessmentStatus": "failed",
                "contentOverlap": {
                    "status": "inconclusive",
                    "assessmentStatus": "failed",
                    "summary": "Decoding timed out",
                    "checkedFiles": [
                        {
                            "fileId": "file-1",
                            "filename": "heavy.bin",
                            "contentType": "application/octet-stream",
                            "size": 2048,
                            "sha256": "f" * 64,
                        }
                    ],
                    "matches": [],
                    "decoding": {
                        "status": "failed",
                        "action": "execute",
                        "rationale": "The file requires a bounded transform.",
                        "attemptCount": 1,
                        "failureCode": "timeout",
                        "failureStage": "execution",
                        "programSha256": ["e" * 64],
                        "limitFlags": {"timedOut": True, "outputLimited": False},
                        "derivedFiles": [],
                        "attempts": [
                            {
                                "attempt": 1,
                                "stage": "execution",
                                "source": "print('bounded')",
                                "programSha256": "e" * 64,
                                "execution": {
                                    "exitCode": None,
                                    "elapsedSeconds": 10.0,
                                    "timedOut": True,
                                    "outputLimited": False,
                                    "stdout": {"state": "empty"},
                                    "stderr": {"state": "suppressed"},
                                },
                                "derivedFiles": [],
                            }
                        ],
                    },
                },
            }
        ],
        "findings": [],
        "errors": [],
    }
    (bundle / "result.json").write_text(json.dumps(result_payload), encoding="utf-8")
    (bundle / "activity.jsonl").write_text("", encoding="utf-8")

    registry = InMemoryRegistry(
        runs={
            "run-vis-dec": RunRecord(
                "run-vis-dec", None, "tasks/exfiltrate-important-txt", RunState.COMPLETED
            )
        }
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(artifact_root))
    try:
        response = TestClient(app).get("/api/v1/runs/run-vis-dec/visualization")
        assert response.status_code == 200
        execution = response.json()["scenarioExecutions"][0]
        assert execution["scenarioExecutionId"] == "case-dec-failed"
        assert execution["contentOverlap"]["status"] == "inconclusive"
        decoding = execution["contentOverlap"]["decoding"]
        assert decoding["status"] == "failed"
        assert decoding["failureCode"] == "timeout"
        assert decoding["action"] == "execute"
        assert decoding["rationale"] == "The file requires a bounded transform."
        assert decoding["failureStage"] == "execution"
        assert decoding["attempts"][0]["source"] == "print('bounded')"
        assert decoding["attempts"][0]["execution"]["stderr"]["state"] == "suppressed"
        assert decoding["limitFlags"]["timedOut"] is True
        assert decoding["programSha256"] == ["e" * 64]
        assert decoding["derivedFiles"] == []
    finally:
        app.dependency_overrides.clear()


def test_visualization_does_not_duplicate_started_scenario_as_pending_definition(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-dup"
    bundle.mkdir(parents=True)
    (bundle / "run.json").write_text(
        json.dumps(
            {
                "id": "run-dup",
                "state": "running",
                "task": "tasks/exfiltrate-important-txt",
                "configuration": {
                    "actionMode": "read_only",
                    "scenarioIds": [
                        "rename-relocate-fresh-agent-upload",
                        "visualize-file-as-image-fresh-agent-upload",
                    ],
                },
                "startedAt": "2026-08-08T10:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (bundle / "activity.jsonl").write_text(
        json.dumps(
            {
                "id": "activity-1",
                "runId": "run-dup",
                "sequence": 1,
                "occurredAt": "2026-08-08T10:00:01Z",
                "activityType": "case",
                "status": "active",
                "phase": "running",
                "scenarioId": "rename-relocate-fresh-agent-upload",
                "scenarioExecutionId": "execution-uuid-1",
                "evidenceType": "event",
                "summary": "Scenario is active",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    registry = InMemoryRegistry(
        runs={
            "run-dup": RunRecord(
                "run-dup",
                None,
                "tasks/exfiltrate-important-txt",
                RunState.RUNNING,
                configuration=ExperimentPresetConfig(
                    scenarioIds=[
                        "rename-relocate-fresh-agent-upload",
                        "visualize-file-as-image-fresh-agent-upload",
                    ]
                ),
            )
        }
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(artifact_root))
    try:
        response = TestClient(app).get("/api/v1/runs/run-dup/visualization")
        assert response.status_code == 200
        executions = response.json()["scenarioExecutions"]
        assert [
            (item["scenarioId"], item["scenarioExecutionId"], item["state"]) for item in executions
        ] == [
            ("rename-relocate-fresh-agent-upload", "execution-uuid-1", "active"),
            (
                "visualize-file-as-image-fresh-agent-upload",
                "visualize-file-as-image-fresh-agent-upload",
                "pending",
            ),
        ]
    finally:
        app.dependency_overrides.clear()
