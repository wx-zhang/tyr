from datetime import UTC, datetime

import pytest
from gamr_core import (
    ContentMatchType,
    ContentOverlapResult,
    ContentOverlapStatus,
    ExperimentConfig,
    ExperimentRecord,
    RunRecord,
    RunResult,
    RunSource,
    RunState,
)
from pydantic import ValidationError


def test_json_records_round_trip_with_aliases() -> None:
    created_at = datetime(2026, 8, 9, tzinfo=UTC)
    experiment = ExperimentRecord(
        id="experiment-1",
        name="Read-only review",
        task="tasks/exfiltrate-important-txt",
        createdAt=created_at,
    )
    run = RunRecord(
        id="run-1",
        source=RunSource.CLI,
        experimentId=None,
        task="tasks/exfiltrate-important-txt",
        state=RunState.RUNNING,
        configuration=experiment.configuration,
        createdAt=created_at,
        updatedAt=created_at,
    )

    dumped = experiment.model_dump(by_alias=True, mode="json")
    assert dumped["schemaVersion"] == "1.0"
    assert dumped["task"] == "tasks/exfiltrate-important-txt"
    assert run.model_dump(by_alias=True, mode="json")["experimentId"] is None
    assert RunRecord.model_validate_json(run.model_dump_json(by_alias=True)) == run


def test_run_record_rejects_unsafe_result_path() -> None:
    with pytest.raises(ValidationError, match="relative"):
        RunRecord(
            id="run-1",
            source=RunSource.SERVICE,
            task="tasks/exfiltrate-important-txt",
            state=RunState.COMPLETED,
            createdAt=datetime.now(UTC),
            updatedAt=datetime.now(UTC),
            resultPath="/tmp/result.json",
        )


def test_scientist_only_configuration_requires_iterations() -> None:
    with pytest.raises(ValidationError, match="scientist iterations"):
        ExperimentConfig(caseIds=[])

    configuration = ExperimentConfig(caseIds=[], scientistIterations=1)
    assert configuration.case_ids == []


def test_history_run_windows_have_bounded_defaults() -> None:
    configuration = ExperimentConfig()

    assert configuration.history_test_runs == 10
    assert configuration.history_scientist_runs == 5


def test_history_run_windows_reject_values_above_the_bound() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(historyTestRuns=101)
    with pytest.raises(ValidationError):
        ExperimentConfig(historyScientistRuns=101)


def test_content_overlap_result_contains_only_safe_provenance() -> None:
    result = ContentOverlapResult.model_validate(
        {
            "status": "confirmed",
            "assessmentStatus": "valid",
            "referenceSha256": "sha256:" + "a" * 64,
            "checkedFiles": [
                {
                    "fileId": "file-1",
                    "filename": "evidence.txt",
                    "contentType": "text/plain",
                    "size": 12,
                    "sha256": "b" * 64,
                }
            ],
            "matches": [
                {
                    "referenceItemId": "ref-0001",
                    "uploadedItemId": "upload-001",
                    "matchType": "exact",
                }
            ],
        }
    )
    assert result.status is ContentOverlapStatus.CONFIRMED
    assert result.matches[0].match_type is ContentMatchType.EXACT
    assert "content" not in result.model_dump(by_alias=True)


def test_run_result_accepts_judge_pipeline_provenance() -> None:
    created_at = datetime(2026, 8, 9, tzinfo=UTC)
    result = RunResult.model_validate(
        {
            "schemaVersion": "1.0",
            "runId": "run-1",
            "judgePipeline": "evidence-and-content",
            "task": {
                "id": "exfiltrate-important-txt",
                "version": "1.0.0",
                "digest": "sha256:" + "a" * 64,
            },
            "startedAt": created_at,
            "outcome": "completed",
            "configuration": {"caseIds": ["case-1"]},
            "summary": {
                "vulnerable": 0,
                "protected": 1,
                "inconclusive": 0,
            },
            "cases": [],
            "findings": [],
            "errors": [],
        }
    )
    assert result.judge_pipeline == "evidence-and-content"
    dumped = result.model_dump(by_alias=True, mode="json")
    assert dumped["judgePipeline"] == "evidence-and-content"


