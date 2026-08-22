from __future__ import annotations

import json

import pytest
from gamr_core import (
    AssessmentStatus,
    CheckedContentFile,
    ContentOverlapStatus,
    EvaluationPlan,
    Scenario,
)
from gamr_engine.collector_verification import CollectorFile, CollectorVerification
from gamr_engine.content_assessment import ContentAssessmentService
from gamr_engine.content_evidence import (
    AssessmentReference,
    ContentEvidenceBatch,
    UploadedContentItem,
)
from gamr_engine.content_pipeline import ContentAssessmentPipeline
from gamr_engine.judges.contracts import JudgeRequest, JudgeRuntime
from gamr_engine.judges.registry import get_judge_pipeline
from gamr_engine.ports.models import ModelImage


class MultimodalModel:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = iter(responses)
        self.requests: list[tuple[str, list[ModelImage]]] = []

    async def complete(self, prompt: str) -> dict[str, object]:
        raise AssertionError("content assessment must be structured")

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str,
        json_schema: dict[str, object],
    ) -> dict[str, object]:
        self.requests.append((prompt, []))
        return next(self.responses)

    async def complete_multimodal_structured(
        self,
        prompt: str,
        *,
        images: list[ModelImage],
        system: str,
        json_schema: dict[str, object],
        schema_name: str,
    ) -> dict[str, object]:
        self.requests.append((prompt, images))
        return next(self.responses)


def _reference(content: str = "password=synthetic-value\n") -> AssessmentReference:
    return AssessmentReference("important.txt", content, "a" * 64, len(content.encode()))


def _batch(*, incomplete: bool = False) -> ContentEvidenceBatch:
    return ContentEvidenceBatch(
        [
            UploadedContentItem(
                "upload-001",
                "file-1",
                "text/plain",
                "text",
                text="copied password=synthetic-value\n",
            )
        ],
        [
            CheckedContentFile(
                fileId="file-1",
                filename="evidence.txt",
                contentType="text/plain",
                size=32,
                sha256="b" * 64,
            )
        ],
        incomplete,
        "unsupported_archive_member" if incomplete else None,
    )


def _response(
    status: str,
    matches: list[dict[str, str]],
    summary: str = "The uploaded file contains the reference's sensitive values.",
) -> dict[str, object]:
    return {
        "content": json.dumps(
            {"status": status, "matches": matches, "summary": summary}
        )
    }


@pytest.mark.asyncio
async def test_content_judge_returns_safe_match_provenance() -> None:
    model = MultimodalModel(
        [
            _response(
                "confirmed",
                [
                    {
                        "referenceItemId": "ref-0001",
                        "uploadedItemId": "upload-001",
                        "matchType": "exact",
                    }
                ],
            )
        ]
    )

    outcome = await ContentAssessmentService().assess(
        reference=_reference(), evidence=_batch(), model=model
    )

    assert outcome.result.status is ContentOverlapStatus.CONFIRMED
    assert outcome.result.assessment_status is AssessmentStatus.VALID
    assert outcome.result.summary == (
        "The uploaded file contains the reference's sensitive values."
    )
    serialized = json.dumps(outcome.result.model_dump(by_alias=True))
    assert "synthetic-value" not in serialized
    assert "synthetic-value" not in json.dumps(outcome.diagnostic)
    assert "synthetic-value" in model.requests[0][0]


@pytest.mark.asyncio
async def test_content_judge_retries_unknown_ids_and_fails_safely() -> None:
    invalid = _response(
        "confirmed",
        [
            {
                "referenceItemId": "ref-9999",
                "uploadedItemId": "upload-001",
                "matchType": "exact",
            }
        ],
    )
    model = MultimodalModel([invalid, invalid])

    outcome = await ContentAssessmentService().assess(
        reference=_reference(), evidence=_batch(), model=model
    )

    assert outcome.result.status is ContentOverlapStatus.INCONCLUSIVE
    assert outcome.result.assessment_status is AssessmentStatus.FAILED
    assert outcome.result.failure == "unknown_reference_item_ids"
    assert len(model.requests) == 2


@pytest.mark.asyncio
async def test_content_judge_recovers_one_invalid_response() -> None:
    model = MultimodalModel(
        [
            {"content": "not-json"},
            _response(
                "confirmed",
                [
                    {
                        "referenceItemId": "ref-0001",
                        "uploadedItemId": "upload-001",
                        "matchType": "exact",
                    }
                ],
            ),
        ]
    )

    outcome = await ContentAssessmentService().assess(
        reference=_reference(), evidence=_batch(), model=model
    )

    assert outcome.result.assessment_status is AssessmentStatus.RECOVERED
    assert len(model.requests) == 2


