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


def _bound_content_overlap(value: dict[str, Any]) -> dict[str, Any]:
    for key in ("contentOverlap", "content_overlap"):
        overlap = value.get(key)
        if not isinstance(overlap, dict):
            continue
        summary = overlap.get("summary")
        if isinstance(summary, str) and len(summary) > _CONTENT_OVERLAP_SUMMARY_LIMIT:
            overlap.setdefault("fullSummary", summary)
            overlap["summary"] = summary[:_CONTENT_OVERLAP_SUMMARY_LIMIT]
    return value


def redact_payload(value: Any, secrets: Iterable[str] = ()) -> Any:
    configured = tuple(secret for secret in secrets if secret)
    if isinstance(value, dict):
        redacted = {
            str(key): _REDACTED
            if _SECRET_KEY.search(str(key))
            else redact_payload(item, configured)
            for key, item in value.items()
        }
        return _bound_content_overlap(redacted)
    if isinstance(value, list):
        return [redact_payload(item, configured) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item, configured) for item in value]
    if isinstance(value, str):
        redacted = _BEARER.sub("Bearer [REDACTED]", value)
        for secret in configured:
            redacted = redacted.replace(secret, _REDACTED)
        return redacted
    return value
