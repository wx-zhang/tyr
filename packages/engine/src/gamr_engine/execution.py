from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from gamr_core import (
    ActivityType,
    EvidenceType,
    ExecutionOutcome,
    ExperimentConfig,
    RunActivity,
    RunResult,
    RunState,
)
from gamr_core.identifiers import new_id

from .collector_verification import DeliveryVerifier
from .content_evidence import ContentEvidenceProvider
from .ports.artifacts import ActivitySink, ArtifactStore
from .ports.models import ModelGateway
from .ports.sandbox import Sandbox
from .ports.targets import TargetGateway
from .reporting import render_markdown
from .runner import ExperimentRunner, LoadedTask, ProgressCallback


@dataclass(frozen=True)
class ExecutionOutput:
    result: RunResult
    result_path: str


class ExperimentExecutionService:
    async def execute(
        self,
        task: LoadedTask,
        configuration: ExperimentConfig,
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
    ) -> ExecutionOutput:
        result = await ExperimentRunner(
            progress=progress,
            activity_sink=activity_sink,
            delivery_verifier=delivery_verifier,
            content_evidence_provider=content_evidence_provider,
            sandbox=sandbox,
            scientist_output_tokens=scientist_output_tokens,
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

    async def resume_scientist(
        self,
        task: LoadedTask,
        configuration: ExperimentConfig,
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
    ) -> ExecutionOutput:
        result = await ExperimentRunner(
            progress=progress,
            activity_sink=activity_sink,
            delivery_verifier=delivery_verifier,
            content_evidence_provider=content_evidence_provider,
            sandbox=sandbox,
            scientist_output_tokens=scientist_output_tokens,
        ).resume_scientist(
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

    @staticmethod
    def _terminal_run_state(outcome: ExecutionOutcome) -> RunState:
        if outcome is ExecutionOutcome.CANCELLED:
            return RunState.CANCELLED
        if outcome is ExecutionOutcome.INTERRUPTED:
            return RunState.INTERRUPTED
        if outcome in {ExecutionOutcome.FAILED, ExecutionOutcome.ERROR}:
            return RunState.FAILED
        return RunState.COMPLETED

    def _emit_terminal_activity(self, activity_sink: ActivitySink, result: RunResult) -> None:
        status = self._terminal_run_state(result.outcome).value
        sequence = activity_sink.latest_sequence(result.run_id) + 1
        occurred_at = result.finished_at or datetime.now(UTC)
        activity_sink.append(
            RunActivity(
                id=new_id(),
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

    def append(self, activity: RunActivity) -> RunActivity:
        for sink in self.sinks:
            sink.append(activity)
        return activity

    def latest_sequence(self, run_id: str) -> int:
        return max((sink.latest_sequence(run_id) for sink in self.sinks), default=0)
