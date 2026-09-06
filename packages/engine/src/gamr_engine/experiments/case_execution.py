from __future__ import annotations

from gamr_core import (
    DiscoveryCandidate,
    ExecutionOutcome,
    ExperimentPresetConfig,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
    TargetOrigin,
)
from gamr_core.identifiers import new_id

from ..collector_verification import (
    CollectorVerificationBatch,
    CollectorVerificationService,
    attach_verification_evidence,
)
from ..content_evidence import ContentEvidenceProvider
from ..ports.artifacts import ArtifactStore
from ..ports.models import ModelGateway
from ..ports.sandbox import Sandbox
from ..ports.targets import TargetGateway
from ..ports.tracing import TracePort, trace_span
from .activity import RunEvents
from .artifacts import turn_ids
from .case_assessment import assess_case
from .case_completion import finish_case, unassessed_case
from .conversation import ConversationRunner
from .records import LoadedTask, RenderedScenario, ScenarioExecutionRecord, TargetConversation
from .rendering import case_prompt, render_scenario, runtime_variable_names, variables
from .results import case_result


class CaseExecutor:
    def __init__(
        self,
        conversation: ConversationRunner,
        events: RunEvents,
        collector_verification: CollectorVerificationService,
        content_evidence_provider: ContentEvidenceProvider | None,
        sandbox: Sandbox | None,
        trace_port: TracePort | None,
    ) -> None:
        self._conversation = conversation
        self._events = events
        self._collector_verification = collector_verification
        self._content_evidence_provider = content_evidence_provider
        self._sandbox = sandbox
        self._trace_port = trace_port

    async def run(
        self,
        task: LoadedTask,
        scenario: Scenario,
        candidate: DiscoveryCandidate,
        config: ExperimentPresetConfig,
        target: TargetGateway,
        model: ModelGateway,
        judge_model: ModelGateway,
        run_id: str,
        artifacts: ArtifactStore | None,
        conversation: TargetConversation,
        *,
        phase: str = "case",
        target_origin: TargetOrigin = TargetOrigin.LIVE,
    ) -> tuple[ScenarioExecutionRecord, str | None]:
        case_id = scenario.metadata.id
        scenario_execution_id = new_id()
        self._events.register_execution(run_id, case_id, scenario_execution_id)
        with trace_span(
            self._trace_port,
            f"case:{case_id}",
            input={"objective": scenario.spec.objective, "steps": list(scenario.spec.steps)},
            metadata={
                "scenarioId": case_id,
                "scenarioExecutionId": scenario_execution_id,
                "runId": run_id,
                "phase": phase,
            },
        ) as case_obs:
            self._events.emit(
                "case.started",
                run_id,
                phase=phase,
                case_id=case_id,
                scenario_execution_id=scenario_execution_id,
                detail=scenario.metadata.title,
            )
            values = variables(task, candidate)
            try:
                rendered = render_scenario(scenario, values)
            except KeyError as exc:
                case = case_result(
                    scenario,
                    scenario_execution_id=scenario_execution_id,
                    outcome=ExecutionOutcome.FAILED,
                    objective_status=ObjectiveStatus.NOT_ATTEMPTED,
                    verdict=SecurityVerdict.INCONCLUSIVE,
                    summary=f"Missing runtime task variable: {exc.args[0]}",
                    turn_ids=[],
                )
                return finish_case(
                    scenario,
                    RenderedScenario(
                        scenario.metadata.title,
                        scenario.spec.objective,
                        list(scenario.spec.steps),
                        scenario.spec.success_criteria or "",
                        scenario.spec.expected_control,
                    ),
                    case,
                    [],
                    error=str(case.summary),
                    detail="failed",
                    phase=phase,
                    run_id=run_id,
                    artifacts=artifacts,
                    events=self._events,
                    trace_port=self._trace_port,
                    observation=case_obs,
                )

            prompt = case_prompt(task, rendered, values, target_origin)
            result = await self._conversation.run(
                prompt,
                target,
                model,
                config,
                scenario_execution_id=scenario_execution_id,
                max_turns=config.max_turns,
                conversation=conversation,
                require_candidates=False,
                run_id=run_id,
                artifacts=artifacts,
                phase=phase,
                case_id=case_id,
                runtime_vars=runtime_variable_names(rendered.steps),
            )
            ids = turn_ids(result.transcript)
            verification = await self.verify_collector(
                scenario,
                result.transcript,
                run_id,
                artifacts,
                phase,
                scenario_execution_id,
            )
            if task.evaluation is None:
                case = unassessed_case(scenario, scenario_execution_id, result, ids)
                case = attach_verification_evidence(case, verification, ids)
                return finish_case(
                    scenario,
                    rendered,
                    case,
                    result.transcript,
                    error=result.error,
                    detail=f"{'failed' if result.error else 'completed'} · {case.verdict.value}",
                    phase=phase,
                    run_id=run_id,
                    artifacts=artifacts,
                    events=self._events,
                    trace_port=self._trace_port,
                    observation=case_obs,
                )
            judge_result = await assess_case(
                task,
                scenario,
                rendered,
                result,
                verification,
                ids,
                judge_model=judge_model,
                content_evidence_provider=self._content_evidence_provider,
                sandbox=self._sandbox,
                artifacts=artifacts,
                events=self._events,
                trace_port=self._trace_port,
                run_id=run_id,
                phase=phase,
            )
            case = case_result(
                scenario,
                scenario_execution_id=scenario_execution_id,
                outcome=ExecutionOutcome.FAILED if result.error else ExecutionOutcome.COMPLETED,
                objective_status=judge_result.objective_status,
                verdict=judge_result.verdict,
                summary=judge_result.summary,
                turn_ids=judge_result.evidence_turn_ids,
                assessment_status=judge_result.assessment_status,
                assessment_failure=judge_result.assessment_failure,
                reason_codes=judge_result.reason_codes,
                missing_evidence=judge_result.missing_evidence,
                content_overlap=judge_result.content_overlap,
            )
            case = attach_verification_evidence(case, verification, ids)
            return finish_case(
                scenario,
                rendered,
                case,
                result.transcript,
                error=result.error,
                detail=(
                    f"{'failed' if result.error else 'completed'} · "
                    f"{judge_result.verdict.value}"
                ),
                phase=phase,
                run_id=run_id,
                artifacts=artifacts,
                events=self._events,
                trace_port=self._trace_port,
                observation=case_obs,
            )

    async def verify_collector(
        self,
        scenario: Scenario,
        transcript: list[dict[str, str]],
        run_id: str,
        artifacts: ArtifactStore | None,
        phase: str,
        scenario_execution_id: str | None = None,
    ) -> CollectorVerificationBatch:
        requirement = scenario.spec.collector_evidence
        if requirement is None:
            return CollectorVerificationBatch([], None, "verified")
        self._events.emit(
            "collector.verification_started",
            run_id,
            phase=phase,
            case_id=scenario.metadata.id,
            scenario_execution_id=scenario_execution_id,
        )
        batch = await self._collector_verification.verify(
            scenario.metadata.id,
            requirement,
            transcript,
            run_id,
            artifacts,
            scenario_execution_id=scenario_execution_id,
        )
        self._events.emit(
            f"collector.{batch.status}",
            run_id,
            phase=phase,
            case_id=scenario.metadata.id,
            scenario_execution_id=scenario_execution_id,
            detail=f"{len(batch.items)} collector request(s)",
        )
        return batch
