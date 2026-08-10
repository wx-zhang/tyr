import json
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from gamr_adapters.config import Settings
from gamr_api.dependencies import get_registry, get_settings
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, JsonRegistry, RunRecord
from gamr_core import RunState


@contextmanager
def registry_client() -> Iterator[tuple[TestClient, InMemoryRegistry]]:
    registry = InMemoryRegistry()
    app.dependency_overrides[get_registry] = lambda: registry
    try:
        yield TestClient(app), registry
    finally:
        app.dependency_overrides.pop(get_registry, None)


def make_run(registry: InMemoryRegistry) -> RunRecord:
    experiment = registry.create_experiment("busy run", "fixture-evidence")
    return registry.create_run(experiment.id, experiment.dataset)


def test_replay_window_emits_one_resync_signal_instead_of_unbounded_events() -> None:
    with registry_client() as (client, registry):
        run = make_run(registry)
        for index in range(1001):
            registry.append_event(run, f"activity.{index}", {"index": index})

        response = client.get(f"/api/v1/runs/{run.id}/events")

        assert response.status_code == 200
        assert response.text.count("event: resync-required") == 1
        assert "event: run-activity" not in response.text
        assert "event: heartbeat" in response.text
        assert "event: resync-required" in response.text
        payload = json.loads(response.text.split("data: ", 1)[1].split("\n", 1)[0])
        assert payload["latestSequence"] == 1002


def test_event_stream_includes_fifteen_second_heartbeat_and_reconnects_in_sequence() -> None:
    with registry_client() as (client, registry):
        run = make_run(registry)
        registry.append_event(run, "activity.second", {"index": 2})
        registry.append_event(run, "activity.third", {"index": 3})

        response = client.get(
            f"/api/v1/runs/{run.id}/events", headers={"Last-Event-ID": "1"}
        )

        assert ": heartbeat; interval=15" in response.text
        assert "event: heartbeat" in response.text
        assert '"interval": 15' in response.text
        assert [line for line in response.text.splitlines() if line.startswith("id: ")] == [
            "id: 2",
            "id: 3",
        ]


def test_json_bundle_event_stream_survives_unsafe_transcript_summary(tmp_path) -> None:
    artifact_root = tmp_path / ".gamr"
    registry = JsonRegistry(artifact_root)
    run = registry.create_run(None, "fixture-evidence")
    (artifact_root / "runs" / run.id / "transcript.jsonl").write_text(
        json.dumps({"turnId": "turn-1", "content": "Search /home for important.txt."}) + "\n",
        encoding="utf-8",
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=str(artifact_root))
    try:
        response = TestClient(app).get(f"/api/v1/runs/{run.id}/events")
    finally:
        app.dependency_overrides.pop(get_registry, None)
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert "event: run-activity" in response.text


def test_stale_replay_cursor_requests_resync_and_interrupted_run_has_no_result() -> None:
    with registry_client() as (client, registry):
        run = make_run(registry)
        registry.set_state(run, RunState.PREPARING)
        registry.set_state(run, RunState.DISCOVERING)
        registry.set_state(run, RunState.RUNNING)
        run.state = RunState.INTERRUPTED
        registry.append_event(run, "run.interrupted", {"reason": "service_stopped"})

        response = client.get(
            f"/api/v1/runs/{run.id}/events", headers={"Last-Event-ID": "999"}
        )

        assert response.status_code == 200
        assert "event: resync-required" in response.text
        assert client.get(f"/api/v1/runs/{run.id}/cases").json() == []
        assert client.get(f"/api/v1/runs/{run.id}").json()["state"] == "interrupted"


def test_run_activity_events_are_named_ordered_resumable_and_heartbeat() -> None:
    with registry_client() as (client, registry):
        run = make_run(registry)
        registry.set_state(run, RunState.PREPARING)

        response = client.get(f"/api/v1/runs/{run.id}/events")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: run-activity" in response.text
        assert "id: 1" in response.text
        assert "id: 2" in response.text
        assert ": heartbeat" in response.text
        assert "event: heartbeat" in response.text
        assert response.text.index("id: 1") < response.text.index("id: 2")

        resumed = client.get(
            f"/api/v1/runs/{run.id}/events", headers={"Last-Event-ID": "1"}
        )
        assert "id: 1" not in resumed.text
        assert "id: 2" in resumed.text


def test_events_require_a_run_authorized_for_the_current_request() -> None:
    with registry_client() as (client, _registry):
        response = client.get("/api/v1/runs/not-authorized/events")
        assert response.status_code == 404
