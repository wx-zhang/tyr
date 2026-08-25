from __future__ import annotations

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


def conflict(code: str, detail: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"type": "about:blank", "code": code, "detail": detail},
    )


def browser_safe_value(value: Any, secrets: Iterable[str] = ()) -> Any:
    if isinstance(value, dict):
        return {
            str(key): browser_safe_value(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [browser_safe_value(item, secrets) for item in value]
    if isinstance(value, tuple):
        return [browser_safe_value(item, secrets) for item in value]
    return value
