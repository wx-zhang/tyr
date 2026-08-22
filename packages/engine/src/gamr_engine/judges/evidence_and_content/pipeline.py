from __future__ import annotations

import re
from typing import Any, TypedDict

from gamr_core import (
    AssessmentStatus,
    CaseAssessment,
    ContentOverlapResult,
    JudgePipelineId,
    ObjectiveStatus,
    SecurityVerdict,
)
from gamr_engine.assessment import (
    AssessmentOutcome,
    AssessmentService,
    build_assessment_prompt,
    failed_assessment_summary,
)
from gamr_engine.collector_verification import collector_assessment_context
from gamr_engine.content_pipeline import ContentAssessmentPipeline, content_assessment_context
from langgraph.graph import END, START, StateGraph

from ..contracts import JudgeRequest, JudgeResult, JudgeRuntime

_UNSAFE_ID_CHAR = re.compile(r"[^A-Za-z0-9_.-]+")


class PipelineState(TypedDict, total=False):
    request: JudgeRequest
    runtime: JudgeRuntime
    content_overlap: ContentOverlapResult | None
    assessment_outcome: AssessmentOutcome | None
    result: JudgeResult


def _turn_ids(transcript: list[dict[str, Any]]) -> list[str]:
    turn_ids: list[str] = []
    for item in transcript:
        for key in ("turnId", "turn_id", "id"):
            value = item.get(key)
            if isinstance(value, str) and value:
                turn_ids.append(value)
                break
    return turn_ids


async def compare_reference_content(state: PipelineState) -> dict[str, Any]:
    request = state["request"]
    runtime = state["runtime"]
    reference = request.assessment_reference
    if reference is None or request.scenario.spec.collector_evidence != "file":
        return {"content_overlap": None}

    pipeline = ContentAssessmentPipeline(runtime.content_evidence_provider)
    outcome = await pipeline.assess(reference, request.verifications, runtime.judge_model)
    if runtime.artifacts is not None:
        safe_id = _UNSAFE_ID_CHAR.sub("-", runtime.case_id)[:128] or "case"
        runtime.artifacts.write_json(
            f"runs/{runtime.run_id}/content-assessments/{safe_id}.json",
            outcome.diagnostic,
        )
    return {"content_overlap": outcome.result}


def route_after_content(state: PipelineState) -> str:
    request = state["request"]
    content_overlap = state.get("content_overlap")
    verified_content = bool(content_overlap and content_overlap.checked_files)
    if request.execution_error and not verified_content:
        return "preserve_execution_failure"
    return "assess_evidence"


async def preserve_execution_failure(state: PipelineState) -> dict[str, Any]:
    request = state["request"]
    result = JudgeResult(
        objective_status=(
            ObjectiveStatus.PARTIAL if request.turn_ids else ObjectiveStatus.NOT_ATTEMPTED
        ),
        verdict=SecurityVerdict.INCONCLUSIVE,
        summary=request.execution_error or "Execution failed",
        evidence_turn_ids=request.turn_ids,
        assessment_status=AssessmentStatus.SKIPPED,
        assessment_failure=None,
        reason_codes=[],
        missing_evidence=[],
        content_overlap=state.get("content_overlap"),
    )
    return {"result": result}


async def assess_evidence(state: PipelineState) -> dict[str, Any]:
    request = state["request"]
    runtime = state["runtime"]
    if runtime.activity_sink is not None:
        runtime.activity_sink(
            "assessment.started",
            {
                "phase": "assessment",
                "caseId": runtime.case_id,
            },
        )
    if request.evaluation_plan is None:
        outcome = AssessmentOutcome(
            None,
            AssessmentStatus.SKIPPED,
            "evaluation_not_configured",
            {"status": AssessmentStatus.SKIPPED.value, "attempts": []},
        )
        return {"assessment_outcome": outcome}

    prompt = build_assessment_prompt(
        evaluation_prompt=request.evaluation_plan.prompt,
        title=request.title,
        expected_control=request.expected_control or "",
        success_criteria=request.success_criteria or "not supplied",
        transcript=request.transcript,
        verifications=request.verifications,
        content_overlap=state.get("content_overlap"),
    )
    service = AssessmentService()
    outcome = await service.assess(
        model=runtime.judge_model,
        prompt=prompt,
        valid_turn_ids=set(request.turn_ids),
        content_overlap=state.get("content_overlap"),
    )
    if runtime.artifacts is not None:
        safe_id = _UNSAFE_ID_CHAR.sub("-", runtime.case_id)[:128] or "case"
        runtime.artifacts.write_json(
            f"runs/{runtime.run_id}/judge-assessments/{safe_id}.json",
            outcome.diagnostic,
        )
    return {"assessment_outcome": outcome}


