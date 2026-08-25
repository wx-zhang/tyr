from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def redact_payload(value: Any, secrets: Iterable[str] = ()) -> Any:
    return value
