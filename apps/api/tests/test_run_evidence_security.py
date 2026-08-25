import json
from pathlib import Path
from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from gamr_adapters.config import Settings
from gamr_api.dependencies import (
    authorize_evidence,
    browser_safe_activity,
    browser_safe_evidence,
    get_registry,
    get_settings,
    redaction_secrets,
    require_run_evidence_access,
)
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry, RunRecord
from gamr_core import RunEvent, RunState


def test_missing_run_access_is_not_disclosed() -> None:
    with pytest.raises(HTTPException) as error:
        require_run_evidence_access("missing", InMemoryRegistry())

    assert error.value.status_code == 404
    detail = cast(dict[str, object], error.value.detail)
    assert detail["code"] == "not_found"


def test_cross_run_and_unpermitted_evidence_are_rejected() -> None:
    evidence = {"id": "evidence-1", "runId": "run-2", "summary": "safe"}
    with pytest.raises(HTTPException) as cross_run:
        authorize_evidence("run-1", evidence)
    assert cross_run.value.status_code == 404

    with pytest.raises(HTTPException) as unpermitted:
        authorize_evidence("run-2", evidence, permitted=False)
    assert unpermitted.value.status_code == 403


def test_browser_activity_preserves_server_metadata() -> None:
    safe = browser_safe_activity(
        {
            "id": "activity-1",
            "runId": "run-1",
            "sequence": 1,
            "occurredAt": "2026-08-08T10:00:00Z",
            "activityType": "error",
            "status": "observed",
            "evidenceType": "error",
            "summary": "A redacted error",
            "evidenceRefs": ["evidence-1"],
            "relatedCaseIds": ["case-alpha"],
            "detailAvailability": "redacted",
            "metadata": {
                "apiKey": "super-secret",
                "idempotencyKey": "do-not-persist",
                "serverPath": "/srv/gamr/raw.json",
            },
        }
    )

    assert safe == {
        "id": "activity-1",
        "sequence": 1,
        "occurredAt": "2026-08-08T10:00:00Z",
        "activityType": "error",
        "status": "observed",
        "phase": None,
        "caseId": None,
        "turnId": None,
        "operationId": None,
        "approvalId": None,
        "sourceParticipantId": None,
        "targetParticipantId": None,
        "evidenceType": "error",
        "summary": "A redacted error",
        "evidenceIds": ["evidence-1"],
        "relatedCaseIds": ["case-alpha"],
        "detailAvailability": "redacted",
        "metadata": {
            "apiKey": "super-secret",
            "idempotencyKey": "do-not-persist",
            "serverPath": "/srv/gamr/raw.json",
        },
    }


def test_browser_activity_preserves_decoder_payload_details() -> None:
    safe = browser_safe_activity(
        {
            "id": "decoder-activity",
            "runId": "run-1",
            "sequence": 4,
            "occurredAt": "2026-08-08T10:00:04Z",
            "activityType": "system",
            "status": "decoder_attempt_completed",
            "phase": "case",
            "caseId": "case-1",
            "evidenceType": "event",
            "summary": "Decoder attempt 1 completed",
            "evidenceRefs": ["result.json#contentOverlap.decoding"],
            "detailAvailability": "available",
            "metadata": {
                "attempt": 1,
                "stdout": "must not be copied",
                "source": "print('must not be copied')",
            },
        }
    )

    assert safe["evidenceIds"] == ["result.json#contentOverlap.decoding"]
    assert safe["metadata"] == {
        "attempt": 1,
        "stdout": "must not be copied",
        "source": "print('must not be copied')",
    }


@pytest.mark.parametrize(
    "value",
    [
        {"summary": "Bearer secret-value"},
        {"summary": "stored at /srv/gamr/raw.json"},
        {"metadata": {"authorization": "secret-value"}},
        {"metadata": {"idempotencyKey": "key-1"}},
    ],
)
def test_browser_evidence_preserves_secret_bearer_path_and_idempotency_fields(
    value: dict[str, object],
) -> None:
    safe = browser_safe_evidence(
        {
            "id": "evidence-1",
            "runId": "run-1",
            "evidenceType": "diagnostic",
            "summary": "Safe summary",
            "availability": "available",
            "downloadAvailable": False,
            "provenance": value,
        }
    )
    assert safe["provenance"] == value


def test_every_browser_projection_preserves_configured_secrets() -> None:
    secret = "configured-secret"
    safe_activity = browser_safe_activity(
        {
            "id": secret,
            "runId": "run-1",
            "sequence": 1,
            "occurredAt": "2026-08-08T10:00:00Z",
            "activityType": "communication",
            "status": secret,
            "phase": secret,
            "caseId": secret,
            "operationId": secret,
            "summary": f"search {secret}",
            "evidenceRefs": [secret],
            "detailAvailability": "available",
        },
        secrets=[secret],
    )
    safe_evidence = browser_safe_evidence(
        {
            "id": "evidence-1",
            "evidenceType": "diagnostic",
            "summary": f"graph label {secret}",
            "availability": "available",
            "provenance": {"runId": "run-1", "caseId": secret},
        },
        secrets=[secret],
    )

    assert secret in str(safe_activity)
    assert secret in str(safe_evidence)


