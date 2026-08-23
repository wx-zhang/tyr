from __future__ import annotations

from ..collector_verification import CollectorFile
from ..content_prepare import prepare_content_evidence
from ..content_source import VerifiedContentSnapshot


def originals_are_directly_readable(snapshots: list[VerifiedContentSnapshot]) -> bool:
    files = [
        CollectorFile(
            snapshot.source_file_id,
            snapshot.filename,
            snapshot.content_type,
            snapshot.size,
            snapshot.sha256,
        )
        for snapshot in snapshots
    ]
    evidence = prepare_content_evidence(files, snapshots)
    return bool(evidence.items) and not evidence.incomplete
