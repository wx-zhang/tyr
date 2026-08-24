from datetime import UTC, datetime

import pytest
from gamr_core import (
    AssessmentStatus,
    ContentMatchType,
    ContentOverlapResult,
    ContentOverlapStatus,
    DecodingAttempt,
    DecodingExecutionResult,
    DecodingFailureCode,
    DecodingLimitFlags,
    DecodingProvenance,
    DecodingStatus,
    DecodingStream,
    DerivedContentFile,
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


def test_content_overlap_result_accepts_detailed_markdown_summary() -> None:
    summary = "### Differences\n\n```diff\n" + ("- expected\n+ received\n" * 80) + "```"

    result = ContentOverlapResult(
        status=ContentOverlapStatus.NOT_FOUND,
        assessmentStatus=AssessmentStatus.VALID,
        summary=summary,
    )

    assert result.summary == summary


def test_decoding_provenance_round_trips_route_attempt_and_execution_details() -> None:
    digest = "a" * 64
    provenance = DecodingProvenance(
        status=DecodingStatus.SUCCEEDED,
        action="execute",
        rationale="The wrapper must be removed before comparison.",
        attemptCount=1,
        programSha256=[digest],
        attempts=[
            DecodingAttempt(
                attempt=1,
                stage="output_validation",
                source="print('decode')",
                programSha256=digest,
                execution=DecodingExecutionResult(
                    exitCode=0,
                    elapsedSeconds=0.25,
                    stdout=DecodingStream(state="captured", value="ok"),
                    stderr=DecodingStream(state="empty"),
                ),
            )
        ],
    )

    dumped = provenance.model_dump(by_alias=True, mode="json")
    assert dumped["rationale"] == "The wrapper must be removed before comparison."
    assert dumped["attempts"][0]["execution"]["stdout"] == {"state": "captured", "value": "ok"}
    assert DecodingProvenance.model_validate(dumped) == provenance


def test_decoding_stream_states_reject_values_for_non_captured_streams() -> None:
    with pytest.raises(ValidationError):
        DecodingStream(state="suppressed", value="secret")


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


def test_decoding_provenance_success_model_validation_and_aliases() -> None:
    data = {
        "status": "succeeded",
        "attemptCount": 2,
        "failureCode": None,
        "programSha256": ["a" * 64, "b" * 64],
        "limitFlags": {
            "timedOut": False,
            "outputLimited": False,
        },
        "derivedFiles": [
            {
                "sourceFileId": "file-001",
                "uploadedItemId": "upload-001",
                "sha256": "c" * 64,
                "size": 128,
                "detectedContentType": "text/plain",
            }
        ],
    }
    provenance = DecodingProvenance.model_validate(data)
    assert provenance.status is DecodingStatus.SUCCEEDED
    assert provenance.attempt_count == 2
    assert provenance.failure_code is None
    assert provenance.program_sha256 == ["a" * 64, "b" * 64]
    assert provenance.limit_flags.timed_out is False
    assert provenance.limit_flags.output_limited is False
    assert len(provenance.derived_files) == 1
    assert provenance.derived_files[0].source_file_id == "file-001"
    assert provenance.derived_files[0].uploaded_item_id == "upload-001"
    assert provenance.derived_files[0].sha256 == "c" * 64
    assert provenance.derived_files[0].size == 128
    assert provenance.derived_files[0].detected_content_type == "text/plain"

    dumped = provenance.model_dump(by_alias=True, mode="json")
    assert dumped["status"] == "succeeded"
    assert dumped["attemptCount"] == 2
    assert dumped["programSha256"] == ["a" * 64, "b" * 64]
    assert dumped["limitFlags"] == {"timedOut": False, "outputLimited": False}
    assert dumped["derivedFiles"][0]["sourceFileId"] == "file-001"
    assert dumped["derivedFiles"][0]["uploadedItemId"] == "upload-001"
    assert dumped["derivedFiles"][0]["detectedContentType"] == "text/plain"


def test_decoding_provenance_failed_and_skipped_states() -> None:
    failed = DecodingProvenance.model_validate(
        {
            "status": "failed",
            "attemptCount": 3,
            "failureCode": "attempt_exhaustion",
            "programSha256": ["a" * 64, "b" * 64, "c" * 64],
            "limitFlags": {"timedOut": True, "outputLimited": False},
            "derivedFiles": [],
        }
    )
    assert failed.status is DecodingStatus.FAILED
    assert failed.attempt_count == 3
    assert failed.failure_code is DecodingFailureCode.ATTEMPT_EXHAUSTION
    assert failed.limit_flags.timed_out is True

    skipped = DecodingProvenance.model_validate(
        {
            "status": "skipped",
            "attemptCount": 0,
            "failureCode": None,
            "programSha256": [],
            "limitFlags": {"timedOut": False, "outputLimited": False},
            "derivedFiles": [],
        }
    )
    assert skipped.status is DecodingStatus.SKIPPED
    assert skipped.attempt_count == 0


@pytest.mark.parametrize(
    "status",
    ["succeeded", "failed", "skipped"],
)
def test_decoding_status_closed_enum_values(status: str) -> None:
    assert DecodingStatus(status).value == status


@pytest.mark.parametrize(
    "code",
    [
        "invalid_agent_response",
        "unknown_tool_or_input",
        "attempt_exhaustion",
        "sandbox_unavailable",
        "unsafe_isolation",
        "infrastructure_failure",
        "timeout",
        "output_limit",
        "unavailable_import",
        "empty_output",
        "invalid_output_tree",
        "ambiguous_lineage",
        "preparation_failure",
    ],
)
def test_decoding_failure_code_closed_enum_values(code: str) -> None:
    assert DecodingFailureCode(code).value == code


@pytest.mark.parametrize(
    "invalid_code",
    ["unknown_code", "syntax_error", "exception_thrown", "custom_error"],
)
def test_decoding_failure_code_rejects_unknown_values(invalid_code: str) -> None:
    with pytest.raises(ValidationError):
        DecodingProvenance.model_validate(
            {
                "status": "failed",
                "attemptCount": 1,
                "failureCode": invalid_code,
            }
        )


@pytest.mark.parametrize("attempt_count", [-1, 4, 10, "two"])
def test_decoding_provenance_rejects_invalid_attempt_bounds(attempt_count: object) -> None:
    with pytest.raises(ValidationError):
        DecodingProvenance.model_validate(
            {
                "status": "failed",
                "attemptCount": attempt_count,
            }
        )


def test_decoding_provenance_rejects_program_sha256_count_mismatch() -> None:
    with pytest.raises(ValidationError, match="programSha256 count"):
        DecodingProvenance.model_validate(
            {
                "status": "succeeded",
                "attemptCount": 2,
                "programSha256": ["a" * 64],
            }
        )


@pytest.mark.parametrize(
    "invalid_digest",
    [
        "not-a-hash",
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "sha256:" + "a" * 64,
    ],
)
def test_decoding_provenance_rejects_invalid_digest_patterns(invalid_digest: str) -> None:
    with pytest.raises(ValidationError):
        DecodingProvenance.model_validate(
            {
                "status": "succeeded",
                "attemptCount": 1,
                "programSha256": [invalid_digest],
            }
        )
    with pytest.raises(ValidationError):
        DerivedContentFile.model_validate(
            {
                "sourceFileId": "file-001",
                "uploadedItemId": "upload-001",
                "sha256": invalid_digest,
                "size": 10,
                "detectedContentType": "text/plain",
            }
        )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "source",
        "code",
        "content",
        "stdout",
        "stderr",
        "prompt",
        "prompts",
        "tool_messages",
        "sandbox_id",
        "container_name",
        "host_path",
        "secret",
        "bearer_token",
    ],
)
def test_decoding_models_forbid_extra_or_secret_bearing_fields(forbidden_field: str) -> None:
    with pytest.raises(ValidationError):
        DecodingProvenance.model_validate(
            {
                "status": "succeeded",
                "attemptCount": 1,
                "programSha256": ["a" * 64],
                forbidden_field: "sensitive_data",
            }
        )
    with pytest.raises(ValidationError):
        DerivedContentFile.model_validate(
            {
                "sourceFileId": "file-001",
                "uploadedItemId": "upload-001",
                "sha256": "a" * 64,
                "size": 10,
                "detectedContentType": "text/plain",
                forbidden_field: "sensitive_data",
            }
        )
    with pytest.raises(ValidationError):
        DecodingLimitFlags.model_validate(
            {
                "timedOut": False,
                "outputLimited": False,
                forbidden_field: "sensitive_data",
            }
        )


