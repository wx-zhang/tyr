from __future__ import annotations

from collections.abc import Awaitable, Callable

from gamr_engine.collector_verification import CollectorFile
from gamr_engine.content_evidence import ContentEvidenceBatch
from gamr_engine.content_prepare import MAX_FILES, MAX_IMAGE_BYTES, checked_content_file, prepare_content_evidence
from gamr_engine.content_source import VerifiedContentSnapshot


async def prepare_uploaded_content(
    files: list[CollectorFile],
    download: Callable[[CollectorFile], Awaitable[bytes]],
) -> ContentEvidenceBatch:
    checked = [checked_content_file(file) for file in files[:MAX_FILES]]
    if len(files) > MAX_FILES:
        return ContentEvidenceBatch([], checked, True, "too_many_files")
    snapshots: list[VerifiedContentSnapshot] = []
    incomplete = False
    failure = None
    for index, file in enumerate(files, 1):
        if file.size > MAX_IMAGE_BYTES:
            incomplete = True
            failure = failure or "content_file_too_large"
            continue
        try:
            content = await download(file)
            snapshots.append(
                VerifiedContentSnapshot(
                    snapshot_id=f"upload-{index:03d}",
                    source_file_id=file.file_id,
                    filename=file.filename,
                    content_type=file.content_type,
                    size=file.size,
                    sha256=file.sha256,
                    content=content,
                )
            )
        except Exception:
            incomplete = True
            failure = failure or "content_download_failed"
    batch = prepare_content_evidence(files, snapshots)
    if incomplete and not batch.incomplete:
        return ContentEvidenceBatch(batch.items, batch.checked_files, True, failure)
    return batch
