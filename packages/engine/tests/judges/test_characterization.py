from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from gamr_core import (
    AssessmentReasonCode,
    AssessmentStatus,
    CheckedContentFile,
    ContentOverlapStatus,
    DecodingProvenance,
    DecodingStatus,
    EvaluationPlan,
    EvaluationReference,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
)
from gamr_engine.collector_verification import CollectorFile, CollectorVerification
from gamr_engine.content_evidence import AssessmentReference
from gamr_engine.content_source import VerifiedContentSnapshot, VerifiedContentSource
from gamr_engine.judges.contracts import JudgeRequest, JudgeRuntime
from gamr_engine.judges.registry import get_judge_pipeline
from gamr_engine.ports.sandbox import ExecutionResult, Sandbox, SandboxEntry, SandboxId


class TrackingJudgeModel:
    def __init__(
        self,
        *,
        chat_responses: list[dict[str, Any]] | None = None,
        structured_responses: list[dict[str, Any]] | None = None,
        complete_responses: list[str] | None = None,
    ) -> None:
        self.chat_responses = list(chat_responses or [])
        self.structured_responses = list(structured_responses or [])
        self.complete_responses = list(complete_responses or [])
        self.chat_calls: list[list[dict[str, Any]]] = []
        self.structured_calls: list[str] = []
        self.complete_calls: list[str] = []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        self.chat_calls.append(messages)
        if self.chat_responses:
            return self.chat_responses.pop(0)
        return {"message": {"role": "assistant", "content": '{"action":"direct"}'}}

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.structured_calls.append(prompt)
        if self.structured_responses:
            return self.structured_responses.pop(0)
        return {
            "content": json.dumps(
                {
                    "objectiveStatus": "achieved",
                    "verdict": "vulnerable",
                    "summary": "Overlap found.",
                    "evidenceTurnIds": ["turn-1"],
                    "reasonCodes": ["side_effect_without_approval"],
                    "missingEvidence": [],
                }
            )
        }

    async def complete(self, prompt: str) -> dict[str, Any]:
        self.complete_calls.append(prompt)
        if self.complete_responses:
            return {"content": self.complete_responses.pop(0)}
        return {
            "content": json.dumps(
                {
                    "objectiveStatus": "achieved",
                    "verdict": "vulnerable",
                    "summary": "Completed.",
                    "evidenceTurnIds": ["turn-1"],
                    "reasonCodes": ["side_effect_without_approval"],
                    "missingEvidence": [],
                }
            )
        }


class TrackingSandbox(Sandbox):
    def __init__(self) -> None:
        self.started_entries: list[list[SandboxEntry]] = []
        self.executed_sources: list[str] = []
        self.collected_dirs: list[str] = []
        self.closed_ids: list[SandboxId] = []

    @property
    def isolation(self) -> str:
        return "contained"

    async def start(self, entries: list[SandboxEntry] = []) -> SandboxId:
        self.started_entries.append(entries)
        return SandboxId("sandbox-1")

    async def execute(self, sandbox_id: SandboxId, source: str | bytes) -> ExecutionResult:
        self.executed_sources.append(str(source))
        return ExecutionResult(0, "success", "", 0.1)

    async def collect_output(self, sandbox_id: SandboxId, output_dir: str) -> list[SandboxEntry]:
        self.collected_dirs.append(output_dir)
        return []

    async def close(self, sandbox_id: SandboxId) -> None:
        self.closed_ids.append(sandbox_id)


class TrackingVerifiedContentSource(VerifiedContentSource):
    def __init__(self, contents: dict[str, bytes] | None = None) -> None:
        self.contents = contents or {}
        self.fetch_calls: list[str] = []

    async def fetch_verified_snapshot(self, target: CollectorFile) -> VerifiedContentSnapshot:
        self.fetch_calls.append(target.file_id)
        content = self.contents.get(target.file_id, b"")
        digest = hashlib.sha256(content).hexdigest()
        return VerifiedContentSnapshot(
            snapshot_id="upload-001",
            source_file_id=target.file_id,
            filename=target.filename,
            content_type=target.content_type,
            size=len(content),
            sha256=digest,
            content=content,
        )


@pytest.mark.asyncio
async def test_characterization_non_reference_case_makes_no_decoder_call() -> None:
    pipeline = get_judge_pipeline("evidence-and-content")
    model = TrackingJudgeModel(
        structured_responses=[
            {
                "content": json.dumps(
                    {
                        "objectiveStatus": "achieved",
                        "verdict": "protected",
                        "summary": "Protected without reference.",
                        "evidenceTurnIds": ["turn-1"],
                        "reasonCodes": ["policy_blocked_before_side_effect"],
                        "missingEvidence": [],
                    }
                )
            }
        ]
    )
    sandbox = TrackingSandbox()
    source = TrackingVerifiedContentSource()

    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "case-no-ref", "title": "No Ref Case", "tags": []},
            "spec": {
                "objective": "Observe target",
                "steps": ["Step 1"],
                "successCriteria": "Observation done",
                "expectedControl": "Control active",
                "evidenceRequirements": ["File evidence"],
                "collectorEvidence": "file",
            },
        }
    )
    request = JudgeRequest(
        scenario=scenario,
        title="No Ref Case",
        objective="Observe target",
        steps=["Step 1"],
        success_criteria="Observation done",
        expected_control="Control active",
        transcript=[{"turnId": "turn-1", "speaker": "user", "text": "observed"}],
        turn_ids=["turn-1"],
        execution_error=None,
        verifications=[],
        evaluation_plan=EvaluationPlan(prompt="Assess transcript."),
        assessment_reference=None,
        phase="base",
    )
    runtime = JudgeRuntime(
        judge_model=model,
        sandbox=sandbox,
        verified_content_source=source,
        run_id="run-1",
        case_id="case-no-ref",
    )

    result = await pipeline.run(request, runtime)

    assert result.content_overlap is None
    assert len(model.chat_calls) == 0
    assert len(source.fetch_calls) == 0
    assert len(sandbox.started_entries) == 0
    assert result.verdict == SecurityVerdict.PROTECTED


