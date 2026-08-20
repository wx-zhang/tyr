from datetime import UTC, datetime
from typing import cast

import pytest
from gamr_core import (
    ActivityType,
    ExecutionOutcome,
    ExperimentConfig,
    RunActivity,
    RunState,
    Scenario,
    TaskManifest,
)
from gamr_engine.execution import ExperimentExecutionService
from gamr_engine.ports.artifacts import ArtifactStore
from gamr_engine.runner import LoadedTask


class _FakeModel:
    async def complete(self, prompt: str) -> dict[str, object]:
        return {"content": '{"kind":"phase_complete","reason":"blocked"}'}


class _FakeTarget:
    async def initialize(self) -> dict[str, object]:
        return {"ok": True}

    async def list_tools(self) -> list[dict[str, object]]:
        return []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object],
        *,
        timeout: float = 60,
    ) -> dict[str, object]:
        return {"state": "completed"}

    async def operation_status(
        self, operation_id: str, *, wait_seconds: int = 0
    ) -> dict[str, object]:
        return {"operationId": operation_id, "state": "completed"}

    async def query(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        return {"operationId": operation_id or "op-1", "state": "completed", "response": "done"}

    async def request(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        return await self.query(prompt, operation_id=operation_id, idempotency_key=idempotency_key)

    async def settle(
        self, result: dict[str, object], *, operation_id: str | None = None
    ) -> dict[str, object]:
        return result


class _ArtifactStore:
    def __init__(self) -> None:
        self.results: list[str] = []
        self.reports: list[str] = []

    def write_result(
        self,
        run_id: str,
        result: object,
        task_snapshot: dict[str, object] | None = None,
    ) -> str:
        self.results.append(run_id)
        return f"{run_id}/result.json"

    def write_report(self, run_id: str, report: str) -> str:
        self.reports.append(run_id)
        return f"{run_id}/report.md"


class _ActivityCollector:
    def __init__(self) -> None:
        self.items: list[RunActivity] = []

    def append(self, item: RunActivity) -> RunActivity:
        self.items.append(item)
        return item

    def latest_sequence(self, run_id: str) -> int:
        matching = [item.sequence for item in self.items if item.run_id == run_id]
        return max(matching, default=0)


@pytest.mark.asyncio
async def test_execution_emits_terminal_run_state_after_result() -> None:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "demo", "title": "Demo", "version": "1.0.0"},
            "spec": {
                "cases": ["one.json"],
                "defaults": {"maxTurns": 1, "actionMode": "read_only"},
            },
        }
    )
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "one", "title": "One"},
            "spec": {
                "objective": "observe",
                "steps": ["observe"],
                "expectedControl": "deny",
                "evidenceRequirements": ["response"],
            },
        }
    )
    artifacts = _ArtifactStore()
    activities = _ActivityCollector()

    output = await ExperimentExecutionService().execute(
        LoadedTask(manifest, [scenario], {}),
        ExperimentConfig(),
        target=_FakeTarget(),
        model=_FakeModel(),
        artifacts=cast(ArtifactStore, artifacts),
        run_id="run-terminal",
        activity_sink=activities,
    )

    assert output.result.outcome is ExecutionOutcome.BLOCKED
    assert artifacts.results == ["run-terminal"]
    terminal = [
        item
        for item in activities.items
        if item.activity_type is ActivityType.RUN_STATE and item.status == RunState.COMPLETED.value
    ]
    assert terminal
    assert terminal[-1].sequence == max(item.sequence for item in activities.items)
    assert terminal[-1].occurred_at.replace(tzinfo=UTC) <= datetime.now(UTC)
