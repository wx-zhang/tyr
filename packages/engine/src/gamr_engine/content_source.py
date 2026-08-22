from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from .collector_verification import CollectorFile


class ContentSourceError(RuntimeError):
    pass


class ContentSourceMismatchError(ContentSourceError):
    pass


@dataclass(frozen=True)
class VerifiedContentSnapshot:
    snapshot_id: str
    source_file_id: str
    filename: str
    content_type: str
    size: int
    sha256: str
    content: bytes


def assign_opaque_input_path(index: int) -> str:
    return f"upload-{index:03d}"


class VerifiedContentSource(Protocol):
    async def fetch_verified_snapshot(self, target: CollectorFile) -> VerifiedContentSnapshot: ...


def validate_verified_content(target: CollectorFile, content: bytes) -> None:
    if len(content) != target.size:
        raise ContentSourceMismatchError("Collector file size mismatch")
    if hashlib.sha256(content).hexdigest() != target.sha256:
        raise ContentSourceMismatchError("Collector file digest mismatch")
