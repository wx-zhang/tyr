import asyncio
from pathlib import Path

import pytest
from gamr_api.execution import RunTaskManager
from gamr_api.registry import JsonRegistry
from gamr_core import ExperimentConfig, RunSource, RunState


@pytest.mark.asyncio
async def test_task_manager_runs_three_and_queues_the_rest_fifo(tmp_path: Path) -> None:
    registry = JsonRegistry(tmp_path)
    started: list[str] = []
    release = asyncio.Event()

    async def execute(run_id: str) -> str:
        started.append(run_id)
        await release.wait()
        return f"runs/{run_id}/result.json"

    manager = RunTaskManager(registry, execute, max_concurrent_runs=3)
    await manager.start()
    runs = [
        registry.create_run(
            None,
            "datasets/first-plan",
            ExperimentConfig(),
            source=RunSource.SERVICE,
        )
        for _ in range(5)
    ]
    for run in runs:
        await manager.submit(run.id)

    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert started == [run.id for run in runs[:3]]
    assert [run.state for run in runs[3:]] == [RunState.QUEUED, RunState.QUEUED]

    release.set()
    await manager.join()
    assert started == [run.id for run in runs]
    completed = [registry.get_run(run.id) for run in runs]
    assert all(run is not None and run.state is RunState.COMPLETED for run in completed)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_task_manager_interrupts_without_replaying_on_restart(tmp_path: Path) -> None:
    registry = JsonRegistry(tmp_path)
    active = registry.create_run(
        None,
        "datasets/first-plan",
        ExperimentConfig(),
        source=RunSource.SERVICE,
    )
    registry.set_state(active, RunState.PREPARING)
    cli = registry.create_run(
        None,
        "datasets/first-plan",
        ExperimentConfig(),
        source=RunSource.CLI,
    )
    registry.set_state(cli, RunState.PREPARING)
    executed: list[str] = []

    async def execute(run_id: str) -> str:
        executed.append(run_id)
        return "result.json"

    manager = RunTaskManager(JsonRegistry(tmp_path), execute, max_concurrent_runs=3)
    await manager.start()

    interrupted = manager.registry.get_run(active.id)
    cli_run = manager.registry.get_run(cli.id)
    assert interrupted is not None and interrupted.state is RunState.INTERRUPTED
    assert cli_run is not None and cli_run.state is RunState.PREPARING
    assert executed == []
    await manager.shutdown()
