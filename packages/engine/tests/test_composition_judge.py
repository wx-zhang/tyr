from typing import cast

import pytest
from gamr_core import (
    DiscoveryPlan,
    EvaluationPlan,
    ExperimentConfig,
    Scenario,
    TaskManifest,
)
from gamr_engine.execution import ExperimentExecutionService
from gamr_engine.ports.artifacts import ArtifactStore
from gamr_engine.runner import LoadedTask


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


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self.files: dict[str, object] = {}

    def write_result(
        self, run_id: str, result: object, task_snapshot: dict[str, object] | None = None
    ) -> str:
        path = f"{run_id}/result.json"
        self.files[path] = result
        return path

    def write_report(self, run_id: str, report: str) -> str:
        path = f"{run_id}/report.md"
        self.files[path] = report
        return path

    def write_json(self, path: str, payload: dict[str, object]) -> str:
        self.files[path] = payload
        return path

    def append_transcript(self, run_id: str, records: list[dict[str, object]]) -> str:
        return "transcript.jsonl"

    def write_checkpoint(self, run_id: str, payload: dict[str, object]) -> str:
        return "checkpoint.json"

    def write_raw(self, run_id: str, turn_id: str, payload: dict[str, object]) -> str:
        return "raw.json"

    def append_event(self, run_id: str, payload: dict[str, object]) -> str:
        return "events.jsonl"

    def read_checkpoint(self, run_id: str) -> dict[str, object] | None:
        return None

    def read_raw(self, run_id: str, turn_id: str) -> dict[str, object] | None:
        return None

    def read_result(self, run_id: str) -> dict[str, object] | None:
        return None


@pytest.mark.asyncio
async def test_cli_and_api_use_same_registry_and_produce_equivalent_results() -> None:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "comp-task", "title": "Comp Task", "version": "1.0.0"},
            "spec": {
                "discovery": "discovery.json",
                "cases": ["case.json"],
                "defaults": {"maxTurns": 2, "actionMode": "read_only"},
                "judge": {"pipeline": "evidence-and-content"},
            },
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
    evaluation = EvaluationPlan(prompt="Assess.")
    task = LoadedTask(
        manifest,
        [scenario],
        {},
        discovery=discovery,
        evaluation=evaluation,
    )

    model_responses_cli = [
        '{"kind":"phase_complete","reason":"found","discoveredCandidates":[{"path":"/home/user/file.txt","workspace":"ws","agent":"ag","bridgeId":"br"}]}',
        '{"kind":"send","message":"test"}',
        '{"kind":"phase_complete","reason":"done"}',
    ]
    judge_responses_cli = [
        (
            '{"objectiveStatus":"achieved","verdict":"protected",'
            '"summary":"Done safely.","evidenceTurnIds":[]}'
        )
    ]

    model_responses_api = list(model_responses_cli)
    judge_responses_api = list(judge_responses_cli)

    service = ExperimentExecutionService()

    # CLI path execution
    cli_output = await service.execute(
        task,
        ExperimentConfig(),
        target=FakeTarget(),
        model=FakeModel(model_responses_cli),
        judge_model=FakeModel(judge_responses_cli),
        artifacts=cast(ArtifactStore, InMemoryArtifactStore()),
        run_id="run-cli",
    )

    # API path execution
    api_output = await service.execute(
        task,
        ExperimentConfig(),
        target=FakeTarget(),
        model=FakeModel(model_responses_api),
        judge_model=FakeModel(judge_responses_api),
        artifacts=cast(ArtifactStore, InMemoryArtifactStore()),
        run_id="run-api",
    )

    assert cli_output.result.judge_pipeline == "evidence-and-content"
    assert api_output.result.judge_pipeline == "evidence-and-content"
    assert cli_output.result.cases[0].verdict == api_output.result.cases[0].verdict
    assert (
        cli_output.result.cases[0].objective_status == api_output.result.cases[0].objective_status
    )
    assert cli_output.result.cases[0].summary == api_output.result.cases[0].summary
    assert (
        cli_output.result.cases[0].assessment_status == api_output.result.cases[0].assessment_status
    )
