from datetime import UTC, datetime
from pathlib import Path

import pytest
from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_api.registry import JsonRegistry
from gamr_core import ExperimentConfig, ExperimentRecord, RunSource, RunState

DISCOVERY_INPUT = {
    "schemaVersion": "1.0",
    "kind": "discovery-input",
    "taskId": "operator-reference",
    "candidate": {
        "path": "/home/alice/work",
        "workspace": "peer",
        "agent": "Alice",
        "bridgeId": "bridge-1",
    },
}

def test_json_registry_persists_and_rediscovers_cli_and_service_runs(tmp_path: Path) -> None:
    registry = JsonRegistry(tmp_path, secrets=("top-secret",))
    experiment = registry.create_experiment(
        "Review", "tasks/exfiltrate-important-txt", ExperimentConfig(model="safe-model")
    )
    service_run = registry.create_run(
        experiment.id,
        experiment.task,
        experiment.configuration,
        source=RunSource.SERVICE,
    )
    cli_run = registry.create_run(
        None,
        "tasks/exfiltrate-important-txt",
        ExperimentConfig(model="cli-model"),
        source=RunSource.CLI,
    )
    registry.set_state(service_run, RunState.PREPARING)

    rediscovered = JsonRegistry(tmp_path)

    assert rediscovered.experiment_presets[experiment.id].name == "Review"
    assert rediscovered.runs[service_run.id].state is RunState.PREPARING
    assert rediscovered.runs[cli_run.id].experiment_id is None
    assert rediscovered.runs[cli_run.id].source is RunSource.CLI
    activities = rediscovered.store.read_activity_records(service_run.id)
    assert [item["sequence"] for item in activities] == [1, 2]
    assert [item["status"] for item in activities] == ["queued", "preparing"]

def test_json_registry_round_trips_discovery_input_for_presets_and_runs(
    tmp_path: Path,
) -> None:
    configuration = ExperimentConfig(
        scenarioIds=["rename-relocate-fresh-agent-upload"],
        discoveryInput=DISCOVERY_INPUT,
        fallbackToDiscovery=True,
    )
    registry = JsonRegistry(tmp_path)
    preset = registry.create_experiment(
        "Provided target", "tasks/exfiltrate-important-txt", configuration
    )
    run = registry.create_run(preset.id, preset.task, configuration, source=RunSource.SERVICE)

    rediscovered = JsonRegistry(tmp_path)

    stored_preset = rediscovered.experiment_presets[preset.id]
    stored_run = rediscovered.runs[run.id]
    assert stored_preset.configuration.discovery_input is not None
    assert stored_preset.configuration.discovery_input.candidate.path == "/home/alice/work"
    assert stored_preset.configuration.fallback_to_discovery is True
    assert stored_run.configuration.discovery_input == stored_preset.configuration.discovery_input


def test_json_registry_refresh_reconciles_external_run_bundles(tmp_path: Path) -> None:
    registry = JsonRegistry(tmp_path)
    store = FilesystemArtifactStore(tmp_path)
    run_id = "cli-refresh"
    started_at = datetime(2026, 8, 30, 10, tzinfo=UTC)
    document = ExperimentRecord(
        id=run_id,
        source=RunSource.CLI,
        state=RunState.RUNNING,
        task="tasks/exfiltrate-important-txt",
        created_at=started_at,
        updated_at=started_at,
    )

    store.write_json(
        f"runs/{run_id}/run.json", document.model_dump(by_alias=True, mode="json")
    )
    registry.refresh()

    assert registry.runs[run_id].state is RunState.RUNNING
    assert registry.runs[run_id].source is RunSource.CLI

    finished_at = datetime(2026, 8, 30, 10, 1, tzinfo=UTC)
    store.write_json(
        f"runs/{run_id}/run.json",
        document.model_copy(
            update={
                "state": RunState.COMPLETED,
                "updated_at": finished_at,
                "finished_at": finished_at,
            }
        ).model_dump(by_alias=True, mode="json"),
    )
    registry.refresh()

    assert registry.runs[run_id].state is RunState.COMPLETED
    assert registry.runs[run_id].updated_at == finished_at
    assert registry.runs[run_id].finished_at == finished_at

    store.delete_run(run_id)
    registry.refresh()

    assert run_id not in registry.runs

def test_json_registry_preserves_values_and_rejects_escaped_ids(tmp_path: Path) -> None:
    registry = JsonRegistry(tmp_path, secrets=("top-secret",))
    run = registry.create_run(
        None,
        "tasks/exfiltrate-important-txt",
        ExperimentConfig(model="model-top-secret"),
        source=RunSource.CLI,
    )

    assert "top-secret" in (tmp_path / "runs" / run.id / "run.json").read_text()
    with pytest.raises(ValueError, match="identifier"):
        registry.get_run("../outside")


def test_json_registry_delete_run_removes_bundle_and_index_entry(tmp_path: Path) -> None:
    registry = JsonRegistry(tmp_path)
    run = registry.create_run(
        None,
        "tasks/exfiltrate-important-txt",
        ExperimentConfig(),
        source=RunSource.CLI,
    )
    run_root = tmp_path / "runs" / run.id
    assert run_root.is_dir()

    registry.delete_run(run.id)

    assert not run_root.exists()
    assert run.id not in registry.runs
    assert registry.get_run(run.id) is None
