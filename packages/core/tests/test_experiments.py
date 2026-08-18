from datetime import UTC, datetime

import pytest
from gamr_core import (
    ContentMatchType,
    ContentOverlapResult,
    ContentOverlapStatus,
    ExperimentConfig,
    ExperimentRecord,
    RunRecord,
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
