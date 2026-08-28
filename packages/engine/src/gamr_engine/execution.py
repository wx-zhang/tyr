from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from gamr_core import (
    ActivityType,
    CompletionOutcome,
    EvidenceType,
    ExperimentActivity,
    ExperimentPresetConfig,
    ExperimentResult,
    ExperimentState,
)

from .collector_verification import DeliveryVerifier
from .content_evidence import ContentEvidenceProvider
from .ports.artifacts import ActivitySink, ArtifactStore
from .ports.models import ModelGateway
from .ports.sandbox import Sandbox
from .ports.targets import TargetGateway
from .ports.tracing import TracePort
from .reporting import render_markdown
from .runner import ExperimentRunner, LoadedTask, ProgressCallback


@dataclass(frozen=True)
class ExecutionOutput:
    result: ExperimentResult
    result_path: str


class ExperimentExecutionService:
    async def execute(
        self,
        task: LoadedTask,
        configuration: ExperimentPresetConfig,
        *,
        target: TargetGateway,
        model: ModelGateway,
        scientist_model: ModelGateway | None = None,
        judge_model: ModelGateway | None = None,
        artifacts: ArtifactStore,
        run_id: str | None = None,
        activity_sink: ActivitySink | None = None,
        progress: ProgressCallback | None = None,
        delivery_verifier: DeliveryVerifier | None = None,
        content_evidence_provider: ContentEvidenceProvider | None = None,
        sandbox: Sandbox | None = None,
        scientist_output_tokens: int = 8192,
        trace_port: TracePort | None = None,
    ) -> ExecutionOutput:
        result = await ExperimentRunner(
            progress=progress,
            activity_sink=activity_sink,
            delivery_verifier=delivery_verifier,
            content_evidence_provider=content_evidence_provider,
            sandbox=sandbox,
            scientist_output_tokens=scientist_output_tokens,
            trace_port=trace_port,
        ).run(
            task,
            configuration,
            run_id=run_id,
            target=target,
            model=model,
            scientist_model=scientist_model,
            judge_model=judge_model,
            artifacts=artifacts,
        )
        result_path = artifacts.write_result(
            result.run_id,
            result,
            task_snapshot=task.raw,
        )
        artifacts.write_report(result.run_id, render_markdown(result))
        if activity_sink is not None:
            self._emit_terminal_activity(activity_sink, result)
        return ExecutionOutput(result, result_path)

    async def resume_research(
        self,
        task: LoadedTask,
        configuration: ExperimentPresetConfig,
        *,
        source_run_id: str,
        target: TargetGateway,
        model: ModelGateway,
        scientist_model: ModelGateway | None = None,
        judge_model: ModelGateway | None = None,
        artifacts: ArtifactStore,
        run_id: str | None = None,
        activity_sink: ActivitySink | None = None,
        progress: ProgressCallback | None = None,
        delivery_verifier: DeliveryVerifier | None = None,
        content_evidence_provider: ContentEvidenceProvider | None = None,
        sandbox: Sandbox | None = None,
        scientist_output_tokens: int = 8192,
        trace_port: TracePort | None = None,
    ) -> ExecutionOutput:
        result = await ExperimentRunner(
            progress=progress,
            activity_sink=activity_sink,
            delivery_verifier=delivery_verifier,
            content_evidence_provider=content_evidence_provider,
            sandbox=sandbox,
            scientist_output_tokens=scientist_output_tokens,
            trace_port=trace_port,
        ).resume_research(
            task,
            configuration,
            source_run_id=source_run_id,
            run_id=run_id,
            target=target,
            model=model,
            scientist_model=scientist_model,
            judge_model=judge_model,
            artifacts=artifacts,
        )
        result_path = artifacts.write_result(
            result.run_id,
            result,
            task_snapshot=task.raw,
        )
        artifacts.write_report(result.run_id, render_markdown(result))
        if activity_sink is not None:
            self._emit_terminal_activity(activity_sink, result)
        return ExecutionOutput(result, result_path)

    resume_scientist = resume_research

    @staticmethod
    def _terminal_experiment_state(outcome: CompletionOutcome) -> ExperimentState:
        if outcome is CompletionOutcome.CANCELLED:
            return ExperimentState.CANCELLED
        if outcome is CompletionOutcome.INTERRUPTED:
            return ExperimentState.INTERRUPTED
        if outcome in {CompletionOutcome.FAILED, CompletionOutcome.ERROR}:
            return ExperimentState.FAILED
        return ExperimentState.COMPLETED

    def _emit_terminal_activity(
        self, activity_sink: ActivitySink, result: ExperimentResult
    ) -> None:
        status = self._terminal_experiment_state(result.outcome).value
        sequence = activity_sink.latest_sequence(result.run_id) + 1
        occurred_at = result.finished_at or datetime.now(UTC)
        activity_sink.append(
            ExperimentActivity(
                runId=result.run_id,
                sequence=sequence,
                occurredAt=occurred_at,
                activityType=ActivityType.RUN_STATE,
                status=status,
                evidenceType=EvidenceType.EVENT,
                summary=f"Run state is {status}",
                metadata={
                    "eventType": f"run.{status}",
                    "outcome": result.outcome.value,
                },
            )
        )


class FanoutActivitySink:
    def __init__(self, *sinks: ActivitySink) -> None:
        self.sinks = sinks

    def append(self, activity: ExperimentActivity) -> ExperimentActivity:
        for sink in self.sinks:
            sink.append(activity)
        return activity

    def latest_sequence(self, run_id: str) -> int:
        return max((sink.latest_sequence(run_id) for sink in self.sinks), default=0)
