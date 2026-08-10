from __future__ import annotations

import uuid


def new_id() -> str:
    """Return a stable string identifier; use UUIDv7 when the runtime provides it."""

    uuid7 = getattr(uuid, "uuid7", None)
    return str(uuid7() if uuid7 is not None else uuid.uuid4())
