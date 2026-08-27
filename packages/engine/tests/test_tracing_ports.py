from __future__ import annotations

import asyncio
from typing import Any

import pytest
from gamr_engine.ports.tracing import (
    TraceObservation,
    trace_generation,
    trace_run,
    trace_score,
    trace_span,
)


class FakeTraceObservation:
    def __init__(
        self,
        name: str,
        kind: str,
        *,
        parent: FakeTraceObservation | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        metadata: dict[str, object] | None = None,
        tags: list[str] | None = None,
        input: object = None,
        output: object = None,
        model: str | None = None,
        model_parameters: dict[str, object] | None = None,
        usage: dict[str, object] | None = None,
    ) -> None:
        self.name = name
        self.kind = kind
        self.parent = parent
        self.session_id = session_id
        self.trace_id = trace_id
        self.metadata = dict(metadata or {})
        self.tags = list(tags or [])
        self.input = input
        self.output = output
        self.model = model
        self.model_parameters = model_parameters
        self.usage = usage
        self.ended = False
        self.error: Exception | str | None = None
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
        if output is not None:
            self.output = output
        if metadata:
            self.metadata.update(metadata)
        if usage:
            self.usage = (self.usage or {}) | usage

    def end(
        self,
        *,
        output: object = None,
        metadata: dict[str, object] | None = None,
        usage: dict[str, object] | None = None,
        error: Exception | str | None = None,
    ) -> None:
        self.ended = True
        self.update(output=output, metadata=metadata, usage=usage)
        if error is not None:
            self.error = error

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.scores.append(
            {
                "name": name,
                "value": value,
                "comment": comment,
                "metadata": metadata,
            }
        )


class FakeTracePort:
    def __init__(self) -> None:
        self.traces: list[FakeTraceObservation] = []
        self.spans: list[FakeTraceObservation] = []
        self.generations: list[FakeTraceObservation] = []
        self.scores: list[dict[str, Any]] = []
        self.flushed = False

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
    ) -> FakeTraceObservation:
        obs = FakeTraceObservation(
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
    ) -> FakeTraceObservation:
        obs = FakeTraceObservation(
            name,
            "span",
            parent=parent,  # type: ignore[arg-type]
            metadata=metadata,
            input=input,
            output=output,
        )
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
    ) -> FakeTraceObservation:
        obs = FakeTraceObservation(
            name,
            "generation",
            parent=parent,  # type: ignore[arg-type]
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
        entry = {
            "name": name,
            "value": value,
            "observation": observation,
            "comment": comment,
            "metadata": metadata,
        }
        self.scores.append(entry)
        if observation is not None:
            observation.score(name, value, comment=comment, metadata=metadata)

    def flush(self, timeout: float | None = None) -> None:
        self.flushed = True


def test_trace_helpers_with_none_port_do_nothing() -> None:
    with trace_run(None, "run-1", session_id="sess-1") as r:
        assert r is None
        with trace_span(None, "case:c1") as s:
            assert s is None
            with trace_generation(None, "gen-1", model="test-model") as g:
                assert g is None
                trace_score(None, "verdict", "deny")


def test_trace_helpers_nest_and_record_terminal_and_scores() -> None:
    port = FakeTracePort()
    with trace_run(port, "run-1", session_id="sess-1", metadata={"dataset": "demo"}) as run_obs:
        assert run_obs is not None
        with trace_span(port, "case:c1", input={"prompt": "hello"}) as case_obs:
            assert case_obs is not None
            assert getattr(case_obs, "parent", None) is run_obs
            with trace_generation(port, "gen-1", model="gpt-4o", input="test prompt") as gen_obs:
                assert gen_obs is not None
                assert getattr(gen_obs, "parent", None) is case_obs
                gen_obs.end(output="test response", usage={"total_tokens": 42})
            trace_score(port, "security_verdict", "deny", observation=case_obs)
            if case_obs is not None:
                case_obs.end(output={"verdict": "deny"})
        trace_score(port, "run_outcome", "passed", observation=run_obs)
        if run_obs is not None:
            run_obs.end(output={"outcome": "passed"})

    assert len(port.traces) == 1
    assert port.traces[0].name == "run-1"
    assert port.traces[0].session_id == "sess-1"
    assert port.traces[0].ended is True
    assert port.traces[0].output == {"outcome": "passed"}

    assert len(port.spans) == 1
    assert port.spans[0].name == "case:c1"
    assert port.spans[0].parent is port.traces[0]
    assert port.spans[0].ended is True

    assert len(port.generations) == 1
    assert port.generations[0].name == "gen-1"
    assert port.generations[0].parent is port.spans[0]
    assert port.generations[0].output == "test response"
    assert port.generations[0].usage == {"total_tokens": 42}

    assert len(port.scores) == 2
    assert port.scores[0]["name"] == "security_verdict"
    assert port.scores[0]["value"] == "deny"
    assert port.scores[1]["name"] == "run_outcome"
    assert port.scores[1]["value"] == "passed"


def test_trace_helpers_capture_exceptions() -> None:
    port = FakeTracePort()
    with pytest.raises(ValueError, match="boom"):
        with trace_run(port, "run-err"), trace_span(port, "span-err"):
            raise ValueError("boom")

    assert port.spans[0].ended is True
    assert "boom" in str(port.spans[0].error)
    assert port.traces[0].ended is True
    assert "boom" in str(port.traces[0].error)


@pytest.mark.asyncio
async def test_concurrent_workflows_isolate_context_observations() -> None:
    port = FakeTracePort()

    async def workflow(run_id: str, case_ids: list[str]) -> None:
        with trace_run(port, f"run:{run_id}", session_id=f"sess:{run_id}") as run_obs:
            for case_id in case_ids:
                await asyncio.sleep(0.01)
                with trace_span(port, f"case:{case_id}") as case_obs:
                    assert getattr(case_obs, "parent", None) is run_obs
                    await asyncio.sleep(0.01)
                    with trace_generation(port, f"gen:{case_id}") as gen_obs:
                        assert getattr(gen_obs, "parent", None) is case_obs
                        await asyncio.sleep(0.01)

    await asyncio.gather(
        workflow("A", ["c1", "c2"]),
        workflow("B", ["c3", "c4"]),
    )

    assert len(port.traces) == 2
    run_a = next(t for t in port.traces if t.name == "run:A")
    run_b = next(t for t in port.traces if t.name == "run:B")

    for span in port.spans:
        if span.name in ("case:c1", "case:c2"):
            assert span.parent is run_a
        elif span.name in ("case:c3", "case:c4"):
            assert span.parent is run_b

    for gen in port.generations:
        if gen.name in ("gen:c1", "gen:c2"):
            assert gen.parent.parent is run_a  # type: ignore[union-attr]
        elif gen.name in ("gen:c3", "gen:c4"):
            assert gen.parent.parent is run_b  # type: ignore[union-attr]
