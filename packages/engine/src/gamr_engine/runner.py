from __future__ import annotations

from datetime import UTC, datetime

from gamr_core import (
    ExecutionOutcome,
    ExperimentPresetConfig,
    ObjectiveStatus,
    RunResult,
    SecurityVerdict,
)
from gamr_core.identifiers import new_id

from .collector_verification import CollectorVerificationService, DeliveryVerifier
from .content_evidence import ContentEvidenceProvider
from .experiments.activity import RunEvents
from .experiments.artifacts import turn_ids
from .experiments.case_execution import CaseExecutor
from .experiments.conversation import ConversationRunner
from .experiments.discovery import DiscoveryRunner
from .experiments.history_store import load_configured_history, load_prior_records
from .experiments.records import LoadedTask, ProgressCallback, TargetConversation
from .experiments.rendering import select_scenarios
from .experiments.results import case_result, finish_result
from .experiments.run_support import execute_cases, initialize_target
from .experiments.scientist import ScientistRunner
from .experiments.scientist_generation import SCIENTIST_OUTPUT_TOKENS
from .ports.artifacts import ActivitySink, ArtifactStore
from .ports.models import ModelGateway
from .ports.sandbox import Sandbox
from .ports.targets import TargetGateway
from .ports.tracing import TracePort, trace_run


