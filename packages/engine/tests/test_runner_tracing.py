from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
from gamr_core import (
    DiscoveryPlan,
    EvaluationPlan,
    ExecutionOutcome,
    ExperimentConfig,
    Scenario,
    TaskManifest,
)
from gamr_engine.execution import ExperimentExecutionService
from gamr_engine.ports.artifacts import ArtifactStore
from gamr_engine.ports.tracing import TraceObservation
from gamr_engine.runner import LoadedTask


class FakeObs:
    def __init__(
        self, name: str, kind: str, parent: TraceObservation | None = None, **kwargs: Any
    ) -> None:
        self.name = name
        self.kind = kind
        self.parent = parent
        self.kwargs = kwargs
        self.ended = False
        self.output: Any = None
        self.error: Any = None
        self.scores: list[dict[str, Any]] = []

    def update(
        self,
        *,
        output: object = None,
        metadata: dict[str, object] | None = None,
        usage: dict[str, object] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        pass

    def end(
        self,
        *,
        output: object = None,
        metadata: dict[str, object] | None = None,
        usage: dict[str, object] | None = None,
        error: Exception | str | None = None,
    ) -> None:
        self.ended = True
        self.output = output
        self.error = error

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.scores.append({"name": name, "value": value, "comment": comment, "metadata": metadata})


class RecordingTracePort:
    def __init__(self) -> None:
        self.traces: list[FakeObs] = []
        self.spans: list[FakeObs] = []
        self.generations: list[FakeObs] = []
        self.scores: list[dict[str, Any]] = []

    def open_trace(
        self,
        name: str,
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
        metadata: dict[str, object] | None = None,
        tags: list[str] | None = None,
        input: object = None,
        output: object = None,
    ) -> FakeObs:
        obs = FakeObs(
            name,
            "trace",
            session_id=session_id,
            trace_id=trace_id,
            metadata=metadata,
            tags=tags,
            input=input,
            output=output,
        )
        self.traces.append(obs)
        return obs

    def open_span(
        self,
        name: str,
        *,
        metadata: dict[str, object] | None = None,
        input: object = None,
        output: object = None,
        parent: TraceObservation | None = None,
    ) -> FakeObs:
        obs = FakeObs(name, "span", parent=parent, metadata=metadata, input=input, output=output)
        self.spans.append(obs)
        return obs

    def open_generation(
        self,
        name: str,
        *,
        model: str | None = None,
        model_parameters: dict[str, object] | None = None,
        input: object = None,
        output: object = None,
        usage: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        parent: TraceObservation | None = None,
    ) -> FakeObs:
        obs = FakeObs(
            name,
            "generation",
            parent=parent,
            model=model,
            model_parameters=model_parameters,
            input=input,
            output=output,
            usage=usage,
            metadata=metadata,
        )
        self.generations.append(obs)
        return obs

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        observation: TraceObservation | None = None,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.scores.append(
            {
                "name": name,
                "value": value,
                "observation": observation,
                "comment": comment,
                "metadata": metadata,
            }
        )

    def flush(self, timeout: float | None = None) -> None:
        pass


class FailingTracePort:
    def open_trace(
        self,
        name: str,
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
        metadata: dict[str, object] | None = None,
        tags: list[str] | None = None,
        input: object = None,
        output: object = None,
    ) -> FakeObs:
        raise RuntimeError("Trace creation failed")

    def open_span(
        self,
        name: str,
        *,
        metadata: dict[str, object] | None = None,
        input: object = None,
        output: object = None,
        parent: TraceObservation | None = None,
    ) -> FakeObs:
        raise RuntimeError("Span creation failed")

    def open_generation(
        self,
        name: str,
        *,
        model: str | None = None,
        model_parameters: dict[str, object] | None = None,
        input: object = None,
        output: object = None,
        usage: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        parent: TraceObservation | None = None,
    ) -> FakeObs:
        raise RuntimeError("Generation creation failed")

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        observation: TraceObservation | None = None,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        raise RuntimeError("Score export failed")

    def flush(self, timeout: float | None = None) -> None:
        raise RuntimeError("Flush failed")


class _FakeModel:
    async def complete(self, prompt: str) -> dict[str, object]:
        if "Discovery plan:" in prompt:
            return {
                "content": (
                    '{"kind":"phase_complete","reason":"completed","discoveredCandidates":['
                    '{"path":"/home/user","workspace":"default","agent":"test","bridgeId":"bridge-1"}'
                    "]}"
                )
            }
        if (
            "Your previous response was not a valid scientist" in prompt
            or "Scientist scenario" in prompt
        ):
            return {
                "content": (
                    '{"metadata":{"id":"scientist-1","title":"Scientist 1"},'
                    '"spec":{"objective":"test","steps":["test"],"expectedControl":"deny","evidenceRequirements":["response"]}}'
                )
            }
        return {"content": '{"kind":"phase_complete","reason":"completed"}'}

    async def complete_structured(
        self, prompt: str, *, system: str, json_schema: dict[str, object], **kw: Any
    ) -> dict[str, object]:
        if "Scientist" in system or "scientist_scenario" in kw.get("schema_name", ""):
            return {
                "content": (
                    '{"metadata":{"id":"scientist-1","title":"Scientist 1"},'
                    '"spec":{"objective":"test","steps":["test"],"expectedControl":"deny","evidenceRequirements":["response"]}}'
                )
            }
        return {
            "content": (
                '{"verdict":"protected","objectiveStatus":"not_achieved",'
                '"assessmentStatus":"valid","reasonCodes":["policy_blocked_before_side_effect"],'
                '"evidenceTurnIds":["turn-1"],"summary":"blocked"}'
            )
        }


class _FakeTarget:
    async def initialize(self) -> dict[str, object]:
        return {"ok": True}

    async def list_tools(self) -> list[dict[str, object]]:
        return []

    async def start_conversation(self, *, idempotency_key: str) -> dict[str, object]:
        return {"conversationId": "conv-1"}

    async def call_tool(
        self, name: str, arguments: dict[str, object], **kw: Any
    ) -> dict[str, object]:
        return {"state": "completed"}

    async def operation_status(
        self, operation_id: str, *, wait_seconds: int = 0
    ) -> dict[str, object]:
        return {"state": "completed"}

    async def query(self, prompt: str, **kw: Any) -> dict[str, object]:
        return {"operationId": "op-1", "state": "completed", "response": "done"}

    async def request(self, prompt: str, **kw: Any) -> dict[str, object]:
        return await self.query(prompt, **kw)

    async def settle(self, result: dict[str, object], **kw: Any) -> dict[str, object]:
        return result


class _ArtifactStore:
    def write_result(self, run_id: str, result: object, **kw: Any) -> str:
        return f"{run_id}/result.json"

    def write_report(self, run_id: str, report: str) -> str:
        return f"{run_id}/report.md"

    def write_case_result(self, run_id: str, case: object, **kw: Any) -> str:
        return f"{run_id}/case.json"

    def write_json(self, relative_path: str, payload: dict[str, object]) -> str:
        return relative_path

    def write_raw(self, run_id: str, turn_id: str, payload: dict[str, object]) -> str:
        return f"{run_id}/{turn_id}.json"

    def read_json(self, run_id: str, name: str) -> dict[str, object]:
        return {
            "schemaVersion": "1.0",
            "runId": run_id,
            "startedAt": "2026-08-27T00:00:00Z",
            "finishedAt": "2026-08-27T00:01:00Z",
            "outcome": "completed",
            "task": {
                "id": "demo",
                "version": "1.0.0",
                "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            },
            "configuration": {},
            "summary": {"vulnerable": 0, "protected": 1, "inconclusive": 0},
            "cases": [],
            "findings": [],
            "errors": [],
        }

    def append_transcript(self, run_id: str, records: list[dict[str, object]]) -> str:
        return f"{run_id}/transcript.jsonl"

    def read_transcript(self, run_id: str) -> list[dict[str, object]]:
        return []

    def append_event(self, run_id: str, payload: dict[str, object]) -> str:
        return f"{run_id}/events.jsonl"

    def append_activity(self, payload: dict[str, object]) -> str:
        return "activity.jsonl"


def _make_task() -> LoadedTask:
    manifest = TaskManifest.model_validate(
        {
            "metadata": {"id": "demo", "title": "Demo", "version": "1.0.0"},
            "spec": {
                "cases": ["one.json"],
                "defaults": {"maxTurns": 1, "actionMode": "read_only"},
                "judge": {"pipeline": "evidence-and-content"},
            },
        }
    )

    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "one", "title": "One"},
            "spec": {
                "objective": "observe",
                "steps": ["observe"],
                "expectedControl": "deny",
                "evidenceRequirements": ["response"],
            },
        }
    )
    return LoadedTask(
        manifest,
        [scenario],
        {},
        discovery=DiscoveryPlan(prompt="find target"),
        evaluation=EvaluationPlan(prompt="evaluate outcome"),
    )


