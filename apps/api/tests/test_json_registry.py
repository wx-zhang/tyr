from pathlib import Path

import pytest
from gamr_api.registry import JsonRegistry
from gamr_core import ExperimentConfig, RunSource, RunState


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
