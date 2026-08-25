from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gamr_core import (
    AssessmentStatus,
    CheckedContentFile,
    ContentOverlapResult,
    ContentOverlapStatus,
)
from gamr_engine.collector_verification import CollectorFile, CollectorVerification
from gamr_engine.content_source import (
    VerifiedContentSnapshot,
    assign_opaque_input_path,
    validate_verified_content,
)

from ..contracts import JudgeRequest, JudgeRuntime

if TYPE_CHECKING:
    from .pipeline import PipelineState


def extract_collector_files(
    verifications: list[CollectorVerification],
) -> tuple[list[CollectorFile], bool]:
    files: list[CollectorFile] = []
    seen: set[tuple[str, str]] = set()
    digests_by_id: dict[str, str] = {}
    has_conflict = False
    for verification in verifications:
        if verification.status != "verified":
            continue
        for file in verification.files:
            previous = digests_by_id.get(file.file_id)
            if previous is not None and previous != file.sha256:
                has_conflict = True
            digests_by_id[file.file_id] = file.sha256
            key = (file.file_id, file.sha256)
            if key not in seen:
                files.append(file)
                seen.add(key)
    return files, has_conflict


async def prepare_verified_content(state: PipelineState) -> dict[str, Any]:
    request: JudgeRequest = state["request"]
    runtime: JudgeRuntime = state["runtime"]

    reference = request.assessment_reference
    if reference is None or request.scenario.spec.collector_evidence != "file":
        return {
            "applicable": False,
            "collector_files": [],
            "verified_snapshots": [],
            "preparation_error": None,
        }

    files, has_conflict = extract_collector_files(request.verifications)
    checked = [
        CheckedContentFile(
            fileId=f.file_id,
            filename=f.filename,
            contentType=f.content_type,
            size=f.size,
            sha256=f.sha256,
        )
        for f in files
    ]

    if has_conflict:
        return {
            "applicable": True,
            "collector_files": files,
            "verified_snapshots": [],
            "preparation_error": "conflicting_collector_file_metadata",
            "content_overlap": ContentOverlapResult(
                status=ContentOverlapStatus.INCONCLUSIVE,
                assessmentStatus=AssessmentStatus.FAILED,
                failure="conflicting_collector_file_metadata",
                referenceSha256=f"sha256:{reference.sha256}",
                checkedFiles=checked,
            ),
        }

    if not files:
        return {
            "applicable": True,
            "collector_files": [],
            "verified_snapshots": [],
            "preparation_error": "collector_file_unavailable",
            "content_overlap": ContentOverlapResult(
                status=ContentOverlapStatus.INCONCLUSIVE,
                assessmentStatus=AssessmentStatus.FAILED,
                failure="collector_file_unavailable",
                referenceSha256=f"sha256:{reference.sha256}",
                checkedFiles=checked,
            ),
        }

    source = runtime.verified_content_source
    if source is None:
        return {
            "applicable": True,
            "collector_files": files,
            "verified_snapshots": [],
            "preparation_error": "preparation_failure",
            "content_overlap": ContentOverlapResult(
                status=ContentOverlapStatus.INCONCLUSIVE,
                assessmentStatus=AssessmentStatus.FAILED,
                failure="preparation_failure",
                referenceSha256=f"sha256:{reference.sha256}",
                checkedFiles=checked,
            ),
        }

    snapshots: list[VerifiedContentSnapshot] = []
    try:
        for idx, file in enumerate(files, 1):
            snapshot = await source.fetch_verified_snapshot(file)
            validate_verified_content(file, snapshot.content)
            opaque_id = assign_opaque_input_path(idx)
            if snapshot.snapshot_id != opaque_id:
                snapshot = VerifiedContentSnapshot(
                    snapshot_id=opaque_id,
                    source_file_id=snapshot.source_file_id,
                    filename=snapshot.filename,
                    content_type=snapshot.content_type,
                    size=snapshot.size,
                    sha256=snapshot.sha256,
                    content=snapshot.content,
                )
            snapshots.append(snapshot)
    except Exception:
        return {
            "applicable": True,
            "collector_files": files,
            "verified_snapshots": [],
            "preparation_error": "preparation_failure",
            "content_overlap": ContentOverlapResult(
                status=ContentOverlapStatus.INCONCLUSIVE,
                assessmentStatus=AssessmentStatus.FAILED,
                failure="preparation_failure",
                referenceSha256=f"sha256:{reference.sha256}",
                checkedFiles=checked,
            ),
        }

    return {
        "applicable": True,
        "collector_files": files,
        "verified_snapshots": snapshots,
        "preparation_error": None,
    }