async def finalize_judgment(state: PipelineState) -> dict[str, Any]:
    request = state["request"]
    runtime = state["runtime"]
    content_overlap = state.get("content_overlap")
    outcome = state["assessment_outcome"]
    assessment = outcome.assessment if outcome else None

    if assessment is None:
        failure = outcome.failure if outcome else None
        assessment = CaseAssessment(
            objectiveStatus=ObjectiveStatus.UNKNOWN,
            verdict=SecurityVerdict.INCONCLUSIVE,
            summary=failed_assessment_summary(failure, content_overlap),
            evidenceTurnIds=request.turn_ids,
            missingEvidence=["A valid structured judge assessment is unavailable."],
        )

    collector_reasons, collector_missing = collector_assessment_context(request.verifications)
    content_reasons, content_missing = content_assessment_context(content_overlap)

    assessment = assessment.model_copy(
        update={
            "reason_codes": list(
                dict.fromkeys([*assessment.reason_codes, *collector_reasons, *content_reasons])
            ),
            "missing_evidence": list(
                dict.fromkeys([*assessment.missing_evidence, *collector_missing, *content_missing])
            ),
        }
    )

    if runtime.activity_sink is not None and outcome is not None:
        detail = (
            f"{assessment.verdict.value} · {assessment.objective_status.value} · "
            f"{assessment.summary}"
        )
        runtime.activity_sink(
            "assessment.completed",
            {
                "phase": "assessment",
                "caseId": runtime.case_id,
                "detail": detail,
                "fields": (
                    ("verdict", assessment.verdict.value),
                    ("objective", assessment.objective_status.value),
                    ("judgeStatus", outcome.status.value),
                    ("summary", assessment.summary),
                ),
            },
        )

    result = JudgeResult(
        objective_status=assessment.objective_status,
        verdict=assessment.verdict,
        summary=assessment.summary,
        evidence_turn_ids=assessment.evidence_turn_ids,
        assessment_status=outcome.status if outcome else AssessmentStatus.SKIPPED,
        assessment_failure=outcome.failure if outcome else None,
        reason_codes=assessment.reason_codes,
        missing_evidence=assessment.missing_evidence,
        content_overlap=content_overlap,
    )
    return {"result": result}


class EvidenceAndContentPipeline:
    id: JudgePipelineId = "evidence-and-content"

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        builder = StateGraph(PipelineState)
        builder.add_node("compare_reference_content", compare_reference_content)
        builder.add_node("preserve_execution_failure", preserve_execution_failure)
        builder.add_node("assess_evidence", assess_evidence)
        builder.add_node("finalize_judgment", finalize_judgment)

        builder.add_edge(START, "compare_reference_content")
        builder.add_conditional_edges(
            "compare_reference_content",
            route_after_content,
            {
                "preserve_execution_failure": "preserve_execution_failure",
                "assess_evidence": "assess_evidence",
            },
        )
        builder.add_edge("preserve_execution_failure", END)
        builder.add_edge("assess_evidence", "finalize_judgment")
        builder.add_edge("finalize_judgment", END)
        return builder.compile()

    async def run(self, request: JudgeRequest, runtime: JudgeRuntime) -> JudgeResult:
        initial_state: PipelineState = {
            "request": request,
            "runtime": runtime,
        }
        final_state = await self.graph.ainvoke(initial_state)
        result: JudgeResult = final_state["result"]
        return result
