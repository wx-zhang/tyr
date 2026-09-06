import asyncio
from typing import cast

import pytest
from gamr_core import ExperimentConfig, Scenario, TaskManifest
from gamr_engine.experiments.records import LoadedTask
from gamr_engine.ports.models import ModelGateway
from gamr_engine.ports.targets import TargetGateway
from gamr_engine.runner import ExperimentRunner


class ParallelTarget:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self.query_count = 0
        self.started_conversations: list[str] = []
        self.completed_conversations: list[str] = []
        self.second_started = asyncio.Event()
        self.second_finished = asyncio.Event()
        self.first_finished = asyncio.Event()

    async def initialize(self) -> dict[str, object]:
        return {"ok": True}

    async def start_conversation(self, *, idempotency_key: str) -> dict[str, object]:
        conversation_id = f"conversation-{len(self.started_conversations) + 1}"
        self.started_conversations.append(conversation_id)
        return {"conversationId": conversation_id}

    async def query(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        conversation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        self.query_count += 1
        request_number = self.query_count
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            if request_number == 1:
                await self.second_started.wait()
                await self.second_finished.wait()
            elif request_number == 2:
                self.second_started.set()
            else:
                await self.first_finished.wait()
            self.completed_conversations.append(cast(str, conversation_id))
            if request_number == 2:
                self.second_finished.set()
            if request_number == 1:
                self.first_finished.set()
            return {
                "operationId": operation_id or f"operation-{request_number}",
                "state": "completed",
                "response": "done",
            }
        finally:
            self.active -= 1

    async def settle(
        self, result: dict[str, object], *, operation_id: str | None = None
    ) -> dict[str, object]:
        return result


class ParallelModel:
    async def complete(self, prompt: str) -> dict[str, object]:
        if "[user] done" in prompt:
            return {"content": '{"kind":"phase_complete","reason":"done"}'}
        return {"content": '{"kind":"send","message":"observe"}'}


def parallel_task() -> LoadedTask:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "parallel", "title": "Parallel", "version": "1.0.0"},
            "spec": {
                "cases": ["one.json", "two.json", "three.json"],
                "defaults": {
                    "maxTurns": 2,
                    "actionMode": "read_only",
                    "defaultCaseIds": ["one", "two", "three"],
                },
            },
        }
    )
    scenarios = [
        Scenario.model_validate(
            {
                "metadata": {"id": case_id, "title": case_id},
                "spec": {
                    "objective": "observe",
                    "steps": ["observe"],
                    "expectedControl": "deny",
                    "evidenceRequirements": ["response"],
                },
            }
        )
        for case_id in ("one", "two", "three")
    ]
    return LoadedTask(manifest, scenarios, {})


@pytest.mark.asyncio
async def test_parallel_cases_are_bounded_isolated_and_keep_manifest_order() -> None:
    target = ParallelTarget()
    result = await ExperimentRunner().run(
        parallel_task(),
        ExperimentConfig(
            maxConcurrentCases=2,
            discoveryInput={
                "schemaVersion": "1.0",
                "kind": "discovery-input",
                "taskId": "parallel",
                "candidate": {
                    "path": "/home/space/file",
                    "workspace": "space",
                    "agent": "agent",
                    "bridgeId": "bridge",
                },
            },
        ),
        target=cast(TargetGateway, target),
        model=cast(ModelGateway, ParallelModel()),
    )

    assert target.maximum_active == 2
    assert target.started_conversations == ["conversation-1", "conversation-2", "conversation-3"]
    assert target.completed_conversations == ["conversation-2", "conversation-1", "conversation-3"]
    assert len(set(target.started_conversations)) == 3
    assert [case.scenario_id for case in result.cases] == ["one", "two", "three"]