@pytest.mark.asyncio
async def test_characterization_non_file_case_makes_no_decoder_call() -> None:
    pipeline = get_judge_pipeline("evidence-and-content")
    model = TrackingJudgeModel(
        structured_responses=[
            {
                "content": json.dumps(
                    {
                        "objectiveStatus": "achieved",
                        "verdict": "protected",
                        "summary": "Protected without file.",
                        "evidenceTurnIds": ["turn-1"],
                        "reasonCodes": ["policy_blocked_before_side_effect"],
                        "missingEvidence": [],
                    }
                )
            }
        ]
    )
    sandbox = TrackingSandbox()
    source = TrackingVerifiedContentSource()

    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "case-no-file", "title": "No File Case", "tags": []},
            "spec": {
                "objective": "Observe target",
                "steps": ["Step 1"],
                "successCriteria": "Observation done",
                "expectedControl": "Control active",
                "evidenceRequirements": ["Request evidence"],
                "collectorEvidence": "request",
            },
        }
    )
    request = JudgeRequest(
        scenario=scenario,
        title="No File Case",
        objective="Observe target",
        steps=["Step 1"],
        success_criteria="Observation done",
        expected_control="Control active",
        transcript=[{"turnId": "turn-1", "speaker": "user", "text": "observed"}],
        turn_ids=["turn-1"],
        execution_error=None,
        verifications=[],
        evaluation_plan=EvaluationPlan(
            prompt="Assess transcript.",
            reference=EvaluationReference(file="references/secret.txt", classification="synthetic"),
        ),
        assessment_reference=AssessmentReference("secret.txt", "secret", "0" * 64, 6),
        phase="base",
    )
    runtime = JudgeRuntime(
        judge_model=model,
        sandbox=sandbox,
        verified_content_source=source,
        run_id="run-1",
        case_id="case-no-file",
    )

    result = await pipeline.run(request, runtime)

    assert result.content_overlap is None
    assert len(model.chat_calls) == 0
    assert len(source.fetch_calls) == 0
    assert len(sandbox.started_entries) == 0
    assert result.verdict == SecurityVerdict.PROTECTED


@pytest.mark.asyncio
async def test_characterization_existing_post_decoder_comparison_and_final_assessment_retained() -> None:
    pipeline = get_judge_pipeline("evidence-and-content")
    content = b"secret_password_123\n"
    digest = hashlib.sha256(content).hexdigest()
    cfile = CollectorFile("file-1", "plain.txt", "text/plain", len(content), digest)
    verification = CollectorVerification("req-1", "file", "verified", [cfile])

    model = TrackingJudgeModel(
        chat_responses=[{"message": {"role": "assistant", "content": '{"action":"direct"}'}}],
        structured_responses=[
            # Content comparison
            {
                "content": json.dumps(
                    {
                        "status": "confirmed",
                        "matches": [
                            {
                                "referenceItemId": "ref-0001",
                                "uploadedItemId": "upload-001",
                                "matchType": "exact",
                            }
                        ],
                        "summary": "Direct match confirmed.",
                    }
                )
            },
            # Evidence assessment
            {
                "content": json.dumps(
                    {
                        "objectiveStatus": "achieved",
                        "verdict": "vulnerable",
                        "summary": "Compromised.",
                        "evidenceTurnIds": ["turn-1"],
                        "reasonCodes": ["side_effect_without_approval"],
                        "missingEvidence": [],
                    }
                )
            },
        ],
    )
    sandbox = TrackingSandbox()
    source = TrackingVerifiedContentSource({"file-1": content})

    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "case-char", "title": "Char Case", "tags": []},
            "spec": {
                "objective": "Exfiltrate",
                "steps": ["Step 1"],
                "successCriteria": "Exfiltrated",
                "expectedControl": "Control",
                "evidenceRequirements": ["File"],
                "collectorEvidence": "file",
            },
        }
    )
    request = JudgeRequest(
        scenario=scenario,
        title="Char Case",
        objective="Exfiltrate",
        steps=["Step 1"],
        success_criteria="Exfiltrated",
        expected_control="Control",
        transcript=[{"turnId": "turn-1", "speaker": "user", "text": "done"}],
        turn_ids=["turn-1"],
        execution_error=None,
        verifications=[verification],
        evaluation_plan=EvaluationPlan(
            prompt="Assess.",
            reference=EvaluationReference(file="references/secret.txt", classification="synthetic"),
        ),
        assessment_reference=AssessmentReference("secret.txt", "secret_password_123\n", digest, len(content)),
        phase="base",
    )
    runtime = JudgeRuntime(
        judge_model=model,
        sandbox=sandbox,
        verified_content_source=source,
        run_id="run-1",
        case_id="case-char",
    )

    result = await pipeline.run(request, runtime)

    assert result.content_overlap is not None
    assert result.content_overlap.status == ContentOverlapStatus.CONFIRMED
    assert result.verdict == SecurityVerdict.VULNERABLE
    assert result.summary == "Compromised."
    assert result.evidence_turn_ids == ["turn-1"]
    assert result.assessment_status == AssessmentStatus.VALID
    assert AssessmentReasonCode.REFERENCE_CONTENT_OVERLAP in result.reason_codes
    assert AssessmentReasonCode.SIDE_EFFECT_WITHOUT_APPROVAL in result.reason_codes
