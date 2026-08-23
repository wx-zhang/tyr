from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from gamr_core import (
    DecodingAttempt,
    DecodingLimitFlags,
    DecodingProvenance,
    DecodingStatus,
    DerivedContentFile,
)

from ..collector_verification import CollectorFile
from ..content_prepare import DerivedContentSnapshot, prepare_derived_content_evidence
from ..content_source import VerifiedContentSnapshot
from ..ports.sandbox import SandboxEntry


def prepare_decoded_output(
    *,
    entries: Sequence[SandboxEntry],
    snapshots: Sequence[VerifiedContentSnapshot],
    source: str,
    execution: object,
    attempt_number: int,
    program_digest: str,
    previous_attempts: list[DecodingAttempt],
    limit_flags: DecodingLimitFlags,
    rationale: str | None,
    attempt_builder: Any,
) -> tuple[DecodingProvenance, list[DerivedContentSnapshot]] | None:
    source_map = {
        snapshot.snapshot_id: CollectorFile(
            file_id=snapshot.source_file_id,
            filename=snapshot.filename,
            content_type=snapshot.content_type,
            size=snapshot.size,
            sha256=snapshot.sha256,
        )
        for snapshot in snapshots
    }
    derived_snapshots = [
        DerivedContentSnapshot(relative_path=entry.path, content=entry.content) for entry in entries
    ]
    collector_files = list(source_map.values())
    batch = prepare_derived_content_evidence(collector_files, source_map, derived_snapshots)
    if batch.incomplete or not batch.items:
        return None

    derived_files: list[DerivedContentFile] = []
    for item in batch.items:
        source_file = next((file for file in collector_files if file.file_id == item.file_id), None)
        if source_file is None:
            continue
        item_bytes = item.text.encode("utf-8") if item.text is not None else (item.image or b"")
        derived_files.append(
            DerivedContentFile(
                sourceFileId=item.file_id,
                uploadedItemId=item.uploaded_item_id,
                sha256=hashlib.sha256(item_bytes).hexdigest(),
                size=len(item_bytes),
                detectedContentType=item.content_type,
            )
        )
    attempt = attempt_builder(
        attempt_number=attempt_number,
        source=source,
        execution=execution,
        stage="output_validation",
        derived_files=derived_files,
    )
    provenance = DecodingProvenance(
        status=DecodingStatus.SUCCEEDED,
        action="execute",
        rationale=rationale,
        attemptCount=len(previous_attempts) + 1,
        programSha256=[item.program_sha256 for item in previous_attempts] + [program_digest],
        limitFlags=limit_flags,
        derivedFiles=derived_files,
        attempts=[*previous_attempts, attempt],
    )
    return provenance, derived_snapshots
