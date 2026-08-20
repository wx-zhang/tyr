from __future__ import annotations

from gamr_core import (
    AssessmentReasonCode,
    AssessmentStatus,
    CheckedContentFile,
    ContentOverlapResult,
    ContentOverlapStatus,
)

from .collector_verification import CollectorVerification
from .content_assessment import ContentAssessmentOutcome, ContentAssessmentService
from .content_evidence import AssessmentReference, ContentEvidenceProvider
from .ports.models import ModelGateway


class ContentAssessmentPipeline:
    def __init__(self, provider: ContentEvidenceProvider | None) -> None:
        self.provider = provider
        self.service = ContentAssessmentService()

    async def assess(
        self,
        reference: AssessmentReference,
        verifications: list[CollectorVerification],
        model: ModelGateway,
    ) -> ContentAssessmentOutcome:
        files = []
        seen: set[tuple[str, str]] = set()
        conflicting_ids: set[str] = set()
        digests_by_id: dict[str, str] = {}
        for verification in verifications:
            if verification.status != "verified":
                continue
            for file in verification.files:
                previous = digests_by_id.get(file.file_id)
                if previous is not None and previous != file.sha256:
                    conflicting_ids.add(file.file_id)
                digests_by_id[file.file_id] = file.sha256
                key = (file.file_id, file.sha256)
                if key not in seen:
                    files.append(file)
                    seen.add(key)
        checked = [
            CheckedContentFile(
                fileId=file.file_id,
                filename=file.filename,
                contentType=file.content_type,
                size=file.size,
                sha256=file.sha256,
            )
            for file in files
        ]
        if conflicting_ids:
            return _unavailable(reference, checked, "conflicting_collector_file_metadata")
        if not files:
            return _unavailable(reference, checked, "collector_file_unavailable")
        if self.provider is None:
            return _unavailable(reference, checked, "content_provider_unavailable")
        try:
            evidence = await self.provider.load(files)
            return await self.service.assess(reference=reference, evidence=evidence, model=model)
        except Exception:
            return _unavailable(reference, checked, "content_preparation_failed")


def content_assessment_context(
    content_overlap: ContentOverlapResult | None,
) -> tuple[list[AssessmentReasonCode], list[str]]:
    if content_overlap is None:
        return [], []
    if content_overlap.status is ContentOverlapStatus.CONFIRMED:
        return [AssessmentReasonCode.REFERENCE_CONTENT_OVERLAP], []
    if content_overlap.status is ContentOverlapStatus.NOT_FOUND:
        return [AssessmentReasonCode.REFERENCE_CONTENT_NOT_FOUND], [
            "Evidence of reference-content exposure is absent."
        ]
    return [AssessmentReasonCode.REFERENCE_CONTENT_UNAVAILABLE], [
        "Reference-content comparison is unavailable."
    ]


def _unavailable(
    reference: AssessmentReference,
    checked: list[CheckedContentFile],
    failure: str,
) -> ContentAssessmentOutcome:
    result = ContentOverlapResult(
        status=ContentOverlapStatus.INCONCLUSIVE,
        assessmentStatus=AssessmentStatus.FAILED,
        failure=failure,
        referenceSha256=f"sha256:{reference.sha256}",
        checkedFiles=checked,
    )
    return ContentAssessmentOutcome(
        result,
        {"status": AssessmentStatus.FAILED.value, "failure": failure, "attempts": []},
    )
