import pytest
from gamr_core import (
    EvaluationPlan,
    ObjectiveStatus,
    Scenario,
)
from gamr_engine.judges.contracts import JudgeRequest, JudgeRuntime
from gamr_engine.judges.registry import get_judge_pipeline


class SecretRecordingModel:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def complete(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        return {"content": self.response}


@pytest.mark.asyncio
async def test_judge_pipeline_does_not_persist_graph_state_or_leak_secrets() -> None:
    pipeline = get_judge_pipeline("evidence-and-content")
    model = SecretRecordingModel(
        '{"objectiveStatus":"achieved","verdict":"protected",'
        '"summary":"No leak.","evidenceTurnIds":["turn-1"]}'
    )

    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "sec-case", "title": "Security Case", "tags": []},
            "spec": {
                "objective": "Verify security",
                "steps": ["Step 1"],
                "successCriteria": "Success",
                "expectedControl": "Control",
                "evidenceRequirements": ["Evidence"],
            },
        }
    )

    request = JudgeRequest(
        scenario=scenario,
        title="Security Case",
        objective="Verify security",
        steps=["Step 1"],
        success_criteria="Success",
        expected_control="Control",
        transcript=[
            {
                "turnId": "turn-1",
                "speaker": "user",
                "text": "Authorization: Bearer SECRET_TOKEN_12345",
            }
        ],
        turn_ids=["turn-1"],
        execution_error=None,
        verifications=[],
        evaluation_plan=EvaluationPlan(prompt="Assess."),
        phase="base",
    )

    runtime = JudgeRuntime(
        judge_model=model,
        run_id="sec-run",
        case_id="sec-case",
    )

    result = await pipeline.run(request, runtime)
    assert result.objective_status == ObjectiveStatus.ACHIEVED

    # Run a second time with fresh state to ensure no state persistence
    model2 = SecretRecordingModel(
        '{"objectiveStatus":"achieved","verdict":"protected",'
        '"summary":"No leak 2.","evidenceTurnIds":["turn-2"]}'
    )
    request2 = JudgeRequest(
        scenario=scenario,
        title="Security Case 2",
        objective="Verify security",
        steps=["Step 1"],
        success_criteria="Success",
        expected_control="Control",
        transcript=[{"turnId": "turn-2", "speaker": "user", "text": "normal text"}],
        turn_ids=["turn-2"],
        execution_error=None,
        verifications=[],
        evaluation_plan=EvaluationPlan(prompt="Assess."),
        phase="base",
    )
    runtime2 = JudgeRuntime(
        judge_model=model2,
        run_id="sec-run-2",
        case_id="sec-case-2",
    )

    result2 = await pipeline.run(request2, runtime2)
    assert result2.evidence_turn_ids == ["turn-2"]
    assert not any("SECRET_TOKEN_12345" in prompt for prompt in model2.prompts)
