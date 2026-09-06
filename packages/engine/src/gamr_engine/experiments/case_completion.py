from __future__ import annotations

from gamr_core import (
    AssessmentStatus,
    CaseResult,
    ExecutionOutcome,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
)

from ..ports.artifacts import ArtifactStore
from ..ports.tracing import TraceObservation, TracePort
from .activity import RunEvents
from .artifacts import scientist_artifact_id, write_case_result
from .records import PhaseResult, RenderedScenario, ScenarioExecutionRecord
from .results import case_result, score_case


def unassessed_case(
    scenario: Scenario,
    scenario_execution_id: str,
    result: PhaseResult,
    turn_ids: list[str],
) -> CaseResult:
    return case_result(
        scenario,
        scenario_execution_id=scenario_execution_id,
        outcome=ExecutionOutcome.FAILED if result.error else ExecutionOutcome.COMPLETED,
        objective_status=(
            ObjectiveStatus.UNKNOWN
            if not result.error
            else (ObjectiveStatus.PARTIAL if turn_ids else ObjectiveStatus.NOT_ATTEMPTED)
        ),
        verdict=SecurityVerdict.INCONCLUSIVE if result.error else SecurityVerdict.NOT_APPLICABLE,
        summary=result.error or "Evaluation not configured.",
        turn_ids=turn_ids,
        assessment_status=AssessmentStatus.SKIPPED,
        assessment_failure="evaluation_not_configured",
    )


def finish_case(
    scenario: Scenario,
    rendered: RenderedScenario,
    case: CaseResult,
    transcript: list[dict[str, str]],
    *,
    error: str | None,
    detail: str,
    phase: str,
    run_id: str,
    artifacts: ArtifactStore | None,
    events: RunEvents,
    trace_port: TracePort | None,
    observation: TraceObservation | None,
) -> tuple[ScenarioExecutionRecord, str | None]:
    write_case_result(artifacts, run_id, case, stage=phase)
    events.emit(
        "case.completed",
        run_id,
        phase=phase,
        case_id=scenario.metadata.id,
        detail=detail,
    )
    score_case(case, trace_port, observation)
    record = ScenarioExecutionRecord(
        scenario=scenario,
        rendered_title=rendered.title,
        rendered_objective=rendered.objective,
        rendered_steps=rendered.steps,
        rendered_success=rendered.success,
        case=case,
        scenario_execution_id=case.scenario_execution_id,
        transcript=transcript,
        origin="scientist" if phase == "scientist" else "base",
        origin_run_id=run_id if phase == "scientist" else None,
        origin_artifact_id=(
            scientist_artifact_id(scenario.metadata.id) if phase == "scientist" else None
        ),
    )
    return record, error
