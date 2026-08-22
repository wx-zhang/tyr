import pytest
from gamr_core import (
    AssessmentStatus,
    EvaluationPlan,
    EvaluationReference,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
)
from gamr_engine.judges.contracts import JudgeRequest, JudgeRuntime
from gamr_engine.judges.registry import get_judge_pipeline


class FakeJudgeModel:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def complete(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        return {"content": self.response}


def make_request(
    *,
    execution_error: str | None = None,
    collector_evidence: str | None = None,
    reference: EvaluationReference | None = None,
) -> JudgeRequest:
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "test-case", "title": "Test Case", "tags": []},
            "spec": {
                "objective": "Test objective",
                "steps": ["Step 1"],
                "successCriteria": "Success",
                "expectedControl": "Control",
                "evidenceRequirements": ["Evidence 1"],
                "collectorEvidence": collector_evidence,
            },
        }
    )
    return JudgeRequest(
        scenario=scenario,
        title="Test Case",
        objective="Test objective",
        steps=["Step 1"],
        success_criteria="Success",
        expected_control="Control",
        transcript=[{"turn": 1, "speaker": "user", "text": "hello"}],
        turn_ids=["turn-1"],
        execution_error=execution_error,
        verifications=[],
        evaluation_plan=EvaluationPlan(
            prompt="Assess the case",
            reference=reference,
        ),
        phase="base",
    )


@pytest.mark.asyncio
async def test_execution_error_shortcut_without_checked_content() -> None:
    pipeline = get_judge_pipeline("evidence-and-content")
    model = FakeJudgeModel("")
    runtime = JudgeRuntime(
        judge_model=model,
        run_id="run-1",
        case_id="test-case",
    )
    request = make_request(execution_error="Agent crashed")
    result = await pipeline.run(request, runtime)

    assert result.objective_status == ObjectiveStatus.PARTIAL
    assert result.verdict == SecurityVerdict.INCONCLUSIVE
    assert result.summary == "Agent crashed"
    assert len(model.prompts) == 0


@pytest.mark.asyncio
async def test_assess_evidence_valid_response() -> None:
    pipeline = get_judge_pipeline("evidence-and-content")
    model = FakeJudgeModel(
        '{"objectiveStatus":"achieved","verdict":"protected",'
        '"summary":"Handled safely.","evidenceTurnIds":["turn-1"]}'
    )
    runtime = JudgeRuntime(
        judge_model=model,
        run_id="run-1",
        case_id="test-case",
    )
    request = make_request()
    result = await pipeline.run(request, runtime)

    assert result.objective_status == ObjectiveStatus.ACHIEVED
    assert result.verdict == SecurityVerdict.PROTECTED
    assert result.summary == "Handled safely."
    assert result.assessment_status == AssessmentStatus.VALID
    assert len(model.prompts) == 1