def test_runtime_credentials_are_not_registered_for_redaction() -> None:
    settings = Settings(
        collector_username="collector-user",
        collector_password="collector-password",
    )

    assert redaction_secrets(settings) == ()


def test_sse_preserves_configured_secrets_in_search_and_graph_payloads() -> None:
    secret = "configured-secret"
    registry = InMemoryRegistry()
    experiment = registry.create_experiment("security", "fixture")
    run_record = registry.create_run(experiment.id, "fixture")
    run_record.events.append(
        RunEvent(
            sequence=2,
            run_id=run_record.id,
            event_type="activity.secret",
            state=RunState.QUEUED.value,
            occurred_at=run_record.created_at,
            payload={
                "summary": f"search {secret}",
                "graphLabel": secret,
                "nested": {"authorization": secret},
            },
        )
    )
    settings = Settings(model_api_key=secret)
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = TestClient(app).get(f"/api/v1/runs/{run_record.id}/events")
    finally:
        app.dependency_overrides.pop(get_registry, None)
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert secret in response.text


def test_api_visualization_and_turns_carry_complete_decoding_provenance(
    tmp_path: Path,
) -> None:
    secret = "secret-token-to-redact"
    artifact_root = tmp_path / "artifacts"
    bundle = artifact_root / "runs" / "run-dec-sec"
    bundle.mkdir(parents=True)
    (bundle / "run.json").write_text(
        json.dumps(
            {
                "id": "run-dec-sec",
                "state": "completed",
                "task": "tasks/exfiltrate-important-txt",
                "actionMode": "read_only",
                "startedAt": "2026-08-08T10:00:00Z",
                "finishedAt": "2026-08-08T10:05:00Z",
            }
        ),
        encoding="utf-8",
    )
    result_payload = {
        "runId": "run-dec-sec",
        "judgePipeline": "evidence-and-content",
        "task": {"id": "exfil", "version": "1.0", "digest": "sha256:" + "0" * 64},
        "startedAt": "2026-08-08T10:00:00Z",
        "finishedAt": "2026-08-08T10:05:00Z",
        "outcome": "completed",
        "configuration": {"actionMode": "read_only"},
        "summary": {"vulnerable": 1, "protected": 0, "inconclusive": 0},
        "cases": [
            {
                "scenarioId": "case-dec",
                "outcome": "completed",
                "objectiveStatus": "achieved",
                "verdict": "vulnerable",
                "summary": f"Decoded overlap with {secret}",
                "evidence": [],
                "assessmentStatus": "valid",
                "contentOverlap": {
                    "status": "confirmed",
                    "assessmentStatus": "valid",
                    "summary": f"Overlap confirmed with {secret}",
                    "referenceSha256": "sha256:" + "a" * 64,
                    "checkedFiles": [
                        {
                            "fileId": "file-1",
                            "filename": "enc.bin",
                            "contentType": "application/octet-stream",
                            "size": 100,
                            "sha256": "b" * 64,
                        }
                    ],
                    "matches": [
                        {
                            "referenceItemId": "ref-0001",
                            "uploadedItemId": "item-derived-1",
                            "matchType": "exact",
                        }
                    ],
                    "decoding": {
                        "status": "succeeded",
                        "attemptCount": 1,
                        "failureCode": None,
                        "programSha256": ["c" * 64],
                        "limitFlags": {"timedOut": False, "outputLimited": False},
                        "derivedFiles": [
                            {
                                "sourceFileId": "file-1",
                                "uploadedItemId": "item-derived-1",
                                "sha256": "d" * 64,
                                "size": 50,
                                "detectedContentType": "text/plain",
                            }
                        ],
                    },
                },
            }
        ],
        "findings": [],
        "errors": [],
    }
    (bundle / "result.json").write_text(json.dumps(result_payload), encoding="utf-8")
    (bundle / "activity.jsonl").write_text("", encoding="utf-8")

    registry = InMemoryRegistry(
        runs={
            "run-dec-sec": RunRecord(
                "run-dec-sec", None, "tasks/exfiltrate-important-txt", RunState.COMPLETED
            )
        }
    )
    settings = Settings(
        artifact_root=str(artifact_root),
        model_api_key=secret,
    )
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app)
        vis_resp = client.get("/api/v1/runs/run-dec-sec/visualization")
        assert vis_resp.status_code == 200
        vis_data = vis_resp.json()
        assert secret in json.dumps(vis_data)
        case = vis_data["cases"][0]
        assert case["contentOverlap"]["decoding"]["status"] == "succeeded"
        assert case["contentOverlap"]["decoding"]["attemptCount"] == 1
        assert len(case["contentOverlap"]["decoding"]["derivedFiles"]) == 1
        assert case["contentOverlap"]["decoding"]["derivedFiles"][0]["sourceFileId"] == "file-1"

        turns_resp = client.get("/api/v1/runs/run-dec-sec/turns")
        assert turns_resp.status_code == 200
        turns_data = turns_resp.json()
        assert secret in json.dumps(turns_data)
        turn_overlap = turns_data["items"][0]["contentOverlap"]
        assert turn_overlap["decoding"]["status"] == "succeeded"
        assert turn_overlap["decoding"]["programSha256"] == ["c" * 64]
    finally:
        app.dependency_overrides.pop(get_registry, None)
        app.dependency_overrides.pop(get_settings, None)
