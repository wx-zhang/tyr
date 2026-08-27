from __future__ import annotations

from typing import Any

import pytest
from gamr_engine.chat import ChatSession
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
        pass


class RecordingTracePort:
    def __init__(self) -> None:
        self.traces: list[FakeObs] = []
        self.spans: list[FakeObs] = []
        self.generations: list[FakeObs] = []

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
        parent: TraceObservation | None = None,
    ) -> FakeObs:
        obs = FakeObs(
            name,
            "trace",
            parent=parent,
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
        pass

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
        parent: TraceObservation | None = None,
    ) -> FakeObs:
        raise RuntimeError("Trace open failed")

    def open_span(
        self,
        name: str,
        *,
        metadata: dict[str, object] | None = None,
        input: object = None,
        output: object = None,
        parent: TraceObservation | None = None,
    ) -> FakeObs:
        raise RuntimeError("Span open failed")

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
        raise RuntimeError("Gen open failed")

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        observation: TraceObservation | None = None,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        raise RuntimeError("Score failed")

    def flush(self, timeout: float | None = None) -> None:
        pass


class FakeModel:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = iter(responses)

    async def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, object]:
        return next(self.responses)


class FakeTarget:
    async def initialize(self) -> dict[str, object]:
        return {"ok": True}

    async def list_tools(self) -> list[dict[str, object]]:
        return [
            {"name": "tyr_assistant_query", "inputSchema": {"type": "object"}},
        ]

    async def start_conversation(self, *, idempotency_key: str) -> dict[str, object]:
        return {"conversationId": "conv-test-123"}

    async def call_tool(
        self, name: str, arguments: dict[str, object], **kw: Any
    ) -> dict[str, object]:
        return {"state": "completed", "response": "done"}

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


@pytest.mark.asyncio
async def test_chat_traces_turns_grouped_by_conversation_id() -> None:
    port = RecordingTracePort()
    model = FakeModel(
        [
            {"message": {"role": "assistant", "content": "turn 1 reply"}},
            {"message": {"role": "assistant", "content": "turn 2 reply"}},
        ]
    )
    target = FakeTarget()
    session = ChatSession(model=model, target=target, trace_port=port)

    messages: list[dict[str, object]] = []
    reply1 = await session.run_turn(messages, "hello turn 1")
    assert reply1 == "turn 1 reply"

    reply2 = await session.run_turn(messages, "hello turn 2")
    assert reply2 == "turn 2 reply"

    assert len(port.traces) == 2
    assert port.traces[0].kwargs["session_id"] == "conv-test-123"
    assert port.traces[0].kwargs["input"] == "hello turn 1"
    assert port.traces[0].ended is True

    assert port.traces[1].kwargs["session_id"] == "conv-test-123"
    assert port.traces[1].kwargs["input"] == "hello turn 2"
    assert port.traces[1].ended is True


@pytest.mark.asyncio
async def test_chat_tracing_failure_does_not_break_turn() -> None:
    port = FailingTracePort()
    model = FakeModel([{"message": {"role": "assistant", "content": "safe reply"}}])
    target = FakeTarget()
    session = ChatSession(model=model, target=target, trace_port=port)

    messages: list[dict[str, object]] = []
    reply = await session.run_turn(messages, "hello with broken trace")
    assert reply == "safe reply"
