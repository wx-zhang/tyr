from __future__ import annotations

import hashlib
from typing import Protocol

import pytest
from gamr_engine.collector_verification import CollectorFile
from gamr_engine.content_source import (
    ContentSourceError,
    ContentSourceMismatchError,
    VerifiedContentSnapshot,
    VerifiedContentSource,
    assign_opaque_input_path,
)


def _file(
    file_id: str = "file-1",
    filename: str = "evidence.txt",
    content_type: str = "text/plain",
    content: bytes = b"test content",
) -> CollectorFile:
    return CollectorFile(
        file_id=file_id,
        filename=filename,
        content_type=content_type,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


@pytest.mark.asyncio
async def test_verified_content_source_downloads_once_and_returns_opaque_snapshot() -> None:
    content = b"sensitive payload data"
    file = _file(file_id="collector-file-abc", filename="stolen.txt", content=content)

    download_count = 0

    class FakeSource(VerifiedContentSource):
        async def fetch_verified_snapshot(self, target: CollectorFile) -> VerifiedContentSnapshot:
            nonlocal download_count
            download_count += 1
            if len(content) != target.size or hashlib.sha256(content).hexdigest() != target.sha256:
                raise ContentSourceMismatchError("Size or digest mismatch")
            return VerifiedContentSnapshot(
                snapshot_id="upload-001",
                source_file_id=target.file_id,
                filename=target.filename,
                content_type=target.content_type,
                size=target.size,
                sha256=target.sha256,
                content=content,
            )

    source = FakeSource()
    snapshot = await source.fetch_verified_snapshot(file)

    assert download_count == 1
    assert snapshot.snapshot_id == "upload-001"
    assert snapshot.source_file_id == "collector-file-abc"
    assert snapshot.filename == "stolen.txt"
    assert snapshot.content_type == "text/plain"
    assert snapshot.size == len(content)
    assert snapshot.sha256 == hashlib.sha256(content).hexdigest()
    assert snapshot.content == content

    # Check snapshot does not carry url, credentials, reference, or host path attributes
    assert not hasattr(snapshot, "url")
    assert not hasattr(snapshot, "credentials")
    assert not hasattr(snapshot, "reference")
    assert not hasattr(snapshot, "host_path")


@pytest.mark.asyncio
async def test_verified_content_source_rejects_size_mismatch() -> None:
    content = b"short"
    file = CollectorFile(
        file_id="file-1",
        filename="evidence.txt",
        content_type="text/plain",
        size=100,  # mismatch
        sha256=hashlib.sha256(content).hexdigest(),
    )

    class FakeSource(VerifiedContentSource):
        async def fetch_verified_snapshot(self, target: CollectorFile) -> VerifiedContentSnapshot:
            if len(content) != target.size or hashlib.sha256(content).hexdigest() != target.sha256:
                raise ContentSourceMismatchError("Collector file size mismatch")
            return VerifiedContentSnapshot(
                snapshot_id="upload-001",
                source_file_id=target.file_id,
                filename=target.filename,
                content_type=target.content_type,
                size=target.size,
                sha256=target.sha256,
                content=content,
            )

    source = FakeSource()
    with pytest.raises(ContentSourceMismatchError, match="size"):
        await source.fetch_verified_snapshot(file)


@pytest.mark.asyncio
async def test_verified_content_source_rejects_digest_mismatch() -> None:
    content = b"real content"
    file = CollectorFile(
        file_id="file-1",
        filename="evidence.txt",
        content_type="text/plain",
        size=len(content),
        sha256="0" * 64,  # mismatch
    )

    class FakeSource(VerifiedContentSource):
        async def fetch_verified_snapshot(self, target: CollectorFile) -> VerifiedContentSnapshot:
            if len(content) != target.size or hashlib.sha256(content).hexdigest() != target.sha256:
                raise ContentSourceMismatchError("Collector file digest mismatch")
            return VerifiedContentSnapshot(
                snapshot_id="upload-001",
                source_file_id=target.file_id,
                filename=target.filename,
                content_type=target.content_type,
                size=target.size,
                sha256=target.sha256,
                content=content,
            )

    source = FakeSource()
    with pytest.raises(ContentSourceMismatchError, match="digest"):
        await source.fetch_verified_snapshot(file)


def test_assign_opaque_input_path() -> None:
    assert assign_opaque_input_path(1) == "upload-001"
    assert assign_opaque_input_path(42) == "upload-042"
