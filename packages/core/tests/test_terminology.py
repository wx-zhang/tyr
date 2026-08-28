from datetime import UTC, datetime

import pytest
from gamr_core import (
    CompletionOutcome,
    EvidenceQuery,
    ExperimentPresetConfig,
    ExperimentResult,
    RunActivity,
    ScenarioExecutionResult,
    TaskManifest,
)
from pydantic import ValidationError


def _result_payload(scenario: dict[str, object]) -> dict[str, object]:
    return {
        "runId": "experiment-1",
        "task": {"id": "task", "version": "1.0.0", "digest": "sha256:" + "a" * 64},
        "startedAt": datetime(2026, 8, 28, tzinfo=UTC),
        "outcome": "completed",
        "configuration": {"scenarioIds": ["scenario-1"]},
        "summary": {"vulnerable": 0, "protected": 1, "inconclusive": 0},
        "cases": [scenario],
        "findings": [],
        "errors": [],
    }


def test_historical_case_result_normalizes_to_canonical_output() -> None:
    result = ExperimentResult.model_validate(
        _result_payload(
            {
                "caseId": "scenario-1",
                "outcome": "completed",
                "verdict": "protected",
                "summary": "Protected",
                "evidence": [],
            }
        )
    )
    execution = result.scenario_executions[0]
    assert execution.scenario_id == "scenario-1"
    assert execution.scenario_execution_id == "scenario-1"
    dumped = result.model_dump(by_alias=True)
    assert "scenarioExecutions" in dumped
    assert "cases" not in dumped
    assert "caseId" not in dumped["scenarioExecutions"][0]


def test_definition_and_execution_ids_remain_distinct() -> None:
    execution = ScenarioExecutionResult(
        scenarioId="catalog-scenario",
        scenarioExecutionId="execution-1",
        outcome=CompletionOutcome.COMPLETED,
        verdict="protected",
        summary="Protected",
        evidence=[],
    )
    assert execution.scenario_id != execution.scenario_execution_id

def test_conflicting_historical_ids_keep_definition_and_execution_identity() -> None:
    execution = ScenarioExecutionResult.model_validate(
        {
            "scenarioId": "catalog-scenario",
            "caseId": "legacy-execution",
            "outcome": "completed",
            "verdict": "protected",
            "summary": "Protected",
            "evidence": [],
        }
    )
    assert execution.scenario_id == "catalog-scenario"
    assert execution.scenario_execution_id == "legacy-execution"


def test_scenario_execution_without_identity_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ScenarioExecutionResult.model_validate(
            {
                "outcome": "completed",
                "verdict": "protected",
                "summary": "Protected",
                "evidence": [],
            }
        )


def test_canonical_config_writes_new_fields_and_reads_legacy_fields() -> None:
    config = ExperimentPresetConfig(
        caseIds=["scenario-1"],
        scientistIterations=2,
        historyScientistRuns=3,
        maxConcurrentCases=1,
    )
    dumped = config.model_dump(by_alias=True)
    assert dumped["scenarioIds"] == ["scenario-1"]
    assert dumped["researchIterations"] == 2
    assert dumped["historyResearchRuns"] == 3
    assert dumped["maxConcurrentScenarioExecutions"] == 1


def test_activity_and_query_map_case_identity_to_execution_identity() -> None:
    activity = RunActivity.model_validate(
        {
            "id": "activity-1",
            "runId": "experiment-1",
            "sequence": 1,
            "occurredAt": datetime(2026, 8, 28, tzinfo=UTC),
            "activityType": "case",
            "status": "case_started",
            "caseId": "legacy-case",
            "evidenceType": "event",
            "summary": "started",
        }
    )
    query = EvidenceQuery(runId="experiment-1", caseId="legacy-case")
    assert activity.scenario_execution_id == "legacy-case"
    assert query.scenario_execution_id == "legacy-case"


def test_task_manifest_writes_scenarios_from_legacy_cases() -> None:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "task", "title": "Task", "version": "1.0.0"},
            "spec": {
                "cases": ["cases/one.json"],
                "defaults": {
                    "maxTurns": 1,
                    "actionMode": "read_only",
                    "defaultCaseIds": ["one"],
                },
            },
        }
    )
    dumped = manifest.model_dump(by_alias=True)
    assert dumped["spec"]["scenarios"] == ["cases/one.json"]
    assert dumped["spec"]["defaults"]["defaultScenarioIds"] == ["one"]
