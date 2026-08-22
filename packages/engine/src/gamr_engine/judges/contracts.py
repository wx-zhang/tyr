from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from gamr_core import (
    AssessmentReasonCode,
    AssessmentStatus,
    ContentOverlapResult,
    EvaluationPlan,
    JudgePipelineId,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
)
from gamr_engine.content_evidence import AssessmentReference, ContentEvidenceProvider
from gamr_engine.ports.artifacts import ArtifactStore
from gamr_engine.ports.models import ModelGateway


@dataclass(frozen=True, slots=True)
class JudgeRequest:
    scenario: Scenario
    title: str
    objective: str
    steps: list[str]
    success_criteria: str
    expected_control: str | None
    transcript: list[dict[str, Any]]
    turn_ids: list[str]
    execution_error: str | None
    verifications: list[Any]
    evaluation_plan: EvaluationPlan | None
    assessment_reference: AssessmentReference | None = None
    phase: str = "base"


@dataclass(frozen=True, slots=True)
class JudgeRuntime:
    judge_model: ModelGateway
    content_evidence_provider: ContentEvidenceProvider | None = None
    artifacts: ArtifactStore | None = None
    activity_sink: Callable[[str, dict[str, Any]], None] | None = None
    run_id: str = ""
    case_id: str = ""


@dataclass(frozen=True, slots=True)
class JudgeResult:
    objective_status: ObjectiveStatus
    verdict: SecurityVerdict
    summary: str
    evidence_turn_ids: list[str]
    assessment_status: AssessmentStatus
    assessment_failure: str | None = None
    reason_codes: list[AssessmentReasonCode] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    content_overlap: ContentOverlapResult | None = None


class JudgePipeline(Protocol):
    id: JudgePipelineId
    graph: Any

    async def run(self, request: JudgeRequest, runtime: JudgeRuntime) -> JudgeResult: ...
