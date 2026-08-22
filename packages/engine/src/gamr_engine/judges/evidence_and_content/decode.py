from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gamr_core import (
    AssessmentStatus,
    CheckedContentFile,
    ContentOverlapResult,
    ContentOverlapStatus,
)
from gamr_engine.content_source import VerifiedContentSnapshot
from gamr_engine.decoder.agent import DecoderAgent
from gamr_engine.ports.models import ChatModelGateway

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

    agent = DecoderAgent(
        model=chat_model,
        sandbox=sandbox,
        snapshots=snapshots,
        task_context=request.scenario.metadata.title,
        case_fields=case_fields,
        evaluation_criteria=eval_criteria,
        transcript=request.transcript,
    )

    loop_result = await agent.run()

    if loop_result.action == "failed":
        failure_code_str = (
            loop_result.provenance.failure_code.value
            if loop_result.provenance.failure_code
            else "decoder_failed"
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

    return {
        "decoder_action": loop_result.action,
        "decoder_provenance": loop_result.provenance,
        "derived_snapshots": loop_result.derived_snapshots,
    }
