import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from gamr_adapters.config import Settings
from gamr_api.dependencies import get_registry, get_settings
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, RunRecord
from gamr_core import RunActivity, RunState


def _registry_with_run() -> tuple[InMemoryRegistry, str]:
    registry = InMemoryRegistry()
    experiment = registry.create_experiment("visualization", "datasets/first-plan")
    run = registry.create_run(experiment.id, experiment.dataset)
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
        assert payload["run"]["currentCaseIds"] == ["case-2"]
        assert payload["counts"] == {
            "totalKnown": True,
            "totalCases": 3,
            "completedCases": 1,
        }
        assert payload["cases"][0]["state"] == "completed"
        assert payload["cases"][1]["state"] == "active"
        assert payload["latestSequence"] == 5
    finally:
        app.dependency_overrides.clear()


def test_visualization_states_unknown_totals_and_concurrent_cases_without_false_completion(
) -> None:
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
            "totalCases": None,
            "completedCases": 0,
        }
        assert payload["run"]["currentCaseIds"] == ["case-a", "case-b"]
        assert {case["state"] for case in payload["cases"]} == {"active"}
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
        )
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
    run.configuration = run.configuration.model_copy(update={"scientistIterations": 1})
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
        runs={"run-results": RunRecord("run-results", None, "dataset", RunState.COMPLETED)}
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(artifact_root))
    try:
        response = TestClient(app).get("/api/v1/runs/run-results/visualization")
        assert response.status_code == 200
        case = response.json()["cases"][0]
        assert case["verdict"] == "protected"
        assert case["objectiveStatus"] == "not_achieved"
        assert case["outcome"] == "completed"
        assert case["summary"] == "The observed request was rejected by the target"
    finally:
        app.dependency_overrides.clear()
