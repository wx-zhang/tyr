from unittest.mock import AsyncMock, patch

import pytest
from gamr_core import (
    AssessmentStatus,
    DiscoveryPlan,
    EvaluationPlan,
    ExperimentConfig,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
    TaskManifest,
)
from gamr_engine.experiments.records import LoadedTask
from gamr_engine.judges.contracts import JudgeResult
from gamr_engine.judges.registry import get_judge_pipeline
from gamr_engine.runner import ExperimentRunner


class FakeModel:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.prompts: list[str] = []

    async def complete(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        return {"content": next(self.responses)}


class FakeTarget:
    async def initialize(self) -> dict[str, object]:
        return {"ok": True}

    async def list_tools(self) -> list[dict[str, object]]:
        return []

    async def start_conversation(self, *, idempotency_key: str) -> dict[str, object]:
        return {"conversationId": "conversation-1"}

    async def call_tool(
        self, name: str, arguments: dict[str, object], *, timeout: float = 60
    ) -> dict[str, object]:
        return {"state": "completed"}

    async def operation_status(
        self, operation_id: str, *, wait_seconds: int = 0
    ) -> dict[str, object]:
        return {"operationId": operation_id, "state": "completed"}

    async def query(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        conversation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        return {"operationId": operation_id or "op-1", "state": "completed", "response": "done"}

    async def request(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        conversation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        return await self.query(
            prompt,
            operation_id=operation_id,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
        )

    async def settle(
        self, result: dict[str, object], *, operation_id: str | None = None
    ) -> dict[str, object]:
        return result


def _make_task(explicit_judge: bool = False, has_evaluation: bool = True) -> LoadedTask:
    spec: dict[str, object] = {
        "discovery": "discovery.json",
        "cases": ["case.json"],
        "defaults": {"maxTurns": 2, "actionMode": "read_only"},
    }
    if explicit_judge:
        spec["judge"] = {"pipeline": "evidence-and-content"}
    if has_evaluation:
        spec["evaluation"] = "evaluation.json"

    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "test-task", "title": "Test Task", "version": "1.0.0"},
            "spec": spec,
        }
    )
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "case-1", "title": "Case 1"},
            "spec": {
                "objective": "Test",
                "steps": ["Step 1"],
                "successCriteria": "Success",
                "expectedControl": "Control",
                "evidenceRequirements": ["Evidence."],
            },
        }
    )
    discovery = DiscoveryPlan(prompt="Discover.", outputFields=["path", "workspace", "agent"])
    evaluation = EvaluationPlan(prompt="Assess.") if has_evaluation else None
    return LoadedTask(
        manifest,
        [scenario],
        {},
        discovery=discovery,
        evaluation=evaluation,
    )


@pytest.mark.asyncio
async def test_runner_explicit_and_legacy_defaulted_task_selection() -> None:
    task_explicit = _make_task(explicit_judge=True)
    task_legacy = _make_task(explicit_judge=False)

    pipeline_explicit = get_judge_pipeline(task_explicit.manifest.spec.judge.pipeline)
    pipeline_legacy = get_judge_pipeline(task_legacy.manifest.spec.judge.pipeline)

    assert pipeline_explicit.id == "evidence-and-content"
    assert pipeline_legacy.id == "evidence-and-content"
    assert pipeline_explicit is pipeline_legacy


@pytest.mark.asyncio
async def test_runner_without_evaluation_skips_registry_and_judge() -> None:
    task_no_eval = _make_task(has_evaluation=False)
    runner = ExperimentRunner()
    model = FakeModel(
        [
            '{"kind":"phase_complete","reason":"found","discoveredCandidates":[{"path":"/home/user/file.txt","workspace":"ws","agent":"ag","bridgeId":"br"}]}',
            '{"kind":"send","message":"test"}',
            '{"kind":"phase_complete","reason":"done"}',
        ]
    )

    with patch("gamr_engine.experiments.case_assessment.get_judge_pipeline") as mock_get_pipeline:
        result = await runner.run(
            task_no_eval,
            ExperimentConfig(),
            target=FakeTarget(),
            model=model,
        )
        assert mock_get_pipeline.call_count == 0
        assert result.cases[0].assessment_status == AssessmentStatus.SKIPPED
        assert result.judge_pipeline is None


@pytest.mark.asyncio
async def test_runner_invokes_pipeline_once_per_case() -> None:
    task = _make_task(explicit_judge=True)
    runner = ExperimentRunner()
    model = FakeModel(
        [
            '{"kind":"phase_complete","reason":"found","discoveredCandidates":[{"path":"/home/user/file.txt","workspace":"ws","agent":"ag","bridgeId":"br"}]}',
            '{"kind":"send","message":"test"}',
            '{"kind":"phase_complete","reason":"done"}',
        ]
    )
    judge_model = FakeModel(
        [
            (
                '{"objectiveStatus":"achieved","verdict":"protected",'
                '"summary":"Done safely.","evidenceTurnIds":[]}'
            )
        ]
    )

    with patch("gamr_engine.experiments.case_assessment.get_judge_pipeline") as mock_get_pipeline:
        mock_pipeline = AsyncMock()
        mock_pipeline.id = "evidence-and-content"
        mock_pipeline.run.return_value = JudgeResult(
            objective_status=ObjectiveStatus.ACHIEVED,
            verdict=SecurityVerdict.PROTECTED,
            summary="Judged via pipeline mock",
            evidence_turn_ids=[],
            assessment_status=AssessmentStatus.VALID,
            assessment_failure=None,
            reason_codes=[],
            missing_evidence=[],
            content_overlap=None,
        )
        mock_get_pipeline.return_value = mock_pipeline

        result = await runner.run(
            task,
            ExperimentConfig(),
            target=FakeTarget(),
            model=model,
            judge_model=judge_model,
        )

        assert mock_get_pipeline.call_count == 1
        assert mock_pipeline.run.call_count == 1
        assert result.judge_pipeline == "evidence-and-content"
        assert result.cases[0].summary == "Judged via pipeline mock"
