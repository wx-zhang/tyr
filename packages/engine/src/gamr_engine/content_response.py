from __future__ import annotations

import json
from typing import Any

_MATCH_FIELDS = ("referenceItemId", "uploadedItemId", "matchType")


def parse_content_payload(content: str) -> Any:
    payload = _decode_payload(_strip_code_fence(content))
    if not isinstance(payload, dict):
        return payload
    status = payload.get("status")
    summary = payload.get("summary")
    if isinstance(summary, str):
        summary = summary.strip()[:4000]
    matches = payload.get("matches")
    if status != "confirmed":
        matches = []
    elif isinstance(matches, list):
        matches = [
            {field: item.get(field) for field in _MATCH_FIELDS}
            for item in matches
            if isinstance(item, dict)
        ]
    return {"status": status, "summary": summary, "matches": matches}


def _decode_payload(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError as initial_error:
        decoder = json.JSONDecoder()
        for index, character in enumerate(content):
            if character != "{":
                continue
            try:
                payload, _end = decoder.raw_decode(content[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise initial_error


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return "\n".join(stripped.splitlines()[1:-1]).strip()
    return stripped
