import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from gamr_adapters.benign_config import BenignSettings
from gamr_adapters.benign_worker import BenignWorker
from gamr_core.benign import BenignRun, BenignScenario, Submission


def scenario(workspace: str) -> BenignScenario:
    return BenignScenario(
        title="Test",
        original_input="Hello",
        workspace=workspace,
        participants=[workspace],
        timezone="UTC",
        reference_time=datetime(2026, 9, 21, tzinfo=UTC),
        stimulus="Hello",
    )


@pytest.mark.asyncio
async def test_pending_participant_blocks_only_overlapping_runs(tmp_path: Path) -> None:
    worker = BenignWorker(BenignSettings(root=tmp_path))
    blocked = BenignRun(scenario=scenario("mira"), state="pending")
    worker.store.save(blocked)
    runs = worker.store.enqueue(Submission(scenarios=[scenario("mira"), scenario("sable")]))
    await worker.tick()
    assert runs[0].id not in worker.active
    assert runs[1].id in worker.active
    for task in worker.active.values():
        task.cancel()
    await asyncio.gather(*worker.active.values(), return_exceptions=True)


@pytest.mark.asyncio
async def test_resume_rechecks_state_without_replaying_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = BenignWorker(BenignSettings(root=tmp_path))
    run = BenignRun(
        scenario=scenario("mira"),
        state="pending",
        phase="assessment",
        observations={"stimulus": {}, "verify.calendar": {}},
        checkpoints={
            "stimulus": {"operationId": "original-op"},
            "verify.calendar": {"operationId": "old-read"},
        },
    )
    worker.store.save(run)
    worker.resume(run.id)
    captured: dict[str, Any] = {}

    async def execute(current: BenignRun, runtime: Any) -> None:
        captured.update(current.model_dump())

    monkeypatch.setattr("gamr_adapters.benign_worker.run_scenario", execute)
    await worker.execute(run)
    assert captured["checkpoints"]["stimulus"]["operationId"] == "original-op"
    assert "operationId" not in captured["checkpoints"]["verify.calendar"]
    assert captured["checkpoints"]["verify.calendar"]["generation"] == 1
    assert "stimulus" not in captured["observations"]