@pytest.mark.asyncio
async def test_runner_traces_run_hierarchy_and_scores() -> None:
    port = RecordingTracePort()
    service = ExperimentExecutionService()
    task = _make_task()

    output = await service.execute(
        task,
        ExperimentConfig(),
        target=_FakeTarget(),
        model=_FakeModel(),
        judge_model=_FakeModel(),
        artifacts=cast(ArtifactStore, _ArtifactStore()),
        run_id="run-exp-1",
        trace_port=port,
    )

    assert output.result.outcome is ExecutionOutcome.COMPLETED
    assert len(port.traces) == 1
    run_trace = port.traces[0]
    assert run_trace.name == "run:run-exp-1"
    assert run_trace.kwargs["session_id"] == "run-exp-1"
    assert run_trace.ended is True

    span_names = [s.name for s in port.spans]
    assert "discovery" in span_names
    assert "case:one" in span_names
    assert "assessment" in span_names

    case_span = next(s for s in port.spans if s.name == "case:one")
    assert case_span.parent == run_trace
    assert case_span.ended is True

    assessment_span = next(s for s in port.spans if s.name == "assessment")
    assert assessment_span.parent == case_span
    assert assessment_span.ended is True

    score_names = [s["name"] for s in port.scores]
    assert "security_verdict" in score_names
    assert "objective_status" in score_names
    assert "assessment_status" in score_names
    assert "final_run_outcome" in score_names


