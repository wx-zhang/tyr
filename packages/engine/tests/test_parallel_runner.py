import asyncio

import pytest
from gamr_core import DiscoveryPlan, ExperimentConfig, Scenario, TaskManifest
from gamr_engine.runner import ExperimentRunner, LoadedTask


class ParallelTarget:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self.operations: list[str | None] = []
        self.release = asyncio.Event()

    async def initialize(self) -> dict[str, object]:
        return {"ok": True}

    async def query(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        if "Discover" in prompt:
            return {"operationId": "discovery", "state": "completed", "response": "done"}
        self.operations.append(operation_id)
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await self.release.wait()
        self.active -= 1
        return {
            "operationId": f"case-{idempotency_key}",
            "state": "completed",
            "response": "done",
        }

    async def settle(
        self, result: dict[str, object], *, operation_id: str | None = None
    ) -> dict[str, object]:
        return result


class ParallelModel:
    async def complete(self, prompt: str) -> dict[str, object]:
        if "Discovery plan" in prompt:
            return {
                "content": (
                    '{"kind":"phase_complete","reason":"done",'
                    '"discoveredCandidates":[{"path":"/tmp/file","workspace":"space",'
                    '"agent":"agent","bridgeId":"bridge"}]}'
                )
            }
        if '"role":"assistant"' in prompt:
            return {"content": '{"kind":"phase_complete","reason":"done"}'}
        return {"content": '{"kind":"send","message":"observe"}'}


def parallel_task() -> LoadedTask:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "parallel", "title": "Parallel", "version": "1.0.0"},
            "spec": {
                "discovery": "discovery.json",
                "cases": ["one.json", "two.json", "three.json"],
                "defaults": {"maxTurns": 2, "actionMode": "read_only"},
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
    return LoadedTask(
        manifest,
        scenarios,
        {},
        discovery=DiscoveryPlan(
            prompt="Discover.", outputFields=["path", "workspace", "agent"]
        ),
    )


@pytest.mark.asyncio
async def test_parallel_cases_are_bounded_isolated_and_keep_manifest_order() -> None:
    target = ParallelTarget()
    run = asyncio.create_task(
        ExperimentRunner().run(
            parallel_task(),
            ExperimentConfig(maxConcurrentCases=2),
            target=target,
            model=ParallelModel(),
        )
    )

    for _ in range(100):
        if target.maximum_active == 2:
            break
        await asyncio.sleep(0.001)
    target.release.set()
    result = await run

    assert target.maximum_active == 2
    assert target.operations == [None, None, None]
    assert [case.scenario_id for case in result.cases] == ["one", "two", "three"]
