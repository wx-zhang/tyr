from gamr_core import (
    AssessmentReasonCode,
    AssessmentStatus,
    ContentMatch,
    ContentMatchType,
    ContentOverlapResult,
    ContentOverlapStatus,
    EvaluationPlan,
    EvaluationReference,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
)
from gamr_engine.judges.contracts import (
    JudgePipeline,
    JudgeRequest,
    JudgeResult,
    JudgeRuntime,
)


def test_judge_contracts_defined_and_instantiable() -> None:
    assert JudgeRequest is not None
    assert JudgeRuntime is not None
    assert JudgeResult is not None
    assert JudgePipeline is not None


def test_judge_request_holds_case_inputs() -> None:
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "case-1", "title": "Test Case"},
            "spec": {
                "objective": "Test objective",
                "steps": ["Step 1"],
                "successCriteria": "Success",
                "expectedControl": "Control",
                "evidenceRequirements": ["Evidence 1"],
            },
        }
    )
    request = JudgeRequest(
        scenario=scenario,
        title="Rendered Title",
        objective="Rendered Objective",
        steps=["Rendered Step 1"],
        success_criteria="Rendered Success",
        expected_control="Rendered Control",
        transcript=[{"turn": 1, "speaker": "user", "text": "hello"}],
        turn_ids=["turn-1"],
        execution_error=None,
        verifications=[],
        evaluation_plan=EvaluationPlan(
            prompt="Assess the case",
            reference=EvaluationReference(
                file="references/important.txt", classification="synthetic"
            ),
        ),
        phase="base",
    )
    assert request.title == "Rendered Title"
    assert request.execution_error is None
    assert request.turn_ids == ["turn-1"]


def test_judge_result_contains_assessment_and_content_fields() -> None:
    result = JudgeResult(
        objective_status=ObjectiveStatus.ACHIEVED,
        verdict=SecurityVerdict.VULNERABLE,
        summary="Security goal compromised",
        evidence_turn_ids=["turn-1"],
        assessment_status=AssessmentStatus.VALID,
        assessment_failure=None,
        reason_codes=[AssessmentReasonCode.REFERENCE_CONTENT_OVERLAP],
        missing_evidence=[],
        content_overlap=ContentOverlapResult(
            status=ContentOverlapStatus.CONFIRMED,
            assessmentStatus=AssessmentStatus.VALID,
            matches=[
                ContentMatch(
                    referenceItemId="ref-0001",
                    uploadedItemId="upload-001",
                    matchType=ContentMatchType.EXACT,
                )
            ],
        ),
    )
    assert result.objective_status == ObjectiveStatus.ACHIEVED
    assert result.verdict == SecurityVerdict.VULNERABLE
    assert result.content_overlap is not None
