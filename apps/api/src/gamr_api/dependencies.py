from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from typing import Any

from fastapi import Request
from gamr_adapters.config import Settings
from gamr_core import RunActivity

from .errors import browser_safe_value, forbidden, not_found
from .execution import RunTaskManager
from .registry import InMemoryRegistry, JsonRegistry


@lru_cache
def get_settings() -> Settings:
    return Settings()


def redaction_secrets(settings: Settings) -> tuple[str, ...]:
    return tuple(
        secret
        for secret in (
            settings.tyr_mcp_token,
            settings.model_api_key,
            settings.collector_username,
            settings.collector_password,
        )
        if secret
    )


registry: InMemoryRegistry | None = None


def get_registry() -> InMemoryRegistry:
    global registry
    if registry is None:
        settings = get_settings()
        registry = JsonRegistry(
            settings.artifact_root,
            secrets=redaction_secrets(settings),
        )
    registry.refresh()
    return registry


def get_task_manager(request: Request) -> RunTaskManager | None:
    return getattr(request.app.state, "run_task_manager", None)


def require_run_evidence_access(run_id: str, registry: InMemoryRegistry) -> Any:
    run = registry.runs.get(run_id)
    if run is None:
        raise not_found("run")
    return run


def authorize_evidence(
    run_id: str,
    evidence: Any,
    *,
    permitted: bool = True,
) -> Any:
    value = (
        evidence.model_dump(by_alias=True, mode="json")
        if hasattr(evidence, "model_dump")
        else evidence
    )
    owner = value.get("runId") if isinstance(value, dict) else None
    if owner != run_id:
        raise not_found("evidence")
    if not permitted:
        raise forbidden("evidence")
    return evidence


def browser_safe_activity(
    activity: RunActivity | dict[str, object], *, secrets: Iterable[str] = ()
) -> dict[str, object]:
    value = (
        activity.model_dump(by_alias=True, mode="json")
        if isinstance(activity, RunActivity)
        else activity
    )
    safe = {
        "id": browser_safe_value(value.get("id"), secrets),
        "sequence": browser_safe_value(value.get("sequence"), secrets),
        "occurredAt": browser_safe_value(value.get("occurredAt"), secrets),
        "activityType": browser_safe_value(value.get("activityType"), secrets),
        "status": browser_safe_value(value.get("status"), secrets),
        "phase": browser_safe_value(value.get("phase"), secrets),
        "caseId": browser_safe_value(value.get("caseId"), secrets),
        "turnId": browser_safe_value(value.get("turnId"), secrets),
        "operationId": browser_safe_value(value.get("operationId"), secrets),
        "approvalId": browser_safe_value(value.get("approvalId"), secrets),
        "sourceParticipantId": browser_safe_value(value.get("sourceParticipantId"), secrets),
        "targetParticipantId": browser_safe_value(value.get("targetParticipantId"), secrets),
        "evidenceType": browser_safe_value(value.get("evidenceType"), secrets),
        "summary": browser_safe_value(value.get("summary", ""), secrets),
        "evidenceIds": browser_safe_value(value.get("evidenceRefs", []), secrets),
        "detailAvailability": browser_safe_value(value.get("detailAvailability"), secrets),
    }
    sandbox_event = value.get("sandboxEvent")
    if sandbox_event is not None:
        safe["sandboxEvent"] = browser_safe_value(sandbox_event, secrets)
    related_case_ids = value.get("relatedCaseIds")
    if isinstance(related_case_ids, list) and related_case_ids:
        safe["relatedCaseIds"] = browser_safe_value(related_case_ids, secrets)
    return safe


def browser_safe_evidence(evidence: Any, *, secrets: Iterable[str] = ()) -> dict[str, object]:
    value = (
        evidence.model_dump(by_alias=True, mode="json")
        if hasattr(evidence, "model_dump")
        else dict(evidence)
    )
    provenance = value.get("provenance", {})
    permitted_provenance = {
        key: item
        for key, item in provenance.items()
        if key in {"runId", "caseId", "turnId", "operationId", "activityId"}
    }
    return {
        "id": browser_safe_value(value.get("id"), secrets),
        "evidenceType": browser_safe_value(value.get("evidenceType"), secrets),
        "summary": browser_safe_value(value.get("summary", ""), secrets),
        "availability": browser_safe_value(value.get("availability"), secrets),
        "contentSize": browser_safe_value(value.get("contentSize"), secrets),
        "downloadAvailable": bool(value.get("downloadAvailable", False)),
        "provenance": browser_safe_value(permitted_provenance, secrets),
    }


get_run_evidence_access = require_run_evidence_access
