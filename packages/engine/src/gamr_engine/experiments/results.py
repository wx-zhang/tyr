from __future__ import annotations

from datetime import UTC, datetime

from gamr_core import (
    AssessmentReasonCode,
    AssessmentStatus,
    CaseResult,
    ContentOverlapResult,
    Evidence,
    ExecutionOutcome,
    ExperimentPresetConfig,
    ObjectiveStatus,
    ResultSummary,
    RunResult,
    Scenario,
    SecurityVerdict,
    TaskReference,
)
from gamr_core.identifiers import new_id

from ..ports.tracing import TraceObservation, TracePort, trace_score
from .records import LoadedTask


def score_case(
    case: CaseResult,
    trace_port: TracePort | None,
    observation: TraceObservation | None,
) -> None:
    if observation is None:
        return
    trace_score(trace_port, "security_verdict", case.verdict.value, observation=observation)
    trace_score(
        trace_port, "objective_status", case.objective_status.value, observation=observation
    )
    trace_score(
        trace_port, "assessment_status", case.assessment_status.value, observation=observation
    )
    if case.outcome is not None:
        trace_score(trace_port, "execution_outcome", case.outcome.value, observation=observation)


def case_result(
    scenario: Scenario,
    *,
    scenario_execution_id: str | None = None,
    outcome: ExecutionOutcome,
    objective_status: ObjectiveStatus,
    verdict: SecurityVerdict,
    summary: str,
    turn_ids: list[str],
    assessment_status: AssessmentStatus = AssessmentStatus.UNKNOWN,
    assessment_failure: str | None = None,
    reason_codes: list[AssessmentReasonCode] | None = None,
    missing_evidence: list[str] | None = None,
    content_overlap: ContentOverlapResult | None = None,
) -> CaseResult:
    return CaseResult(
        scenarioId=scenario.metadata.id,
        scenarioExecutionId=scenario_execution_id or new_id(),
        outcome=outcome,
        objectiveStatus=objective_status,
        verdict=verdict,
        summary=summary,
        assessmentStatus=assessment_status,
        assessmentFailure=assessment_failure,
        reasonCodes=reason_codes or [],
        missingEvidence=missing_evidence or [],
        contentOverlap=content_overlap,
        evidence=[
            Evidence(turnId=turn_id, artifact=f"raw/{turn_id}.json") for turn_id in turn_ids
        ],
    )


def result(
    run_id: str,
    started_at: datetime,
    task: LoadedTask,
    config: ExperimentPresetConfig,
    results: list[CaseResult],
    *,
    outcome: ExecutionOutcome = ExecutionOutcome.COMPLETED,
    errors: list[str] | None = None,
) -> RunResult:
    counts = {verdict.value: 0 for verdict in SecurityVerdict}
    for item in results:
        counts[item.verdict.value] += 1
    return RunResult(
        schemaVersion="1.0",
        runId=run_id,
        task=TaskReference(
            id=task.manifest.metadata.id,
            version=task.manifest.metadata.version,
            digest=task.digest,
        ),
        startedAt=started_at,
        finishedAt=datetime.now(UTC),
        outcome=outcome,
        configuration=config,
        summary=ResultSummary(
            vulnerable=counts[SecurityVerdict.VULNERABLE.value],
            protected=counts[SecurityVerdict.PROTECTED.value],
            inconclusive=counts[SecurityVerdict.INCONCLUSIVE.value],
        ),
        cases=results,
        judgePipeline=(
            task.manifest.spec.judge.pipeline if task.evaluation is not None else None
        ),
        findings=[],
        errors=errors or [],
    )


def scenario_succeeded(case: CaseResult) -> bool:
    return (
        case.outcome is ExecutionOutcome.COMPLETED
        and case.objective_status is ObjectiveStatus.ACHIEVED
    )

def finish_result(
    trace_port: TracePort | None,
    run_id: str,
    started_at: datetime,
    task: LoadedTask,
    config: ExperimentPresetConfig,
    cases: list[CaseResult],
    *,
    outcome: ExecutionOutcome = ExecutionOutcome.COMPLETED,
    errors: list[str] | None = None,
    observation: TraceObservation | None,
) -> RunResult:
    finished = result(run_id, started_at, task, config, cases, outcome=outcome, errors=errors)
    if observation is not None:
        trace_score(
            trace_port, "final_run_outcome", finished.outcome.value, observation=observation
        )
    return finished
