from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient
from gamr_api.dependencies import get_registry
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, RunRecord
from gamr_core import ExperimentConfig, RunSource, RunState


def _experiment(client: TestClient) -> str:
    response = client.post(
        "/api/v1/experiments",
        json={"name": "run API test", "dataset": "datasets/first-plan"},
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


def test_list_runs_includes_timestamps_and_orders_newest_first() -> None:
    registry = InMemoryRegistry()
    older = RunRecord(
        "run-older",
        None,
        "datasets/first-plan",
        created_at=datetime(2026, 8, 8, 10, tzinfo=UTC),
        updated_at=datetime(2026, 8, 8, 10, tzinfo=UTC),
        source=RunSource.CLI,
    )
    newer = RunRecord(
        "run-newer",
        None,
        "datasets/first-plan",
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


def test_service_accepts_approval_required_experiment() -> None:
    registry = InMemoryRegistry()
    experiment = registry.create_experiment(
        "action run",
        "first-plan",
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


def test_create_experiment_accepts_dataset_id_and_case_ids() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/experiments",
            json={
                "name": "case selection",
                "dataset": "first-plan",
                "actionMode": "approval_required",
                "caseIds": ["rename-relocate-fresh-agent-upload"],
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["dataset"] == "first-plan"
        assert body["configuration"]["actionMode"] == "approval_required"
        assert body["configuration"]["caseIds"] == ["rename-relocate-fresh-agent-upload"]
    finally:
        app.dependency_overrides.clear()


def test_create_experiment_rejects_unknown_case_id() -> None:
    response = TestClient(app).post(
        "/api/v1/experiments",
        json={
            "name": "bad case",
            "dataset": "first-plan",
            "actionMode": "read_only",
            "caseIds": ["not-a-real-case"],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_dataset"


def test_run_events_support_last_event_id() -> None:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        client = TestClient(app)
        experiment_id = _experiment(client)
        run = client.post(f"/api/v1/experiments/{experiment_id}/runs", json={}).json()
        response = client.get(f"/api/v1/runs/{run['id']}/events")
        assert "id: 1" in response.text
        resumed = client.get(
            f"/api/v1/runs/{run['id']}/events", headers={"Last-Event-ID": "1"}
        )
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
        "datasets/first-plan",
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
        "datasets/first-plan",
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
        "datasets/first-plan",
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
        "datasets/first-plan",
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
