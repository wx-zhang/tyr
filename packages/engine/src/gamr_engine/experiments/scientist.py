from __future__ import annotations

from gamr_core import DiscoveryCandidate, ExperimentPresetConfig, TargetOrigin

from ..ports.artifacts import ArtifactStore
from ..ports.models import ModelGateway
from ..ports.targets import TargetGateway
from ..ports.tracing import TracePort, trace_span
from .activity import RunEvents
from .case_execution import CaseExecutor
from .history import cap_history_records, effective_scientist_history
from .records import LoadedTask, ScenarioExecutionRecord, TargetConversation
from .results import scenario_succeeded
from .scientist_generation import generate_scenario
from .scientist_input import (
    build_prompt_context,
    estimated_tokens,
    prepare_generation_input,
)


class ScientistRunner:
    def __init__(
        self,
        case_executor: CaseExecutor,
        events: RunEvents,
        output_tokens: int,
        trace_port: TracePort | None,
    ) -> None:
        self._case_executor = case_executor
        self._events = events
        self._output_tokens = output_tokens
        self._trace_port = trace_port

    async def run(
        self,
        task: LoadedTask,
        candidate: DiscoveryCandidate,
        config: ExperimentPresetConfig,
        target: TargetGateway,
        model: ModelGateway,
        judge_model: ModelGateway,
        run_id: str,
        artifacts: ArtifactStore | None,
        prior_records: list[ScenarioExecutionRecord],
        *,
        target_origin: TargetOrigin = TargetOrigin.LIVE,
    ) -> tuple[list[ScenarioExecutionRecord], list[str]]:
        records: list[ScenarioExecutionRecord] = []
        errors: list[str] = []
        used_ids = {record.case.scenario_id for record in prior_records}
        context = build_prompt_context(task, candidate, target_origin=target_origin)
        self._events.emit(
            "scientist.started",
            run_id,
            phase="scientist",
            detail=f"{config.scientist_iterations} iteration(s)",
        )
        for index in range(1, config.scientist_iterations + 1):
            with trace_span(
                self._trace_port,
                f"scientist iteration:{index}",
                metadata={"iteration": index, "runId": run_id},
            ):
                effective_records = effective_scientist_history(prior_records + records, artifacts)
                history_records = cap_history_records(
                    effective_records,
                    test_limit=config.history_test_runs,
                    scientist_limit=config.history_scientist_runs,
                )
                generation_input = prepare_generation_input(context, history_records)
                if isinstance(generation_input, str):
                    errors.append(generation_input)
                    self._events.emit(
                        "scientist.failed",
                        run_id,
                        phase="scientist",
                        turn=index,
                        detail=generation_input,
                    )
                    continue
                self._events.emit(
                    "scientist.history_used",
                    run_id,
                    phase="scientist",
                    turn=index,
                    detail=(
                        f"Iteration {index} uses {len(history_records)} prior test(s)"
                        if history_records
                        else f"Iteration {index} has no prior tests"
                    ),
                    related_case_ids=generation_input.history_case_ids,
                    metadata_extra={
                        "historyOrigins": ",".join(generation_input.history_origins) or "none",
                        "estimatedInputTokens": estimated_tokens(generation_input.prompt),
                        "historyTruncated": generation_input.history_truncated,
                        "promptBytes": generation_input.prompt_bytes,
                        "historyBytes": len(generation_input.history.encode("utf-8")),
                    },
                )
                generated = await generate_scenario(
                    task=task,
                    model=model,
                    generation_input=generation_input,
                    iteration=index,
                    used_ids=used_ids,
                    run_id=run_id,
                    artifacts=artifacts,
                    events=self._events,
                    output_tokens=self._output_tokens,
                    trace_port=self._trace_port,
                )
                if generated.error:
                    errors.append(generated.error)
                scenario = generated.scenario
                if scenario is None:
                    continue
                self._events.emit(
                    "scientist.scenario_ready",
                    run_id,
                    phase="scientist",
                    case_id=scenario.metadata.id,
                    turn=index,
                    detail=scenario.metadata.title,
                )
                record, case_error = await self._case_executor.run(
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
                    phase="scientist",
                    target_origin=target_origin,
                )
                records.append(record)
                if case_error:
                    errors.append(case_error)
                elif scenario_succeeded(record.case):
                    break
        self._events.emit(
            "scientist.completed",
            run_id,
            phase="scientist",
            detail=f"{len(records)} scenario(s)",
        )
        return records, errors
