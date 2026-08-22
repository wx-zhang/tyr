import pytest
from gamr_core import (
    EvaluationPlan,
    EvaluationReference,
    Scenario,
    SecurityVerdict,
)
from gamr_engine.collector_verification import CollectorVerification
from gamr_engine.content_evidence import AssessmentReference
from gamr_engine.judges.contracts import JudgeRequest, JudgeRuntime
from gamr_engine.judges.registry import get_judge_pipeline


class RecordingModel:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def complete(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        return {"content": self.response}


class EmptyEvidenceProvider:
    async def get_evidence(self, *args: object, **kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_unreadable_upload_preserves_inconclusive_outcome_and_triggers_no_sandbox() -> None:
    pipeline = get_judge_pipeline("evidence-and-content")
    model = RecordingModel(
        '{"objectiveStatus":"achieved","verdict":"inconclusive",'
        '"summary":"File content was unavailable.","evidenceTurnIds":[]}'
    )

    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "unreadable-case", "title": "Unreadable Case", "tags": []},
            "spec": {
                "objective": "Verify unreadable upload",
                "steps": ["Step 1"],
                "successCriteria": "Success",
                "expectedControl": "Control",
                "evidenceRequirements": ["Evidence"],
                "collectorEvidence": "file",
            },
        }
    )

    verification = CollectorVerification(
        request_id="req-1",
        requirement="file",
        status="verified",
        files=[],
        detail=None,
        source_turn_id="turn-1",
    )

    request = JudgeRequest(
        scenario=scenario,
        title="Unreadable Case",
        objective="Verify unreadable upload",
        steps=["Step 1"],
        success_criteria="Success",
        expected_control="Control",
        transcript=[{"turnId": "turn-1", "speaker": "user", "text": "uploaded file"}],
        turn_ids=["turn-1"],
        execution_error=None,
        verifications=[verification],
        evaluation_plan=EvaluationPlan(
            prompt="Assess.",
            reference=EvaluationReference(
                file="references/important.txt", classification="synthetic"
            ),
        ),
        assessment_reference=AssessmentReference(
            filename="important.txt",
            content="secret text",
            sha256="a" * 64,
            size=11,
        ),
        phase="base",
    )

    runtime = JudgeRuntime(
        judge_model=model,
        content_evidence_provider=EmptyEvidenceProvider(),  # type: ignore[arg-type]
        run_id="run-unreadable",
        case_id="case-unreadable",
    )

    result = await pipeline.run(request, runtime)

    assert result.verdict == SecurityVerdict.INCONCLUSIVE
    # Only standard judge prompts executed, no sandbox / reading plan scripts generated
    assert all("sandbox" not in prompt.lower() for prompt in model.prompts)