class ExperimentRunner:
    def __init__(
        self,
        progress: ProgressCallback | None = None,
        activity_sink: ActivitySink | None = None,
        delivery_verifier: DeliveryVerifier | None = None,
        content_evidence_provider: ContentEvidenceProvider | None = None,
        sandbox: Sandbox | None = None,
        scientist_output_tokens: int = SCIENTIST_OUTPUT_TOKENS,
        trace_port: TracePort | None = None,
    ) -> None:
        events = RunEvents(progress, activity_sink)
        conversation = ConversationRunner(events)
        collector_verification = CollectorVerificationService(delivery_verifier)
        case_executor = CaseExecutor(
            conversation,
            events,
            collector_verification,
            content_evidence_provider,
            sandbox,
            trace_port,
        )
        self._events = events
        self._discovery = DiscoveryRunner(conversation, events, trace_port)
        self._case_executor = case_executor
        self._scientist = ScientistRunner(
            case_executor,
            events,
            scientist_output_tokens,
            trace_port,
        )
        self._trace_port = trace_port

    async def run(
        self,
        task: LoadedTask,
        config: ExperimentPresetConfig,
        *,
        run_id: str | None = None,
        target: TargetGateway | None = None,
        model: ModelGateway | None = None,
        scientist_model: ModelGateway | None = None,
        judge_model: ModelGateway | None = None,
        artifacts: ArtifactStore | None = None,
        activity_sink: ActivitySink | None = None,
    ) -> RunResult:
        return await self._execute(
            task,
            config,
            run_id=run_id,
            target=target,
            model=model,
            scientist_model=scientist_model,
            judge_model=judge_model,
            artifacts=artifacts,
            activity_sink=activity_sink,
            source_run_id=None,
        )

    async def resume_research(
        self,
        task: LoadedTask,
        config: ExperimentPresetConfig,
        *,
        source_run_id: str,
        run_id: str | None = None,
        target: TargetGateway | None = None,
        model: ModelGateway | None = None,
        scientist_model: ModelGateway | None = None,
        judge_model: ModelGateway | None = None,
        artifacts: ArtifactStore | None = None,
        activity_sink: ActivitySink | None = None,
    ) -> RunResult:
        return await self._execute(
            task,
            config,
            run_id=run_id,
            target=target,
            model=model,
            scientist_model=scientist_model,
            judge_model=judge_model,
            artifacts=artifacts,
            activity_sink=activity_sink,
            source_run_id=source_run_id,
        )

    async def _execute(
        self,
        task: LoadedTask,
        config: ExperimentPresetConfig,
        *,
        run_id: str | None,
        target: TargetGateway | None,
        model: ModelGateway | None,
        scientist_model: ModelGateway | None,
        judge_model: ModelGateway | None,
        artifacts: ArtifactStore | None,
        activity_sink: ActivitySink | None,
        source_run_id: str | None,
    ) -> RunResult:
        identifier = run_id or new_id()
        self._events.begin_run(identifier, activity_sink)
        started_at = datetime.now(UTC)
        if source_run_id is not None:
            if target is None or model is None:
                raise ValueError("target and model providers are required")
            if artifacts is None:
                raise ValueError("resuming the scientist phase requires an artifact store")
            if not config.scientist_iterations:
                raise ValueError("scientist_iterations must be greater than zero to resume")
        session_id = source_run_id or identifier
        metadata: dict[str, object] = {"taskId": task.manifest.metadata.id, "runId": identifier}
        if source_run_id is not None:
            metadata["sourceRunId"] = source_run_id
        with trace_run(
            self._trace_port,
            f"run:{identifier}",
            session_id=session_id,
            trace_id=identifier,
            metadata=metadata,
        ) as run_obs:
            scenarios = [] if source_run_id is not None else select_scenarios(task, config)
            if target is None or model is None:
                raise ValueError("target and model providers are required")
            execution_detail = "scientist-only" if not scenarios else f"{len(scenarios)} case(s)"
            self._events.emit(
                "run.started",
                identifier,
                detail=(
                    f"{task.manifest.metadata.id} · resuming scientist from {source_run_id}"
                    if source_run_id is not None
                    else f"{task.manifest.metadata.id} · {execution_detail}"
                ),
            )
            initialization_error = await initialize_target(target, self._events, identifier)
            if initialization_error is not None:
                failed_results = [
                    case_result(
                        scenario,
                        outcome=ExecutionOutcome.ERROR,
                        objective_status=ObjectiveStatus.NOT_ATTEMPTED,
                        verdict=SecurityVerdict.INCONCLUSIVE,
                        summary=initialization_error,
                        turn_ids=[],
                    )
                    for scenario in scenarios
                ]
                return finish_result(
                    self._trace_port,
                    identifier,
                    started_at,
                    task,
                    config,
                    failed_results,
                    outcome=ExecutionOutcome.ERROR,
                    errors=[initialization_error],
                    observation=run_obs,
                )
            discovery = await self._discovery.run(
                identifier,
                task,
                config,
                target,
                model,
                artifacts,
                TargetConversation(),
            )
            if not discovery.candidates:
                blocked_results = [
                    case_result(
                        scenario,
                        outcome=ExecutionOutcome.BLOCKED,
                        objective_status=ObjectiveStatus.NOT_ATTEMPTED,
                        verdict=SecurityVerdict.NOT_APPLICABLE,
                        summary=discovery.error or "Discovery did not produce a usable target.",
                        turn_ids=turn_ids(discovery.transcript),
                    )
                    for scenario in scenarios
                ]
                return finish_result(
                    self._trace_port,
                    identifier,
                    started_at,
                    task,
                    config,
                    blocked_results,
                    outcome=ExecutionOutcome.BLOCKED,
                    errors=[discovery.error or "discovery failed"],
                    observation=run_obs,
                )
            candidate = discovery.candidates[0]
            if source_run_id is not None:
                assert artifacts is not None
                prior_records = load_prior_records(task, candidate, artifacts, source_run_id)
                case_records, errors = await self._scientist.run(
                    task,
                    candidate,
                    config,
                    target,
                    scientist_model or model,
                    judge_model or scientist_model or model,
                    identifier,
                    artifacts,
                    prior_records,
                    target_origin=discovery.target_origin,
                )
            else:
                configured_history = (
                    load_configured_history(task, candidate, config, artifacts, identifier)
                    if config.scientist_iterations
                    else []
                )
                case_records, errors = await execute_cases(
                    self._case_executor,
                    self._events,
                    task,
                    scenarios,
                    candidate,
                    config,
                    target,
                    model,
                    judge_model or model,
                    identifier,
                    artifacts,
                    target_origin=discovery.target_origin,
                )
                if config.scientist_iterations:
                    scientist_records, scientist_errors = await self._scientist.run(
                        task,
                        candidate,
                        config,
                        target,
                        scientist_model or model,
                        judge_model or scientist_model or model,
                        identifier,
                        artifacts,
                        configured_history + case_records,
                        target_origin=discovery.target_origin,
                    )
                    case_records.extend(scientist_records)
                    errors.extend(scientist_errors)
            return finish_result(
                self._trace_port,
                identifier,
                started_at,
                task,
                config,
                [record.case for record in case_records],
                errors=errors,
                observation=run_obs,
            )
