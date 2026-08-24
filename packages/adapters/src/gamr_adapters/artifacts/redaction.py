from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from gamr_core.sandbox import sandbox_stream_is_safe, sanitize_sandbox_text

_SECRET_KEY = re.compile(
    r"(?:authorization|api[_-]?key|token|secret|password|cookie|idempotency)", re.I
)
_BEARER = re.compile(r"Bearer\s+[^\s,;]+", re.I)
_HOST_PATH = re.compile(
    r"/(?:tmp|private/tmp|Users|home|var/run/docker|var/folders)(?:[/\\][^\s'\"]*)?",
    re.I,
)
_REDACTED = "[REDACTED]"
_REDACTED_PATH = "[REDACTED_PATH]"
_CONTENT_OVERLAP_SUMMARY_LIMIT = 600
_DECODING_SOURCE_LIMIT = 65_536
_DECODING_STREAM_LIMIT = 16_384


_DECODING_ALLOWED_KEYS = frozenset(
    {
        "status", "action", "rationale", "attemptCount", "failureCode", "failureStage",
        "programSha256", "limitFlags", "derivedFiles", "attempts",
    }
)
_LIMIT_FLAGS_ALLOWED_KEYS = frozenset({"timedOut", "outputLimited"})
_DERIVED_FILE_ALLOWED_KEYS = frozenset(
    {"sourceFileId", "uploadedItemId", "sha256", "size", "detectedContentType"}
)
_ATTEMPT_ALLOWED_KEYS = frozenset(
    {
        "attempt", "stage", "source", "programSha256", "execution", "failureCode",
        "failureDetail", "derivedFiles",
    }
)
_EXECUTION_ALLOWED_KEYS = frozenset(
    {"exitCode", "elapsedSeconds", "timedOut", "outputLimited", "stdout", "stderr"}
)
_STREAM_ALLOWED_KEYS = frozenset({"state", "value"})
_SANDBOX_EVENT_ALLOWED_KEYS = frozenset(
    {
        "operationId",
        "owner",
        "state",
        "generation",
        "attempt",
        "programSha256",
        "source",
        "execution",
        "outputCount",
        "failureCode",
        "failureDetail",
    }
)


def _sanitize_text(value: str, secrets: tuple[str, ...], *, paths: bool = False) -> str:
    sanitized = _BEARER.sub("Bearer [REDACTED]", value)
    for secret in secrets:
        sanitized = sanitized.replace(secret, _REDACTED)
    return _HOST_PATH.sub(_REDACTED_PATH, sanitized) if paths else sanitized


def _sanitize_stream(value: Any, secrets: tuple[str, ...]) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"state": "unavailable"}
    state = value.get("state")
    if state not in {"captured", "empty", "redacted", "suppressed", "unavailable"}:
        return {"state": "unavailable"}
    if state != "captured":
        return {"state": state}
    content = value.get("value")
    if not isinstance(content, str) or not content:
        return {"state": "empty"}
    content = sanitize_sandbox_text(content[:_DECODING_STREAM_LIMIT], secrets)
    if not sandbox_stream_is_safe(content):
        return {"state": "suppressed"}
    return {"state": "captured", "value": content}