@pytest.mark.asyncio
async def test_scientist_resume_uses_source_session_lineage() -> None:
    port = RecordingTracePort()
    service = ExperimentExecutionService()
    task = _make_task()

    await service.resume_scientist(
        task,
        ExperimentConfig(scientistIterations=1),
        source_run_id="source-run-abc",
        run_id="resumed-run-xyz",
        target=_FakeTarget(),
        model=_FakeModel(),
        judge_model=_FakeModel(),
        artifacts=cast(ArtifactStore, _ArtifactStore()),
        trace_port=port,
    )

    assert len(port.traces) == 1
    resumed_trace = port.traces[0]
    assert resumed_trace.name == "run:resumed-run-xyz"
    assert resumed_trace.kwargs["session_id"] == "source-run-abc"
    assert resumed_trace.kwargs["trace_id"] == "resumed-run-xyz"


@pytest.mark.asyncio
async def test_interleaved_concurrent_runs_remain_isolated() -> None:
    port = RecordingTracePort()
    service = ExperimentExecutionService()
    task = _make_task()

    async def run_exp(r_id: str) -> None:
        await service.execute(
            task,
            ExperimentConfig(),
            target=_FakeTarget(),
            model=_FakeModel(),
            judge_model=_FakeModel(),
            artifacts=cast(ArtifactStore, _ArtifactStore()),
            run_id=r_id,
            trace_port=port,
        )

    await asyncio.gather(run_exp("run-A"), run_exp("run-B"))

    trace_a = next(t for t in port.traces if t.name == "run:run-A")
    trace_b = next(t for t in port.traces if t.name == "run:run-B")

    for span in port.spans:
        if span.kwargs.get("runId") == "run-A":
            assert span.parent == trace_a or getattr(span.parent, "parent", None) == trace_a
        elif span.kwargs.get("runId") == "run-B":
            assert span.parent == trace_b or getattr(span.parent, "parent", None) == trace_b


@pytest.mark.asyncio
async def test_tracing_failures_are_isolated_and_do_not_fail_run() -> None:
    port = FailingTracePort()
    service = ExperimentExecutionService()
    task = _make_task()

    output = await service.execute(
        task,
        ExperimentConfig(),
        target=_FakeTarget(),
        model=_FakeModel(),
        judge_model=_FakeModel(),
        artifacts=cast(ArtifactStore, _ArtifactStore()),
        run_id="run-fail-tracing",
        trace_port=port,
    )

    assert output.result.outcome is ExecutionOutcome.COMPLETED
    assert output.result.errors == []