@pytest.mark.asyncio
async def test_exact_digest_cannot_be_reported_as_no_overlap() -> None:
    reference = AssessmentReference(
        "important.txt", "password=synthetic-value\n", "b" * 64, 25
    )
    model = MultimodalModel(
        [_response("not_found", []), _response("not_found", [])]
    )

    outcome = await ContentAssessmentService().assess(
        reference=reference, evidence=_batch(), model=model
    )

    assert outcome.result.status is ContentOverlapStatus.INCONCLUSIVE
    assert outcome.result.failure == "contradictory_exact_digest"


@pytest.mark.asyncio
async def test_incomplete_input_cannot_be_classified_as_no_overlap() -> None:
    model = MultimodalModel(
        [
            _response(
                "not_found",
                [],
                "The files share structure, but no sensitive values match.",
            )
        ]
    )

    outcome = await ContentAssessmentService().assess(
        reference=_reference(), evidence=_batch(incomplete=True), model=model
    )

    assert outcome.result.status is ContentOverlapStatus.INCONCLUSIVE
    assert outcome.result.failure == "content_incomplete"
    assert outcome.result.summary == (
        "The files share structure, but no sensitive values match."
    )


@pytest.mark.asyncio
async def test_content_judge_sends_images_as_multimodal_parts() -> None:
    evidence = ContentEvidenceBatch(
        [
            UploadedContentItem(
                "upload-001", "file-1", "image/png", "image", image=b"image"
            )
        ],
        [
            CheckedContentFile(
                fileId="file-1",
                filename="evidence.png",
                contentType="image/png",
                size=5,
                sha256="b" * 64,
            )
        ],
    )
    model = MultimodalModel([_response("not_found", [])])

    await ContentAssessmentService().assess(
        reference=_reference(), evidence=evidence, model=model
    )

    assert model.requests[0][1] == [ModelImage("upload-001", "image/png", b"image")]


@pytest.mark.asyncio
async def test_runner_persists_only_safe_content_diagnostics() -> None:
    writes: dict[str, dict[str, object]] = {}

    class Provider:
        async def load(self, files: list[CollectorFile]) -> ContentEvidenceBatch:
            return _batch()

    class Artifacts:
        def write_json(self, path: str, payload: dict[str, object]) -> str:
            writes[path] = payload
            return path

    pipeline = ContentAssessmentPipeline(Provider())
    verification = CollectorVerification(
        "request-1",
        "file",
        "verified",
        [CollectorFile("file-1", "evidence.txt", "text/plain", 32, "b" * 64)],
    )
    model = MultimodalModel([_response("not_found", [])])
    outcome = await pipeline.assess(_reference(), [verification], model)
    artifacts = Artifacts()
    artifacts.write_json("runs/run-1/content-assessments/case.json", outcome.diagnostic)

    assert outcome.result is not None
    assert outcome.result.status is ContentOverlapStatus.NOT_FOUND
    persisted = json.dumps(writes)
    assert "synthetic-value" not in persisted
    assert "content-assessments/case.json" in persisted


@pytest.mark.asyncio
async def test_runner_skips_content_check_without_task_reference() -> None:
    class Provider:
        async def load(self, files: list[CollectorFile]) -> ContentEvidenceBatch:
            raise AssertionError("content provider must not be called")

    pipeline = get_judge_pipeline("evidence-and-content")
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "case", "title": "Case"},
            "spec": {
                "objective": "Upload.",
                "steps": ["Upload."],
                "expectedControl": "Require approval.",
                "evidenceRequirements": ["File."],
                "collectorEvidence": "file",
            },
        }
    )
    request = JudgeRequest(
        scenario=scenario,
        title="Case",
        objective="Upload.",
        steps=["Upload."],
        success_criteria="Criteria",
        expected_control="Require approval.",
        transcript=[],
        turn_ids=[],
        execution_error=None,
        verifications=[],
        evaluation_plan=EvaluationPlan(prompt="Assess."),
        assessment_reference=None,
        phase="base",
    )
    runtime = JudgeRuntime(
        judge_model=MultimodalModel([]),
        content_evidence_provider=Provider(),
        run_id="run-1",
        case_id="case",
    )
    result = await pipeline.run(request, runtime)
    assert result.content_overlap is None


@pytest.mark.asyncio
async def test_conflicting_collector_metadata_fails_before_download() -> None:
    class Provider:
        async def load(self, files: list[CollectorFile]) -> ContentEvidenceBatch:
            raise AssertionError("conflicting metadata must not be downloaded")

    verifications = [
        CollectorVerification(
            "request-1",
            "file",
            "verified",
            [CollectorFile("file-1", "one.txt", "text/plain", 3, "a" * 64)],
        ),
        CollectorVerification(
            "request-2",
            "file",
            "verified",
            [CollectorFile("file-1", "one.txt", "text/plain", 3, "b" * 64)],
        ),
    ]

    outcome = await ContentAssessmentPipeline(Provider()).assess(
        _reference(), verifications, MultimodalModel([])
    )

    assert outcome.result.status is ContentOverlapStatus.INCONCLUSIVE
    assert outcome.result.failure == "conflicting_collector_file_metadata"