def _sanitize_attempt(attempt: Any, secrets: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(attempt, dict):
        return {}
    sanitized = {key: attempt[key] for key in _ATTEMPT_ALLOWED_KEYS if key in attempt}
    source = sanitized.get("source")
    if isinstance(source, str):
        sanitized["source"] = sanitize_sandbox_text(source[:_DECODING_SOURCE_LIMIT], secrets)
    execution = sanitized.get("execution")
    if isinstance(execution, dict):
        execution = {key: execution[key] for key in _EXECUTION_ALLOWED_KEYS if key in execution}
        execution["stdout"] = _sanitize_stream(execution.get("stdout"), secrets)
        execution["stderr"] = _sanitize_stream(execution.get("stderr"), secrets)
        sanitized["execution"] = execution
    detail = sanitized.get("failureDetail")
    if isinstance(detail, str):
        sanitized["failureDetail"] = _sanitize_text(detail[:300], secrets, paths=True)
    return sanitized


def _bound_decoding_provenance(
    decoding: dict[str, Any], secrets: tuple[str, ...] = ()
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key in _DECODING_ALLOWED_KEYS:
        if key in decoding:
            sanitized[key] = decoding[key]
    limit_flags = sanitized.get("limitFlags")
    if isinstance(limit_flags, dict):
        sanitized["limitFlags"] = {
            k: limit_flags[k] for k in _LIMIT_FLAGS_ALLOWED_KEYS if k in limit_flags
        }
    derived_files = sanitized.get("derivedFiles")
    if isinstance(derived_files, list):
        sanitized["derivedFiles"] = [
            {k: item[k] for k in _DERIVED_FILE_ALLOWED_KEYS if k in item}
            for item in derived_files
            if isinstance(item, dict)
        ]
    rationale = sanitized.get("rationale")
    if isinstance(rationale, str):
        sanitized["rationale"] = _sanitize_text(rationale[:600], secrets)
    attempts = sanitized.get("attempts")
    if isinstance(attempts, list):
        sanitized["attempts"] = [_sanitize_attempt(item, secrets) for item in attempts[:3]]
    return sanitized


def _bound_sandbox_event(value: Any, secrets: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    sanitized = {key: value[key] for key in _SANDBOX_EVENT_ALLOWED_KEYS if key in value}
    source = sanitized.get("source")
    if isinstance(source, dict):
        source = dict(source)
        if source.get("state") == "captured" and isinstance(source.get("value"), str):
            source["value"] = sanitize_sandbox_text(
                source["value"][:_DECODING_SOURCE_LIMIT], secrets
            )
        sanitized["source"] = source
    execution = sanitized.get("execution")
    if isinstance(execution, dict):
        execution = {key: execution[key] for key in _EXECUTION_ALLOWED_KEYS if key in execution}
        execution["stdout"] = _sanitize_stream(execution.get("stdout"), secrets)
        execution["stderr"] = _sanitize_stream(execution.get("stderr"), secrets)
        sanitized["execution"] = execution
    detail = sanitized.get("failureDetail")
    if isinstance(detail, str):
        sanitized["failureDetail"] = _sanitize_text(detail[:300], secrets, paths=True)
    return sanitized


def _bound_content_overlap(value: dict[str, Any], secrets: tuple[str, ...]) -> dict[str, Any]:
    for key in ("contentOverlap", "content_overlap"):
        overlap = value.get(key)
        if not isinstance(overlap, dict):
            continue
        summary = overlap.get("summary")
        if isinstance(summary, str) and len(summary) > _CONTENT_OVERLAP_SUMMARY_LIMIT:
            overlap.setdefault("fullSummary", summary)
            overlap["summary"] = summary[:_CONTENT_OVERLAP_SUMMARY_LIMIT]
        decoding = overlap.get("decoding")
        if isinstance(decoding, dict):
            overlap["decoding"] = _bound_decoding_provenance(decoding, secrets)
    sandbox_event = value.get("sandboxEvent")
    if isinstance(sandbox_event, dict):
        value["sandboxEvent"] = _bound_sandbox_event(sandbox_event, secrets)
    return value


def redact_payload(value: Any, secrets: Iterable[str] = ()) -> Any:
    configured = tuple(secret for secret in secrets if secret)
    if isinstance(value, dict):
        redacted_mapping = {
            str(key): _REDACTED
            if _SECRET_KEY.search(str(key))
            else redact_payload(item, configured)
            for key, item in value.items()
        }
        return _bound_content_overlap(redacted_mapping, configured)
    if isinstance(value, list):
        return [redact_payload(item, configured) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item, configured) for item in value]
    if isinstance(value, str):
        redacted: str = _BEARER.sub("Bearer [REDACTED]", value)
        for secret in configured:
            redacted = redacted.replace(secret, _REDACTED)
        return redacted
    return value
