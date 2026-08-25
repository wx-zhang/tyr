from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from gamr_core import (
    AssessmentStatus,
    CheckedContentFile,
    ContentOverlapResult,
    ContentOverlapStatus,
    SandboxOperationEvent,
)
from gamr_engine.content_source import VerifiedContentSnapshot
from gamr_engine.decoder.agent import DecoderAgent
from gamr_engine.ports.models import ChatModelGateway
from gamr_engine.sandbox_preview import ObservedSandbox

from ..contracts import JudgeRequest, JudgeRuntime

if TYPE_CHECKING:
    from .pipeline import PipelineState


async def decode_trajectory_content(state: PipelineState) -> dict[str, Any]:
    applicable = state.get("applicable", False)
    if not applicable:
        return {
            "decoder_action": None,
            "decoder_provenance": None,
            "derived_snapshots": [],
        }

    if state.get("preparation_error") is not None:
        return {
            "decoder_action": None,
            "decoder_provenance": None,
            "derived_snapshots": [],
        }

    request: JudgeRequest = state["request"]
    runtime: JudgeRuntime = state["runtime"]
    reference = request.assessment_reference
    snapshots: list[VerifiedContentSnapshot] = state.get("verified_snapshots", [])
    files = state.get("collector_files", [])

    checked = [
        CheckedContentFile(
            fileId=f.file_id,
            filename=f.filename,
            contentType=f.content_type,
            size=f.size,
            sha256=f.sha256,
        )
        for f in files
    ]

    judge_model = runtime.judge_model
    sandbox = runtime.sandbox

    if not callable(getattr(judge_model, "chat", None)):
        return {
            "decoder_action": "failed",
            "decoder_provenance": None,
            "derived_snapshots": [],
            "content_overlap": ContentOverlapResult(
                status=ContentOverlapStatus.INCONCLUSIVE,
                assessmentStatus=AssessmentStatus.FAILED,
                failure="preparation_failure",
                referenceSha256=f"sha256:{reference.sha256}" if reference else None,
                checkedFiles=checked,
            ),
        }

    if sandbox is None:
        return {
            "decoder_action": "failed",
            "decoder_provenance": None,
            "derived_snapshots": [],
            "content_overlap": ContentOverlapResult(
                status=ContentOverlapStatus.INCONCLUSIVE,
                assessmentStatus=AssessmentStatus.FAILED,
                failure="sandbox_unavailable",
                referenceSha256=f"sha256:{reference.sha256}" if reference else None,
                checkedFiles=checked,
            ),
        }

    chat_model: ChatModelGateway = judge_model  # type: ignore[assignment]
    sandbox_operation_id: str | None = None

    def emit_decoder_activity(name: str, payload: dict[str, object]) -> None:
        if runtime.activity_sink is None:
            return
        runtime.activity_sink(
            name,
            {
                **payload,
                "phase": "case",
                "caseId": runtime.case_id,
                "operationId": sandbox_operation_id,
                "evidenceRefs": ["result.json#contentOverlap.decoding"],
            },
        )

    def emit_sandbox_event(event: object) -> None:
        if runtime.activity_sink is None:
            return
        sandbox_event = (
            event.model_dump(by_alias=True, mode="json")
            if isinstance(event, SandboxOperationEvent)
            else event
        )
        runtime.activity_sink(
            "sandbox.operation",
            {
                "phase": "case",
                "caseId": runtime.case_id,
                "detail": f"Sandbox {getattr(event, 'state', 'updated')}",
                "operationId": getattr(event, "operation_id", None),
                "sandboxEvent": sandbox_event,
                "evidenceRefs": ["result.json#contentOverlap.decoding"],
            },
        )

    case_fields: dict[str, object] = {
        "title": request.title,
        "objective": request.objective,
        "steps": request.steps,
        "success_criteria": request.success_criteria,
        "expected_control": request.expected_control,
    }

    eval_criteria = ""
    if request.evaluation_plan is not None:
        eval_criteria = request.evaluation_plan.prompt

    observed_sandbox = ObservedSandbox(
        sandbox,
        owner="evidence-and-content",
        event_sink=emit_sandbox_event,
        sensitive_values=[snapshot.content for snapshot in snapshots],
    )
    sandbox_operation_id = observed_sandbox.operation_id
    agent = DecoderAgent(
        model=chat_model,
        sandbox=observed_sandbox,
        snapshots=snapshots,
        task_context=request.scenario.metadata.title,
        case_fields=case_fields,
        evaluation_criteria=eval_criteria,
        transcript=request.transcript,
        activity_sink=emit_decoder_activity,
    )

    try:
        loop_result = await agent.run()
    except asyncio.CancelledError:
        if observed_sandbox.has_events:
            observed_sandbox.cancel()
        emit_decoder_activity(
            "decoder.failed",
            {"detail": "Decoder cancelled", "metadata": {"failureStage": "cleanup"}},
        )
        raise

    if observed_sandbox.has_events:
        if loop_result.action == "failed":
            observed_sandbox.fail()
        else:
            observed_sandbox.complete()

    if loop_result.action == "failed":
        failure_code_str = (
            loop_result.provenance.failure_code.value
            if loop_result.provenance.failure_code
            else "decoder_failed"
        )
        emit_decoder_activity(
            "decoder.failed",
            {
                "detail": f"Decoder failed: {failure_code_str}",
                "metadata": {"failureCode": failure_code_str},
            },
        )
        return {
            "decoder_action": "failed",
            "decoder_provenance": loop_result.provenance,
            "derived_snapshots": [],
            "content_overlap": ContentOverlapResult(
                status=ContentOverlapStatus.INCONCLUSIVE,
                assessmentStatus=AssessmentStatus.FAILED,
                failure=failure_code_str,
                referenceSha256=f"sha256:{reference.sha256}" if reference else None,
                checkedFiles=checked,
                decoding=loop_result.provenance,
            ),
        }

    emit_decoder_activity(
        "decoder.completed",
        {
            "detail": f"Decoder completed: {loop_result.action}",
            "metadata": {
                "decoderAction": loop_result.action,
                "attemptCount": loop_result.provenance.attempt_count,
            },
        },
    )
    return {
        "decoder_action": loop_result.action,
        "decoder_provenance": loop_result.provenance,
        "derived_snapshots": loop_result.derived_snapshots,
    }
