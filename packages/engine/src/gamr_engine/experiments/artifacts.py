from __future__ import annotations

import re
from datetime import UTC, datetime

from gamr_core import CaseResult, DiscoveryCandidate, Scenario

from ..ports.artifacts import ArtifactStore
from .records import PhaseResult

_UNSAFE_ID_CHAR = re.compile(r"[^A-Za-z0-9_-]+")


def scientist_artifact_id(scenario_id: str) -> str:
    return _UNSAFE_ID_CHAR.sub("-", scenario_id)[:128] or "scenario"


def write_raw(
    artifacts: ArtifactStore | None,
    run_id: str,
    turn_id: str,
    payload: dict[str, object],
) -> None:
    if artifacts is not None:
        artifacts.write_raw(run_id, turn_id, payload)


def write_checkpoint(
    artifacts: ArtifactStore | None, run_id: str, payload: dict[str, object]
) -> None:
    if artifacts is not None:
        artifacts.write_checkpoint(run_id, payload)


def write_scenario(artifacts: ArtifactStore | None, run_id: str, scenario: Scenario) -> None:
    if artifacts is None:
        return
    safe_id = scientist_artifact_id(scenario.metadata.id)
    artifacts.write_json(
        f"runs/{run_id}/scientist-scenarios/{safe_id}.json",
        scenario.model_dump(by_alias=True, exclude_none=True, mode="json"),
    )


def write_transcript(
    artifacts: ArtifactStore | None,
    run_id: str,
    records: list[dict[str, object]],
) -> None:
    if artifacts is None:
        return
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    stamped = []
    for record in records:
        item = dict(record)
        item.setdefault("occurredAt", now)
        stamped.append(item)
    artifacts.append_transcript(run_id, stamped)


def write_event(
    artifacts: ArtifactStore | None, run_id: str, payload: dict[str, object]
) -> None:
    if artifacts is not None:
        artifacts.append_event(run_id, payload)


def discovery_fields(candidate: DiscoveryCandidate) -> tuple[tuple[str, str], ...]:
    return (
        ("path", candidate.path),
        ("workspace", candidate.workspace),
        ("agent", candidate.agent),
        ("bridgeId", candidate.bridge_id),
    )


def write_discovery_result(
    artifacts: ArtifactStore | None,
    run_id: str,
    result: PhaseResult,
) -> None:
    if artifacts is None or not hasattr(artifacts, "write_json"):
        return
    occurred_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if result.candidates:
        fields = [
            {"name": name, "value": value}
            for name, value in discovery_fields(result.candidates[0])
        ]
        payload: dict[str, object] = {
            "status": "found",
            "candidateCount": len(result.candidates),
            "fields": fields,
            "targetOrigin": result.target_origin.value,
            "occurredAt": occurred_at,
        }
    else:
        payload = {
            "status": "blocked",
            "candidateCount": 0,
            "fields": [],
            "targetOrigin": result.target_origin.value,
            "reason": result.error or "blocked",
            "occurredAt": occurred_at,
        }
    artifacts.write_json(f"runs/{run_id}/discovery-result.json", payload)


def write_case_result(
    artifacts: ArtifactStore | None,
    run_id: str,
    case: CaseResult,
    *,
    stage: str,
) -> None:
    if artifacts is None or not hasattr(artifacts, "write_json"):
        return
    safe_id = _UNSAFE_ID_CHAR.sub("-", case.scenario_execution_id)[:128] or "scenario-execution"
    payload = case.model_dump(by_alias=True, exclude_none=True, mode="json")
    payload["stage"] = "scientist" if stage == "scientist" else "scenario_execution"
    payload["occurredAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    artifacts.write_json(f"runs/{run_id}/scenario-execution-results/{safe_id}.json", payload)
    legacy_id = _UNSAFE_ID_CHAR.sub("-", case.scenario_id)[:128] or "case"
    legacy_payload = dict(payload)
    legacy_payload["stage"] = "scientist" if stage == "scientist" else "case"
    artifacts.write_json(f"runs/{run_id}/case-results/{legacy_id}.json", legacy_payload)


def turn_ids(transcript: list[dict[str, str]]) -> list[str]:
    return list(dict.fromkeys(item["turnId"] for item in transcript if "turnId" in item))
