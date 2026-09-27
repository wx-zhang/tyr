import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_adapters.config import Settings
from gamr_api import dependencies
from gamr_api.dependencies import get_registry, get_settings
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, JsonRegistry, RunRecord
from gamr_core import ExperimentConfig, ExperimentRecord, RunSource, RunState

DISCOVERY_INPUT: dict[str, Any] = {
    "schemaVersion": "1.0",
    "kind": "discovery-input",
    "taskId": "informational-task-id",
    "candidate": {
        "path": "/home/alice/work",
        "workspace": "peer",
        "agent": "Alice",
        "bridgeId": "bridge-1",
    },
}


def _experiment(client: TestClient) -> str:
    response = client.post(
        "/api/v1/experiments",
        json={"name": "run API test", "task": "tasks/exfiltrate-important-txt"},
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


def test_list_runs_includes_timestamps_and_orders_newest_first() -> None:
    registry = InMemoryRegistry()
    older = RunRecord(
        "run-older",
        None,
        "tasks/exfiltrate-important-txt",
        created_at=datetime(2026, 8, 8, 10, tzinfo=UTC),
        updated_at=datetime(2026, 8, 8, 10, tzinfo=UTC),
        source=RunSource.CLI,
    )
    newer = RunRecord(
        "run-newer",
        None,
        "tasks/exfiltrate-important-txt",
        created_at=datetime(2026, 8, 9, 12, tzinfo=UTC),
        updated_at=datetime(2026, 8, 9, 12, tzinfo=UTC),
        source=RunSource.CLI,
    )
    registry.runs = {older.id: older, newer.id: newer}
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        payload = TestClient(app).get("/api/v1/runs").json()
    finally:
        app.dependency_overrides.clear()

    assert [item["id"] for item in payload] == ["run-newer", "run-older"]
    assert payload[0]["createdAt"].startswith("2026-08-09T12:00:00")
    assert payload[0]["updatedAt"].startswith("2026-08-09T12:00:00")
    assert payload[0]["finishedAt"] is None


def test_list_runs_includes_compact_scenario_execution_results(
    tmp_path: Path,
) -> None:
    registry = InMemoryRegistry()
    older = RunRecord(
        "run-older",
        None,
        "tasks/exfiltrate-important-txt",
        created_at=datetime(2026, 8, 8, 10, tzinfo=UTC),
        updated_at=datetime(2026, 8, 8, 10, tzinfo=UTC),
        source=RunSource.CLI,
    )
    newer = RunRecord(
        "run-newer",
        None,
        "tasks/exfiltrate-important-txt",
        created_at=datetime(2026, 8, 9, 12, tzinfo=UTC),
        updated_at=datetime(2026, 8, 9, 12, tzinfo=UTC),
        source=RunSource.CLI,
    )
    registry.runs = {older.id: older, newer.id: newer}
    result = json.loads(Path("tests/fixtures/run_evidence/completed/result.json").read_text())
    result["runId"] = newer.id
    result["summary"] = {"vulnerable": 1, "protected": 1, "inconclusive": 1}
    result["cases"] = [
        {
            "scenarioId": "scenario-vulnerable",
            "scenarioExecutionId": "execution-vulnerable",
            "outcome": "completed",
            "objectiveStatus": "achieved",
            "verdict": "vulnerable",
            "summary": "The protected asset was exposed.",
            "evidence": [],
        },
        {
            "scenarioId": "scenario-protected",
            "scenarioExecutionId": "execution-protected",
            "outcome": "completed",
            "objectiveStatus": "not_achieved",
            "verdict": "protected",
            "summary": "The protected asset remained secure.",
            "evidence": [],
        },
        {
            "scenarioId": "scenario-inconclusive",
            "scenarioExecutionId": "execution-inconclusive",
            "outcome": "completed",
            "objectiveStatus": "unknown",
            "verdict": "inconclusive",
            "summary": "The available evidence was inconclusive.",
            "evidence": [],
        },
    ]
    bundle = tmp_path / "runs" / newer.id
    bundle.mkdir(parents=True)
    (bundle / "result.json").write_text(json.dumps(result))
    malformed_bundle = tmp_path / "runs" / older.id
    malformed_bundle.mkdir(parents=True)
    (malformed_bundle / "result.json").write_text("{not valid JSON")
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(tmp_path))
    try:
        response = TestClient(app).get("/api/v1/runs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == ["run-newer", "run-older"]
    assert payload[0]["scenarioExecutions"] == [
        {
            "scenarioId": "scenario-vulnerable",
            "scenarioExecutionId": "execution-vulnerable",
            "order": 0,
            "state": "completed",
            "verdict": "vulnerable",
            "objectiveStatus": "achieved",
            "outcome": "completed",
        },
        {
            "scenarioId": "scenario-protected",
            "scenarioExecutionId": "execution-protected",
            "order": 1,
            "state": "completed",
            "verdict": "protected",
            "objectiveStatus": "not_achieved",
            "outcome": "completed",
        },
        {
            "scenarioId": "scenario-inconclusive",
            "scenarioExecutionId": "execution-inconclusive",
            "order": 2,
            "state": "completed",
            "verdict": "inconclusive",
            "objectiveStatus": "unknown",
            "outcome": "completed",
        },
    ]
    assert payload[1]["scenarioExecutions"] == []


def test_list_runs_refreshes_process_global_json_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = JsonRegistry(tmp_path)
    monkeypatch.setattr(dependencies, "registry", registry)
    client = TestClient(app)

    first_response = client.get("/api/v1/runs")
    assert first_response.status_code == 200
    assert first_response.json() == []

    store = FilesystemArtifactStore(tmp_path)
    run_id = "cli-api-refresh"
    document = ExperimentRecord(
        id=run_id,
        source=RunSource.CLI,
        state=RunState.RUNNING,
        task="tasks/exfiltrate-important-txt",
    )
    store.write_json(f"runs/{run_id}/run.json", document.model_dump(by_alias=True, mode="json"))

    second_response = client.get("/api/v1/runs")

    assert second_response.status_code == 200
    assert second_response.json()[0]["id"] == run_id
    assert second_response.json()[0]["source"] == "cli"


def test_service_accepts_approval_required_experiment() -> None:
    registry = InMemoryRegistry()
    experiment = registry.create_experiment(
        "action run",
        "exfiltrate-important-txt",
        ExperimentConfig(actionMode="approval_required"),
    )
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        response = TestClient(app).post(f"/api/v1/experiments/{experiment.id}/runs", json={})
        assert response.status_code == 202
        body = response.json()
        assert body["id"]
        assert body["state"] == "queued"
        run = registry.runs[body["id"]]
        assert run.configuration.action_mode == "approval_required"
    finally:
        app.dependency_overrides.clear()


def test_starting_a_run_carries_the_experiment_name() -> None:
    registry = InMemoryRegistry()
    experiment = registry.create_experiment("Nightly red team", "exfiltrate-important-txt")
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.post(f"/api/v1/experiments/{experiment.id}/runs", json={})
        assert response.status_code == 202
        run_id = response.json()["id"]
        run_payload = client.get(f"/api/v1/runs/{run_id}").json()
        assert run_payload["name"] == "Nightly red team"
    finally:
        app.dependency_overrides.clear()


def test_retrying_a_run_keeps_its_name() -> None:
    registry = InMemoryRegistry()
    failed = registry.create_run(
        None,
        "tasks/exfiltrate-important-txt",
        source=RunSource.SERVICE,
        name="Nightly red team",
    )
    registry.set_state(failed, RunState.PREPARING)
    registry.set_state(failed, RunState.FAILED)
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        response = TestClient(app).post(f"/api/v1/runs/{failed.id}/retry")
        assert response.status_code == 202
        assert response.json()["name"] == "Nightly red team"
    finally:
        app.dependency_overrides.clear()


def test_create_experiment_and_run_override_max_concurrent_cases() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/experiments",
            json={"name": "default concurrency", "task": "exfiltrate-important-txt"},
        )
        assert response.status_code == 201
        experiment_id = response.json()["id"]
        assert response.json()["configuration"]["maxConcurrentScenarioExecutions"] == 5

        response = client.post(
            "/api/v1/experiments",
            json={
                "name": "custom concurrency",
                "task": "exfiltrate-important-txt",
                "maxConcurrentCases": 2,
            },
        )
        assert response.status_code == 201
        assert response.json()["configuration"]["maxConcurrentScenarioExecutions"] == 2

        for invalid in (0, 6, -1, "many"):
            response = client.post(
                "/api/v1/experiments",
                json={
                    "name": "invalid concurrency",
                    "task": "exfiltrate-important-txt",
                    "maxConcurrentCases": invalid,
                },
            )
            assert response.status_code == 422

        response = client.post(
            f"/api/v1/experiments/{experiment_id}/runs",
            json={"maxConcurrentCases": 3},
        )
        assert response.status_code == 202
        run_payload = client.get(f"/api/v1/runs/{response.json()['id']}").json()
        assert run_payload["configuration"]["maxConcurrentScenarioExecutions"] == 3

        response = client.post(
            f"/api/v1/experiments/{experiment_id}/runs",
            json={"maxConcurrentCases": 10},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_create_experiment_accepts_task_id_and_case_ids() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/experiments",
            json={
                "name": "case selection",
                "task": "exfiltrate-important-txt",
                "actionMode": "approval_required",
                "caseIds": ["rename-relocate-fresh-agent-upload"],
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["task"] == "exfiltrate-important-txt"
        assert body["configuration"]["actionMode"] == "approval_required"
        assert body["configuration"]["scenarioIds"] == ["rename-relocate-fresh-agent-upload"]
    finally:
        app.dependency_overrides.clear()


def test_create_and_start_experiment_persists_discovery_input() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/experiments",
            json={
                "name": "provided target",
                "task": "exfiltrate-important-txt",
                "discoveryInput": DISCOVERY_INPUT,
                "fallbackToDiscovery": True,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["configuration"]["discoveryInput"] == DISCOVERY_INPUT
        assert body["configuration"]["fallbackToDiscovery"] is True

        started = client.post(f"/api/v1/experiments/{body['id']}/runs", json={})
        assert started.status_code == 202
        run = registry.runs[started.json()["id"]]
        assert run.configuration.discovery_input is not None
        assert run.configuration.discovery_input.candidate.bridge_id == "bridge-1"
        assert run.configuration.fallback_to_discovery is True
    finally:
        app.dependency_overrides.clear()


def test_create_experiment_rejects_invalid_discovery_input() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/experiments",
            json={
                "name": "invalid provided target",
                "task": "exfiltrate-important-txt",
                "fallbackToDiscovery": True,
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "invalid_task"

        response = client.post(
            "/api/v1/experiments",
            json={
                "name": "empty provided path",
                "task": "exfiltrate-important-txt",
                "discoveryInput": {
                    **DISCOVERY_INPUT,
                    "candidate": {**DISCOVERY_INPUT["candidate"], "path": ""},
                },
            },
        )
        assert response.status_code == 422
        response = client.post(
            "/api/v1/experiments",
            json={
                "name": "server path target",
                "task": "exfiltrate-important-txt",
                "discoveryInput": {
                    **DISCOVERY_INPUT,
                    "candidate": {
                        **DISCOVERY_INPUT["candidate"],
                        "serverPath": "/srv/secret",
                    },
                },
            },
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_create_experiment_accepts_configured_scientist_history_windows() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        response = TestClient(app).post(
            "/api/v1/experiments",
            json={
                "name": "history windows",
                "task": "exfiltrate-important-txt",
                "caseIds": [],
                "scientistIterations": 1,
                "historyTestRuns": 7,
                "historyScientistRuns": 3,
            },
        )
        assert response.status_code == 201
        configuration = response.json()["configuration"]
        assert configuration["historyTestRuns"] == 7
        assert configuration["historyResearchRuns"] == 3
    finally:
        app.dependency_overrides.clear()


def test_create_experiment_rejects_unknown_case_id() -> None:
    response = TestClient(app).post(
        "/api/v1/experiments",
        json={
            "name": "bad case",
            "task": "exfiltrate-important-txt",
            "actionMode": "read_only",
            "caseIds": ["not-a-real-case"],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_task"


def test_start_run_supports_scientist_only_and_rejects_empty_disabled_runs() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        experiment_id = _experiment(client)

        scientist_only = client.post(
            f"/api/v1/experiments/{experiment_id}/runs",
            json={
                "caseIds": [],
                "scientistIterations": 1,
                "historyTestRuns": 2,
                "historyScientistRuns": 4,
            },
        )
        assert scientist_only.status_code == 202
        run = registry.runs[scientist_only.json()["id"]]
        assert run.configuration.case_ids == []
        assert run.configuration.scientist_iterations == 1
        assert run.configuration.history_test_runs == 2
        assert run.configuration.history_scientist_runs == 4

        invalid = client.post(
            f"/api/v1/experiments/{experiment_id}/runs",
            json={"caseIds": [], "scientistIterations": 0},
        )
        assert invalid.status_code == 400
        assert invalid.json()["detail"]["code"] == "invalid_configuration"
    finally:
        app.dependency_overrides.clear()


def test_run_events_support_last_event_id() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        experiment_id = _experiment(client)
        run = client.post(f"/api/v1/experiments/{experiment_id}/runs", json={}).json()
        response = client.get(f"/api/v1/runs/{run['id']}/events")
        assert "id: 1" in response.text
        resumed = client.get(f"/api/v1/runs/{run['id']}/events", headers={"Last-Event-ID": "1"})
        assert ": heartbeat; interval=15" in resumed.text
        assert "event: heartbeat" in resumed.text
        assert '"interval": 15' in resumed.text
    finally:
        app.dependency_overrides.clear()


def test_cancelled_queued_run_is_persisted() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        experiment_id = _experiment(client)
        run = client.post(f"/api/v1/experiments/{experiment_id}/runs", json={}).json()
        cancelled = client.post(f"/api/v1/runs/{run['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["state"] == "cancelled"
        assert client.get(f"/api/v1/runs/{run['id']}").json()["state"] == "cancelled"
    finally:
        app.dependency_overrides.clear()


def test_delete_run_removes_it_from_the_registry() -> None:
    registry = InMemoryRegistry()
    finished = registry.create_run(
        None,
        "tasks/exfiltrate-important-txt",
        ExperimentConfig(),
        source=RunSource.SERVICE,
    )
    registry.set_state(finished, RunState.PREPARING)
    registry.set_state(finished, RunState.DISCOVERING)
    registry.set_state(finished, RunState.RUNNING)
    registry.set_state(finished, RunState.EVALUATING)
    registry.set_state(finished, RunState.REPORTING)
    registry.set_state(finished, RunState.COMPLETED)
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/runs/{finished.id}")
        assert response.status_code == 204
        assert client.get(f"/api/v1/runs/{finished.id}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_delete_run_removes_a_queued_run_without_requiring_cancel_first() -> None:
    registry = InMemoryRegistry()
    queued = registry.create_run(
        None,
        "tasks/exfiltrate-important-txt",
        ExperimentConfig(),
        source=RunSource.SERVICE,
    )
    assert queued.state is RunState.QUEUED
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/runs/{queued.id}")
        assert response.status_code == 204
        assert client.get(f"/api/v1/runs/{queued.id}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_delete_run_rejects_a_run_still_in_progress() -> None:
    registry = InMemoryRegistry()
    running = registry.create_run(
        None,
        "tasks/exfiltrate-important-txt",
        ExperimentConfig(),
        source=RunSource.SERVICE,
    )
    registry.set_state(running, RunState.PREPARING)
    registry.set_state(running, RunState.DISCOVERING)
    registry.set_state(running, RunState.RUNNING)
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/runs/{running.id}")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "run_not_deletable"
        assert client.get(f"/api/v1/runs/{running.id}").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_delete_run_returns_404_for_unknown_run() -> None:
    client = TestClient(app)
    response = client.delete("/api/v1/runs/does-not-exist")
    assert response.status_code == 404


def test_retry_creates_a_linked_new_bundle_and_approval_routes_are_removed() -> None:
    registry = InMemoryRegistry()
    failed = registry.create_run(
        None,
        "tasks/exfiltrate-important-txt",
        ExperimentConfig(),
        source=RunSource.SERVICE,
    )
    registry.set_state(failed, RunState.PREPARING)
    registry.set_state(failed, RunState.FAILED)
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.post(f"/api/v1/runs/{failed.id}/retry")
        assert response.status_code == 202
        assert response.json()["id"] != failed.id
        assert response.json()["retryOf"] == failed.id
        assert client.get(f"/api/v1/runs/{failed.id}/approvals").status_code == 404
    finally:
        app.dependency_overrides.clear()
