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
    require_run_evidence_access,
)
from gamr_api.main import app
from gamr_api.registry import InMemoryRegistry
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


def test_browser_activity_is_an_allowlist_and_drops_server_only_metadata() -> None:
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
        "detailAvailability": "redacted",
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
def test_browser_evidence_never_returns_secret_bearer_path_or_idempotency_fields(
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
    encoded = str(safe)
    assert "secret-value" not in encoded
    assert "/srv/gamr" not in encoded
    assert "idempotency" not in encoded.lower()


def test_every_browser_projection_redacts_configured_secrets() -> None:
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

    assert secret not in str(safe_activity)
    assert secret not in str(safe_evidence)


def test_sse_redacts_configured_secrets_from_search_and_graph_payloads() -> None:
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
    assert secret not in response.text
