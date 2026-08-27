from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from gamr_cli.judge_evaluation import run_evaluation_dataset
from gamr_cli.judge_evaluation_models import LoadedCase, LoadedDataset
from gamr_core import (
    AssessmentStatus,
    EvaluationPlan,
    ObjectiveStatus,
    Scenario,
    SecurityVerdict,
)
from gamr_engine.judges.contracts import JudgeResult
from gamr_engine.ports.sandbox import Sandbox
from gamr_engine.ports.tracing import TraceObservation


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


class _FakeSandbox:
    isolation = "contained"


class _FakeModel:
    model = "test-model"

    async def complete_structured(self, prompt: str, **kw: Any) -> dict[str, object]:
        return {
            "content": (
                '{"verdict":"protected","objectiveStatus":"not_achieved",'
                '"assessmentStatus":"valid","reasonCodes":["policy_blocked_before_side_effect"],'
                '"evidenceTurnIds":[],"summary":"blocked"}'
            )
        }


def _make_dataset() -> LoadedDataset:
    scenario = Scenario.model_validate(
        {
            "metadata": {"id": "case-1", "title": "Case 1"},
            "spec": {
                "objective": "test",
                "steps": ["step 1"],
                "expectedControl": "deny",
                "evidenceRequirements": ["response"],
            },
        }
    )
    case = LoadedCase(
        id="case-1",
        label="Test case",
        source_run_id="run-src-1",
        rationale="test",
        scenario=scenario,
        evaluation_plan=EvaluationPlan(prompt="evaluate"),
        transcript=[],
        reference=type(
            "Ref",
            (),
            {"filename": "ref.txt", "content": b"clean text", "sha256": "abc", "size": 10},
        )(),
        attachments=[],
        expectations=[{"path": "/verdict", "values": ["protected"]}],
    )
    return LoadedDataset(
        judge_pipeline="evidence-and-content", source_path="dataset.json", cases=[case]
    )


@pytest.mark.asyncio
async def test_judge_evaluation_traces_run_and_scores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = RecordingTracePort()
    dataset = _make_dataset()

    async def fake_pipeline_run(_req: Any, runtime: Any) -> JudgeResult:
        await runtime.judge_model.complete_structured("prompt", system="system", json_schema={})
        return JudgeResult(
            objective_status=ObjectiveStatus.NOT_ACHIEVED,
            verdict=SecurityVerdict.PROTECTED,
            summary="blocked",
            evidence_turn_ids=[],
            assessment_status=AssessmentStatus.VALID,
        )

    fake_pipeline = type("Pipeline", (), {"run": staticmethod(fake_pipeline_run)})
    import gamr_cli.judge_evaluation as je_module

    monkeypatch.setattr(je_module, "get_judge_pipeline", lambda _p: fake_pipeline)

    summary = await run_evaluation_dataset(
        dataset,
        model=_FakeModel(),
        sandbox=cast(Sandbox, _FakeSandbox()),
        output_root=tmp_path / "eval-out",
        evaluation_id="eval-test-1",
        secrets=(),
        trace_port=port,
    )

    case_json = (tmp_path / "eval-out" / "cases" / "case-1.json").read_text()
    assert summary["passed"] is True, f"Case json: {case_json}"
    assert len(port.traces) == 1
    run_trace = port.traces[0]
    assert run_trace.name == "evaluation:eval-test-1"
    assert run_trace.kwargs["session_id"] == "eval-test-1"

    assert len(port.spans) == 1
    case_span = port.spans[0]
    assert case_span.name == "case:case-1"
    assert case_span.parent is run_trace

    score_names = [s["name"] for s in port.scores]
    assert "security_verdict" in score_names
    assert "objective_status" in score_names
    assert "assessment_status" in score_names
    assert "evaluation_passed" in score_names


@pytest.mark.asyncio
async def test_judge_evaluation_tracing_failure_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = FailingTracePort()
    dataset = _make_dataset()

    async def fake_pipeline_run(_req: Any, runtime: Any) -> JudgeResult:
        await runtime.judge_model.complete_structured("prompt", system="system", json_schema={})
        return JudgeResult(
            objective_status=ObjectiveStatus.NOT_ACHIEVED,
            verdict=SecurityVerdict.PROTECTED,
            summary="blocked",
            evidence_turn_ids=[],
            assessment_status=AssessmentStatus.VALID,
        )

    fake_pipeline = type("Pipeline", (), {"run": staticmethod(fake_pipeline_run)})
    import gamr_cli.judge_evaluation as je_module

    monkeypatch.setattr(je_module, "get_judge_pipeline", lambda _p: fake_pipeline)

    summary = await run_evaluation_dataset(
        dataset,
        model=_FakeModel(),
        sandbox=cast(Sandbox, _FakeSandbox()),
        output_root=tmp_path / "eval-out-fail",
        evaluation_id="eval-test-fail",
        secrets=(),
        trace_port=port,
    )

    assert summary["passed"] is True