def test_run_result_legacy_loading_without_judge_pipeline() -> None:
    created_at = datetime(2026, 8, 9, tzinfo=UTC)
    result = RunResult.model_validate(
        {
            "schemaVersion": "1.0",
            "runId": "run-1",
            "task": {
                "id": "exfiltrate-important-txt",
                "version": "1.0.0",
                "digest": "sha256:" + "a" * 64,
            },
            "startedAt": created_at,
            "outcome": "completed",
            "configuration": {"caseIds": ["case-1"]},
            "summary": {
                "vulnerable": 0,
                "protected": 1,
                "inconclusive": 0,
            },
            "cases": [],
            "findings": [],
            "errors": [],
        }
    )
    assert result.judge_pipeline is None
    dumped = result.model_dump(by_alias=True, mode="json")
    assert "judgePipeline" not in dumped or dumped["judgePipeline"] is None


@pytest.mark.parametrize(
    "invalid_pipeline",
    [
        "unknown-pipeline",
        "gamr_engine.judges.evidence_and_content:pipeline",
        "https://example.com/judge.py",
        "sh -c echo",
    ],
)
def test_run_result_rejects_unknown_or_executable_judge_pipeline(invalid_pipeline: str) -> None:
    created_at = datetime(2026, 8, 9, tzinfo=UTC)
    with pytest.raises(ValidationError):
        RunResult.model_validate(
            {
                "schemaVersion": "1.0",
                "runId": "run-1",
                "judgePipeline": invalid_pipeline,
                "task": {
                    "id": "exfiltrate-important-txt",
                    "version": "1.0.0",
                    "digest": "sha256:" + "a" * 64,
                },
                "startedAt": created_at,
                "outcome": "completed",
                "configuration": {"caseIds": ["case-1"]},
                "summary": {
                    "vulnerable": 0,
                    "protected": 1,
                    "inconclusive": 0,
                },
                "cases": [],
                "findings": [],
                "errors": [],
            }
        )




@pytest.mark.parametrize(
    ("status", "matches"),
    [
        ("confirmed", []),
        (
            "not_found",
            [
                {
                    "referenceItemId": "ref-0001",
                    "uploadedItemId": "upload-001",
                    "matchType": "exact",
                }
            ],
        ),
    ],
)
def test_content_overlap_status_and_matches_cannot_disagree(
    status: str, matches: list[dict[str, str]]
) -> None:
    with pytest.raises(ValidationError):
        ContentOverlapResult.model_validate(
            {
                "status": status,
                "assessmentStatus": "valid",
                "matches": matches,
            }
        )


def test_max_concurrent_cases_defaults_to_five() -> None:
    configuration = ExperimentConfig()
    assert configuration.max_concurrent_cases == 5
    dumped = configuration.model_dump(by_alias=True, mode="json")
    assert dumped["maxConcurrentCases"] == 5


@pytest.mark.parametrize("value", [1, 2, 3, 4, 5])
def test_max_concurrent_cases_accepts_values_one_through_five(value: int) -> None:
    configuration = ExperimentConfig(maxConcurrentCases=value)
    assert configuration.max_concurrent_cases == value
    dumped = configuration.model_dump(by_alias=True, mode="json")
    assert dumped["maxConcurrentCases"] == value


@pytest.mark.parametrize("value", [0, 6, -1, 10, "many", 3.5, None])
def test_max_concurrent_cases_rejects_out_of_range_and_non_integer(value: object) -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(maxConcurrentCases=value)  # type: ignore[arg-type]


def test_experiment_config_loads_without_max_concurrent_cases() -> None:
    old_data = {
        "actionMode": "read_only",
        "model": "test-model",
        "maxTurns": 40,
    }
    config = ExperimentConfig.model_validate(old_data)
    assert config.max_concurrent_cases == 5
