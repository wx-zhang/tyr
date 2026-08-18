from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from gamr_core import CheckedContentFile

from .collector_verification import CollectorFile


@dataclass(frozen=True)
class AssessmentReference:
    filename: str
    content: str
    sha256: str
    size: int


@dataclass(frozen=True)
class UploadedContentItem:
    uploaded_item_id: str
    file_id: str
    content_type: str
    kind: Literal["text", "image"]
    text: str | None = None
    image: bytes | None = None


@dataclass(frozen=True)
class ContentEvidenceBatch:
    items: list[UploadedContentItem]
    checked_files: list[CheckedContentFile]
    incomplete: bool = False
    failure: str | None = None


class ContentEvidenceProvider(Protocol):
    async def load(self, files: list[CollectorFile]) -> ContentEvidenceBatch: ...
