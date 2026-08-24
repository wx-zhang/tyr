from datetime import UTC, datetime

import pytest
from gamr_core import (
    ActivityType,
    Availability,
    EvidenceItem,
    EvidenceQuery,
    EvidenceType,
    ParticipantKind,
    RunActivity,
    RunParticipant,
    SandboxExecutionPreview,
    SandboxOperationEvent,
    SandboxOperationState,
    SandboxPreviewText,
)
from pydantic import ValidationError


def activity(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": "0190a000-0000-7000-8000-000000000001",
        "runId": "run-1",
        "sequence": 1,
        "occurredAt": "2026-08-08T10:00:00Z",
        "activityType": "case",
        "status": "active",
        "evidenceType": "event",
        "summary": "Case started",
        "detailAvailability": "available",
        "metadata": {"order": 0},
    }
    value.update(overrides)
    return value


def test_activity_accepts_safe_camel_case_contract_and_explicit_utc() -> None:
    item = RunActivity.model_validate(activity())

    assert item.activity_type is ActivityType.CASE
    assert item.occurred_at == datetime(2026, 8, 8, 10, tzinfo=UTC)
    assert item.model_dump(by_alias=True)["detailAvailability"] == Availability.AVAILABLE


def test_activity_related_case_ids_are_unique_bounded_and_safe() -> None:
    item = RunActivity.model_validate(activity(relatedCaseIds=["case-alpha", "case-beta"]))

    assert item.related_case_ids == ["case-alpha", "case-beta"]

    with pytest.raises(ValidationError):
        RunActivity.model_validate(activity(relatedCaseIds=["case-alpha", "case-alpha"]))
    with pytest.raises(ValidationError):
        RunActivity.model_validate(
            activity(relatedCaseIds=[f"case-{index}" for index in range(101)])
        )
    with pytest.raises(ValidationError):
        RunActivity.model_validate(activity(relatedCaseIds=["/srv/gamr/raw.json"]))


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", ""),
        ("runId", ""),
        ("sequence", 0),
        ("sequence", -1),
        ("occurredAt", "2026-08-08T10:00:00"),
        ("occurredAt", "2026-08-08T12:00:00+02:00"),
        ("detailAvailability", "unknown"),
        ("metadata", {"authorization": "Bearer secret"}),
        ("metadata", {"path": "/srv/gamr/raw.json"}),
        ("metadata", {"idempotencyKey": "key-1"}),
        ("metadata", {"nested": {"provider": "payload"}}),
        ("summary", "Bearer super-secret"),
        ("summary", "captured at /srv/gamr/raw.json"),
    ],
)
def test_activity_rejects_invalid_or_unsafe_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        RunActivity.model_validate(activity(**{field: value}))


def test_run_state_activities_use_the_run_state_enum() -> None:
    RunActivity.model_validate(activity(activityType="run_state", status="running"))

    with pytest.raises(ValidationError):
        RunActivity.model_validate(activity(activityType="run_state", status="finished"))


def test_participant_identity_is_explicit_and_labels_do_not_define_identity() -> None:
    first = RunParticipant(
        id="participant-1",
        runId="run-1",
        kind=ParticipantKind.TYR_AGENT,
        displayLabel="Tyr",
        firstObservedSequence=2,
        evidenceId="evidence-1",
    )
    second = first.model_copy(update={"id": "participant-2"})

    assert first.id != second.id

    with pytest.raises(ValidationError):
        RunParticipant.model_validate(
            first.model_dump(by_alias=True) | {"firstObservedSequence": 0}
        )


def test_evidence_items_and_queries_bound_availability_and_page_size() -> None:
    evidence = EvidenceItem(
        id="evidence-1",
        runId="run-1",
        evidenceType=EvidenceType.DIAGNOSTIC,
        summary="A redacted diagnostic",
        availability=Availability.REDACTED,
        contentRef="raw/turn-1.json",
        contentSize=10,
        provenance={"runId": "run-1", "turnId": "turn-1"},
    )
    query = EvidenceQuery(runId="run-1", q="literal [text]", limit=200)

    assert evidence.availability is Availability.REDACTED
    assert query.query == "literal [text]"

    with pytest.raises(ValidationError):
        EvidenceQuery(runId="run-1", limit=201)
    with pytest.raises(ValidationError):
        EvidenceQuery(runId="run-1", occurredFrom=datetime(2026, 8, 8, 10))


def test_sandbox_operation_event_accepts_bounded_camel_case_contract() -> None:
    event = SandboxOperationEvent(
        operationId="sandbox-operation-1",
        state=SandboxOperationState.EXECUTION_STARTED,
        generation=1,
        attempt=1,
        programSha256="a" * 64,
        source=SandboxPreviewText(state="captured", value="print('ok')"),
    )

    assert event.state is SandboxOperationState.EXECUTION_STARTED
    assert event.model_dump(by_alias=True)["operationId"] == "sandbox-operation-1"
    assert event.model_dump(by_alias=True)["programSha256"] == "a" * 64


def test_sandbox_execution_preview_requires_structured_streams() -> None:
    execution = SandboxExecutionPreview(
        exitCode=0,
        elapsedSeconds=0.25,
        stdout=SandboxPreviewText(state="empty"),
        stderr=SandboxPreviewText(state="captured", value="ok"),
    )

    assert execution.elapsed_seconds == 0.25
    assert execution.stdout.state == "empty"

    with pytest.raises(ValidationError):
        SandboxPreviewText(state="captured")
    with pytest.raises(ValidationError):
        SandboxPreviewText(state="empty", value="unexpected")


def test_sandbox_operation_event_rejects_invalid_state_specific_fields() -> None:
    with pytest.raises(ValidationError):
        SandboxOperationEvent(
            operationId="sandbox-operation-1",
            state=SandboxOperationState.READY,
            generation=1,
            execution=SandboxExecutionPreview(
                exitCode=0,
                elapsedSeconds=0.1,
                stdout=SandboxPreviewText(state="empty"),
                stderr=SandboxPreviewText(state="empty"),
            ),
        )
    with pytest.raises(ValidationError):
        SandboxOperationEvent(
            operationId="sandbox-operation-1",
            state=SandboxOperationState.EXECUTION_COMPLETED,
            generation=1,
            execution=SandboxExecutionPreview(
                exitCode=0,
                elapsedSeconds=0.1,
                stdout=SandboxPreviewText(state="empty"),
                stderr=SandboxPreviewText(state="empty"),
            ),
            source=SandboxPreviewText(state="captured", value="x" * (64 * 1024 + 1)),
        )


def test_run_activity_accepts_optional_sandbox_event_and_legacy_activity() -> None:
    event = SandboxOperationEvent(
        operationId="sandbox-operation-1",
        state=SandboxOperationState.REQUESTED,
        generation=1,
    )
    item = RunActivity.model_validate(
        activity(
            activityType="execution",
            status="sandbox_requested",
            operationId="sandbox-operation-1",
            sandboxEvent=event.model_dump(by_alias=True, mode="json"),
        )
    )

    assert item.sandbox_event is not None
    assert item.sandbox_event.operation_id == "sandbox-operation-1"
    assert RunActivity.model_validate(activity()).sandbox_event is None
