from __future__ import annotations

from typing import Any

from gamr_core import SandboxOperationEvent, Scenario

from ..collector_verification import CollectorVerificationBatch
from ..content_evidence import ContentEvidenceProvider
from ..judge_runtime import build_judge_runtime
from ..judges.contracts import JudgeRequest, JudgeResult
from ..judges.registry import get_judge_pipeline
from ..ports.artifacts import ArtifactStore
from ..ports.models import ModelGateway
from ..ports.sandbox import Sandbox
from ..ports.tracing import TracePort, trace_span
from .activity import RunEvents
from .records import LoadedTask, PhaseResult, RenderedScenario


async def assess_case(
    task: LoadedTask,
    scenario: Scenario,
    rendered: RenderedScenario,
    result: PhaseResult,
    verification: CollectorVerificationBatch,
    turn_ids: list[str],
    *,
    judge_model: ModelGateway,
    content_evidence_provider: ContentEvidenceProvider | None,
    sandbox: Sandbox | None,
    artifacts: ArtifactStore | None,
    events: RunEvents,
    trace_port: TracePort | None,
    run_id: str,
    phase: str,
) -> JudgeResult:
    pipeline = get_judge_pipeline(task.manifest.spec.judge.pipeline)
    judge_request = JudgeRequest(
        scenario=scenario,
        title=rendered.title,
        objective=rendered.objective,
        steps=rendered.steps,
        success_criteria=rendered.success,
        expected_control=rendered.expected_control,
        transcript=result.transcript,
        turn_ids=turn_ids,
        execution_error=result.error,
        verifications=verification.items,
        evaluation_plan=task.evaluation,
        assessment_reference=task.assessment_reference,
        phase=phase,
    )

    def activity_sink(name: str, payload: dict[str, Any]) -> None:
        events.emit(
            name,
            run_id,
            phase=payload.get("phase"),
            case_id=payload.get("caseId"),
            detail=payload.get("detail"),
            fields=payload.get("fields"),
            metadata_extra=payload.get("metadata"),
            evidence_refs=payload.get("evidenceRefs", ()),
            operation_id=(
                payload.get("operationId")
                if isinstance(payload.get("operationId"), str)
                else None
            ),
            sandbox_event=(
                SandboxOperationEvent.model_validate(payload["sandboxEvent"])
                if isinstance(payload.get("sandboxEvent"), dict)
                else payload.get("sandboxEvent")
                if isinstance(payload.get("sandboxEvent"), SandboxOperationEvent)
                else None
            ),
        )

    judge_runtime = build_judge_runtime(
        judge_model=judge_model,
        content_evidence_provider=content_evidence_provider,
        sandbox=sandbox,
        artifacts=artifacts,
        activity_sink=activity_sink,
        run_id=run_id,
        case_id=scenario.metadata.id,
    )
    with trace_span(
        trace_port,
        "assessment",
        metadata={"caseId": scenario.metadata.id, "runId": run_id},
    ):
        return await pipeline.run(judge_request, judge_runtime)