def test_content_overlap_result_with_decoding_provenance() -> None:
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
            "decoding": {
                "status": "succeeded",
                "attemptCount": 1,
                "programSha256": ["f" * 64],
                "limitFlags": {"timedOut": False, "outputLimited": False},
                "derivedFiles": [
                    {
                        "sourceFileId": "file-1",
                        "uploadedItemId": "upload-001",
                        "sha256": "b" * 64,
                        "size": 12,
                        "detectedContentType": "text/plain",
                    }
                ],
            },
        }
    )
    assert result.decoding is not None
    assert result.decoding.status is DecodingStatus.SUCCEEDED
    assert result.decoding.attempt_count == 1
    assert result.decoding.derived_files[0].source_file_id == "file-1"

    dumped = result.model_dump(by_alias=True, mode="json")
    assert "decoding" in dumped
    assert dumped["decoding"]["status"] == "succeeded"


def test_legacy_content_overlap_result_without_decoding_provenance() -> None:
    legacy_payload = {
        "status": "not_found",
        "assessmentStatus": "valid",
        "checkedFiles": [],
        "matches": [],
    }
    result = ContentOverlapResult.model_validate(legacy_payload)
    assert result.decoding is None
    dumped = result.model_dump(by_alias=True, mode="json")
    assert dumped.get("decoding") is None
