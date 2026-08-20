import asyncio
from typing import Any, cast

import pytest
from gamr_core import (
    DiscoveryCandidate,
    ExecutionOutcome,
    ExperimentConfig,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
    TaskManifest,
)
from gamr_engine.ports.models import ModelGateway
from gamr_engine.ports.targets import TargetGateway
from gamr_engine.runner import (
    CaseRecord,
    ExperimentRunner,
    LoadedTask,
    PhaseResult,
    TargetConversation,
)


class InitializableTarget:
    async def initialize(self) -> dict[str, object]:
        return {"ok": True}


class CoordinatorRunner(ExperimentRunner):
    def __init__(self) -> None:
        super().__init__()
        self.active = 0
        self.maximum_active = 0
        self.conversations: list[TargetConversation] = []
        self.release = asyncio.Event()

    async def _run_discovery(self, *args: Any, **kwargs: Any) -> PhaseResult:
        return PhaseResult(
            [],
            None,
            None,
            [DiscoveryCandidate(
                path="/home/space/file", workspace="space", agent="agent", bridgeId="bridge"
            )],
        )

    async def _run_case(
        self,
        task: LoadedTask,
        scenario: Scenario,
        candidate: DiscoveryCandidate,
        config: ExperimentConfig,
        target: Any,
        model: Any,
        judge_model: Any,
        run_id: str,
        artifacts: Any,
        conversation: TargetConversation,
        *,
        phase: str = "case",
    ) -> tuple[CaseRecord, None]:
        self.conversations.append(conversation)
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await self.release.wait()
        self.active -= 1
        case = self._case_result(
            scenario,
            outcome=ExecutionOutcome.COMPLETED,
            objective_status=ObjectiveStatus.NOT_ACHIEVED,
            verdict=SecurityVerdict.PROTECTED,
            summary="done",
            turn_ids=[],
        )
        record = CaseRecord(
            scenario,
            scenario.metadata.title,
            "observe",
            ["observe"],
            "",
            case,
            [],
        )
        return record, None


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
    runner = CoordinatorRunner()
    run = asyncio.create_task(
        runner.run(
            parallel_task(),
            ExperimentConfig(maxConcurrentCases=2),
            target=cast(TargetGateway, InitializableTarget()),
            model=cast(ModelGateway, object()),
        )
    )

    for _ in range(100):
        if runner.maximum_active == 2:
            break
        await asyncio.sleep(0.001)
    runner.release.set()
    result = await run

    assert runner.maximum_active == 2
    assert len({id(conversation) for conversation in runner.conversations}) == 3
    assert all(conversation.operation_id is None for conversation in runner.conversations)
    assert [case.scenario_id for case in result.cases] == ["one", "two", "three"]
