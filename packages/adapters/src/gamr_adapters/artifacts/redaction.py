from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

_SECRET_KEY = re.compile(
    r"(?:authorization|api[_-]?key|token|secret|password|cookie|idempotency)", re.I
)
_BEARER = re.compile(r"Bearer\s+[^\s,;]+", re.I)
_REDACTED = "[REDACTED]"
_CONTENT_OVERLAP_SUMMARY_LIMIT = 600


_DECODING_ALLOWED_KEYS = frozenset(
    {"status", "attemptCount", "failureCode", "programSha256", "limitFlags", "derivedFiles"}
)
_LIMIT_FLAGS_ALLOWED_KEYS = frozenset({"timedOut", "outputLimited"})
_DERIVED_FILE_ALLOWED_KEYS = frozenset(
    {"sourceFileId", "uploadedItemId", "sha256", "size", "detectedContentType"}
)


def _bound_decoding_provenance(decoding: dict[str, Any]) -> dict[str, Any]:
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
    return sanitized


def _bound_content_overlap(value: dict[str, Any]) -> dict[str, Any]:
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
            overlap["decoding"] = _bound_decoding_provenance(decoding)
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
        return _bound_content_overlap(redacted_mapping)
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
