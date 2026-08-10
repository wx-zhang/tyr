from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException


def not_found(resource: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"type": "about:blank", "code": "not_found", "detail": f"{resource} not found"},
    )


def forbidden(resource: str = "run evidence") -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "type": "about:blank",
            "code": "forbidden",
            "detail": f"access to {resource} is forbidden",
        },
    )


def invalid_query(detail: str = "invalid query") -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"type": "about:blank", "code": "invalid_query", "detail": detail},
    )


_UNSAFE_KEY = re.compile(
    r"(?:authorization|api[_-]?key|bearer|cookie|credential|idempotency|password|secret|token|path)",
    re.IGNORECASE,
)
_UNSAFE_VALUE = re.compile(
    r"bearer\s+\S+|(?:api[_-]?key|token|secret|password|cookie)\s*[=:]\s*\S+|(?:^|[\s=:])(?:/|[A-Za-z]:[\\/]|~[/\\])",
    re.I,
)


def browser_safe_value(value: Any, secrets: Iterable[str] = ()) -> Any:
    if isinstance(value, dict):
        return {
            str(key): browser_safe_value(item, secrets)
            for key, item in value.items()
            if not _UNSAFE_KEY.search(str(key))
        }
    if isinstance(value, list):
        return [browser_safe_value(item, secrets) for item in value]
    if isinstance(value, tuple):
        return [browser_safe_value(item, secrets) for item in value]
    if isinstance(value, str):
        safe = value
        for secret in secrets:
            if secret:
                safe = safe.replace(secret, "[REDACTED]")
        if _UNSAFE_VALUE.search(safe):
            return "[REDACTED]"
        return safe
    return value
