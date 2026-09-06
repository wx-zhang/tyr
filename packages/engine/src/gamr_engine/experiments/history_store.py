from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from gamr_core import (
    DiscoveryCandidate,
    ExperimentPresetConfig,
    RunRecord,
    RunResult,
    RunState,
    Scenario,
)
from pydantic import ValidationError

from ..ports.artifacts import ArtifactStore
from .artifacts import scientist_artifact_id
from .records import LoadedTask, RenderedScenario, ScenarioExecutionRecord
from .rendering import render_scenario, select_scenarios, variables


@dataclass(frozen=True)
class _HistorySource:
    run_id: str
    configuration: ExperimentPresetConfig
    created_at: datetime
    result: RunResult


def load_prior_records(
    task: LoadedTask,
    candidate: DiscoveryCandidate,
    artifacts: ArtifactStore,
    source_run_id: str,
) -> list[ScenarioExecutionRecord]:
    payload = artifacts.read_json(source_run_id, "result.json")
    source_result = RunResult.model_validate(payload)
    return records_from_result(
        task,
        candidate,
        artifacts,
        source_run_id,
        source_result,
        source_result.configuration,
        source_result.started_at,
        include_base=True,
        include_scientist=True,
    )


def load_configured_history(
    task: LoadedTask,
    candidate: DiscoveryCandidate,
    config: ExperimentPresetConfig,
    artifacts: ArtifactStore | None,
    current_run_id: str,
) -> list[ScenarioExecutionRecord]:
    if artifacts is None or not (config.history_test_runs or config.history_scientist_runs):
        return []
    list_run_ids = getattr(artifacts, "list_run_ids", None)
    if not callable(list_run_ids):
        return []
    sources: list[_HistorySource] = []
    terminal_states = {
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
        RunState.INTERRUPTED,
    }
    for source_run_id in list_run_ids():
        if source_run_id == current_run_id:
            continue
        try:
            source_run = RunRecord.model_validate(artifacts.read_json(source_run_id, "run.json"))
            if source_run.state not in terminal_states:
                continue
            source_result = RunResult.model_validate(
                artifacts.read_json(source_run_id, "result.json")
            )
        except (FileNotFoundError, TypeError, ValueError):
            continue
        if source_result.task.id != task.manifest.metadata.id:
            continue
        try:
            base_case_ids = {
                scenario.metadata.id
                for scenario in select_scenarios(task, source_run.configuration)
            }
        except ValueError:
            continue
        if not base_case_ids and not source_run.configuration.scientist_iterations:
            continue
        sources.append(
            _HistorySource(
                source_run_id,
                source_run.configuration,
                source_run.created_at,
                source_result,
            )
        )
    records: list[ScenarioExecutionRecord] = []
    for source in sorted(sources, key=lambda item: (item.created_at, item.run_id)):
        has_base = bool(select_scenarios(task, source.configuration))
        has_scientist = bool(source.configuration.scientist_iterations)
        include_base = has_base and config.history_test_runs > 0
        include_scientist = has_scientist and config.history_scientist_runs > 0
        if not include_base and not include_scientist:
            continue
        records.extend(
            records_from_result(
                task,
                candidate,
                artifacts,
                source.run_id,
                source.result,
                source.configuration,
                source.created_at,
                include_base=include_base,
                include_scientist=include_scientist,
            )
        )
    return records


def records_from_result(
    task: LoadedTask,
    candidate: DiscoveryCandidate,
    artifacts: ArtifactStore,
    source_run_id: str,
    source_result: RunResult,
    source_configuration: ExperimentPresetConfig,
    source_created_at: datetime,
    *,
    include_base: bool,
    include_scientist: bool,
) -> list[ScenarioExecutionRecord]:
    scenario_by_id: dict[str, Scenario] = {
        scenario.metadata.id: scenario for scenario in task.scenarios
    }
    base_case_ids = {
        scenario.metadata.id for scenario in select_scenarios(task, source_configuration)
    }
    transcript_by_case: dict[str, list[dict[str, str]]] = {}
    for entry in artifacts.read_transcript(source_run_id):
        case_id = entry.get("caseId")
        role = entry.get("role")
        content = entry.get("content")
        if (
            not isinstance(case_id, str)
            or not isinstance(role, str)
            or not isinstance(content, str)
        ):
            continue
        turn: dict[str, str] = {"role": role, "content": content}
        turn_id = entry.get("turnId")
        if isinstance(turn_id, str):
            turn["turnId"] = turn_id
        transcript_by_case.setdefault(case_id, []).append(turn)
    values = variables(task, candidate)
    records: list[ScenarioExecutionRecord] = []
    for case in source_result.cases:
        is_base = case.scenario_id in base_case_ids
        if (is_base and not include_base) or (not is_base and not include_scientist):
            continue
        scenario = scenario_by_id.get(case.scenario_id)
        if scenario is None:
            safe_id = scientist_artifact_id(case.scenario_id)
            try:
                scenario = Scenario.model_validate(
                    artifacts.read_json(source_run_id, f"scientist-scenarios/{safe_id}.json")
                )
            except (FileNotFoundError, ValidationError, ValueError):
                continue
        try:
            rendered = render_scenario(scenario, values)
        except KeyError:
            rendered = RenderedScenario(
                scenario.metadata.title,
                scenario.spec.objective,
                list(scenario.spec.steps),
                scenario.spec.success_criteria or "",
                scenario.spec.expected_control,
            )
        records.append(
            ScenarioExecutionRecord(
                scenario=scenario,
                rendered_title=rendered.title,
                rendered_objective=rendered.objective,
                rendered_steps=rendered.steps,
                rendered_success=rendered.success,
                case=case,
                scenario_execution_id=case.scenario_execution_id,
                transcript=transcript_by_case.get(case.scenario_id, []),
                origin="base" if is_base else "scientist",
                origin_run_id=None if is_base else source_run_id,
                origin_artifact_id=(
                    None if is_base else scientist_artifact_id(case.scenario_id)
                ),
                source_created_at=source_created_at,
            )
        )
    return records
