from __future__ import annotations

import asyncio

from gamr_core import DiscoveryCandidate, ExperimentPresetConfig, Scenario, TargetOrigin

from ..ports.artifacts import ArtifactStore
from ..ports.models import ModelGateway
from ..ports.targets import TargetGateway
from .activity import RunEvents
from .case_execution import CaseExecutor
from .records import LoadedTask, ScenarioExecutionRecord, TargetConversation


async def initialize_target(
    target: TargetGateway,
    events: RunEvents,
    run_id: str,
) -> str | None:
    events.emit("tyr.connecting", run_id)
    try:
        await target.initialize()
    except Exception as exc:
        events.emit("tyr.failed", run_id, detail=type(exc).__name__)
        return f"Tyr initialization failed: {type(exc).__name__}: {exc}"
    events.emit("tyr.connected", run_id)
    return None


async def execute_cases(
    case_executor: CaseExecutor,
    events: RunEvents,
    task: LoadedTask,
    scenarios: list[Scenario],
    candidate: DiscoveryCandidate,
    config: ExperimentPresetConfig,
    target: TargetGateway,
    model: ModelGateway,
    judge_model: ModelGateway,
    run_id: str,
    artifacts: ArtifactStore | None,
    *,
    target_origin: TargetOrigin,
) -> tuple[list[ScenarioExecutionRecord], list[str]]:
    semaphore = asyncio.Semaphore(config.max_concurrent_cases)
    records: list[ScenarioExecutionRecord | None] = [None] * len(scenarios)
    case_errors: list[str | None] = [None] * len(scenarios)

    async def execute_case(index: int, scenario: Scenario) -> None:
        async with semaphore:
            record, case_error = await case_executor.run(
                task,
                scenario,
                candidate,
                config,
                target,
                model,
                judge_model,
                run_id,
                artifacts,
                TargetConversation(),
                target_origin=target_origin,
            )
            records[index] = record
            case_errors[index] = case_error

    async with asyncio.TaskGroup() as task_group:
        for index, scenario in enumerate(scenarios):
            if index >= config.max_concurrent_cases:
                events.emit(
                    "case.queued",
                    run_id,
                    phase="case",
                    case_id=scenario.metadata.id,
                    detail="Waiting for an execution slot",
                )
            task_group.create_task(execute_case(index, scenario))
    return (
        [record for record in records if record is not None],
        [error for error in case_errors if error is not None],
    )
