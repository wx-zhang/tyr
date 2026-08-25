from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gamr_engine.collector_verification import CollectorFile
from gamr_engine.content_assessment import ContentAssessmentService
from gamr_engine.content_pipeline import ContentAssessmentPipeline
from gamr_engine.content_prepare import (
    DerivedContentSnapshot,
    prepare_content_evidence,
    prepare_derived_content_evidence,
)
from gamr_engine.content_source import VerifiedContentSnapshot

from ..contracts import JudgeRequest, JudgeRuntime

if TYPE_CHECKING:
    from .pipeline import PipelineState

_UNSAFE_ID_CHAR = re.compile(r"[^A-Za-z0-9_.-]+")


async def compare_reference_content(state: PipelineState) -> dict[str, Any]:
    request: JudgeRequest = state["request"]
    runtime: JudgeRuntime = state["runtime"]
    reference = request.assessment_reference

    if reference is None or request.scenario.spec.collector_evidence != "file":
        return {"content_overlap": None}

    if state.get("content_overlap") is not None:
        content_overlap = state["content_overlap"]
        if runtime.artifacts is not None and content_overlap is not None:
            safe_id = _UNSAFE_ID_CHAR.sub("-", runtime.case_id)[:128] or "case"
            runtime.artifacts.write_json(
                f"runs/{runtime.run_id}/content-assessments/{safe_id}.json",
                {
                    "status": content_overlap.assessment_status.value,
                    "failure": content_overlap.failure,
                    "attempts": [],
                },
            )
        return {"content_overlap": content_overlap}

    collector_files: list[CollectorFile] = state.get("collector_files", [])
    verified_snapshots: list[VerifiedContentSnapshot] = state.get("verified_snapshots", [])
    decoder_action = state.get("decoder_action")
    decoder_prov = state.get("decoder_provenance")
    derived_snapshots: list[DerivedContentSnapshot] = state.get("derived_snapshots", [])

    if decoder_action == "decoded":
        source_map = {
            s.snapshot_id: next((f for f in collector_files if f.file_id == s.source_file_id), None)
            for s in verified_snapshots
        }
        valid_source_map = {k: v for k, v in source_map.items() if v is not None}
        batch = prepare_derived_content_evidence(
            collector_files, valid_source_map, derived_snapshots
        )
    elif decoder_action == "direct":
        batch = prepare_content_evidence(collector_files, verified_snapshots)
    else:
        pipeline = ContentAssessmentPipeline(runtime.content_evidence_provider)
        outcome = await pipeline.assess(reference, request.verifications, runtime.judge_model)
        if runtime.artifacts is not None:
            safe_id = _UNSAFE_ID_CHAR.sub("-", runtime.case_id)[:128] or "case"
            runtime.artifacts.write_json(
                f"runs/{runtime.run_id}/content-assessments/{safe_id}.json",
                outcome.diagnostic,
            )
        return {"content_overlap": outcome.result}

    service = ContentAssessmentService()
    outcome = await service.assess(
        reference=reference,
        evidence=batch,
        model=runtime.judge_model,
    )

    result = outcome.result
    if decoder_prov is not None and result is not None:
        result = result.model_copy(update={"decoding": decoder_prov})

    if runtime.artifacts is not None:
        safe_id = _UNSAFE_ID_CHAR.sub("-", runtime.case_id)[:128] or "case"
        runtime.artifacts.write_json(
            f"runs/{runtime.run_id}/content-assessments/{safe_id}.json",
            outcome.diagnostic,
        )

    return {"content_overlap": result}
