import pytest
from gamr_core import (
    DiscoveryPlan,
    EvaluationPlan,
    ExperimentConfig,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
    TaskManifest,
)
from gamr_engine.runner import ExperimentRunner, LoadedTask


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

    async def call_tool(
        self, name: str, arguments: dict[str, object], *, timeout: float = 60
    ) -> dict[str, object]:
        return {"state": "completed"}

    async def operation_status(
        self, operation_id: str, *, wait_seconds: int = 0
    ) -> dict[str, object]:
        return {"operationId": operation_id, "state": "completed"}

    async def query(
        self, prompt: str, *, operation_id: str | None = None, idempotency_key: str = ""
    ) -> dict[str, object]:
        return {"operationId": operation_id or "op-1", "state": "completed", "response": "done"}

    async def request(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        idempotency_key: str = "",
    ) -> dict[str, object]:
        return await self.query(prompt, operation_id=operation_id, idempotency_key=idempotency_key)

    async def settle(
        self, result: dict[str, object], *, operation_id: str | None = None
    ) -> dict[str, object]:
        return result


@pytest.mark.asyncio
async def test_characterization_runner_success_flow() -> None:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "char-test", "title": "Char Test", "version": "1.0.0"},
            "spec": {
                "discovery": "discovery.json",
                "variables": {
                    "path": {"source": "discovery", "field": "path"},
                    "workspace": {"source": "discovery", "field": "workspace"},
                    "agent": {"source": "discovery", "field": "agent"},
                },
                "cases": ["cases/case-1.json"],
                "defaults": {"maxTurns": 4, "actionMode": "read_only"},
            },
        }
    )
    discovery = DiscoveryPlan(prompt="Find a target.", outputFields=["path", "workspace", "agent"])
    evaluation = EvaluationPlan(prompt="Assess transcript.")
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "case-1", "title": "Case 1", "tags": []},
            "spec": {
                "objective": "Observe target.",
                "steps": ["Observe {path}."],
                "successCriteria": "Observation done.",
                "expectedControl": "Control active.",
                "evidenceRequirements": ["Transcript."],
            },
        }
    )
    model = FakeModel(
        [
            '{"kind":"phase_complete","reason":"found","discoveredCandidates":[{"path":"/home/alice/target","workspace":"ws","agent":"ag","bridgeId":"bridge-1"}]}',
            '{"kind":"send","message":"Read the file."}',
            '{"kind":"phase_complete","reason":"done"}',
        ]
    )
    judge_model = FakeModel(
        [
            (
                '{"objectiveStatus":"achieved","verdict":"protected",'
                '"summary":"Done safely.","evidenceTurnIds":["turn-1"]}'
            )
        ]
    )

    runner = ExperimentRunner()
    result = await runner.run(
        LoadedTask(
            manifest,
            [scenario],
            {"discovery": discovery.model_dump(by_alias=True)},
            discovery=discovery,
            evaluation=evaluation,
            assessment_reference=None,
        ),
        ExperimentConfig(),
        target=FakeTarget(),
        model=model,
        judge_model=judge_model,
    )
    print("ERRORS:", result.errors)

    assert result.outcome == "completed"
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.objective_status == ObjectiveStatus.ACHIEVED
    assert case.verdict == SecurityVerdict.PROTECTED
    assert case.summary == "Done safely."
    assert len(judge_model.prompts) == 1
