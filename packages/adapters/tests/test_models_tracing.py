from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from gamr_adapters.models import openai_compatible
from gamr_engine.ports.models import ModelImage
from gamr_engine.ports.tracing import (
    TraceObservation,
)
from httpx import Request, Response
from openai import APIError, BadRequestError
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, Choice, ChoiceDelta
from openai.types.completion_usage import CompletionUsage


class FakeGenerationObs:
    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.kwargs = kwargs
        self.model = kwargs.get("model")
        self.ended = False
        self.output: Any = None
        self.usage: Any = None
        self.metadata: dict[str, Any] = dict(kwargs.get("metadata") or {})
        self.error: Any = None

    def update(self, **kwargs: Any) -> None:
        if "output" in kwargs:
            self.output = kwargs["output"]
        if "usage" in kwargs:
            self.usage = kwargs["usage"]
        if "metadata" in kwargs:
            self.metadata.update(kwargs["metadata"])

    def end(self, **kwargs: Any) -> None:
        self.ended = True
        self.update(**kwargs)
        if "error" in kwargs:
            self.error = kwargs["error"]

    def score(self, name: str, value: Any, **kwargs: Any) -> None:
        pass


class FakeTracer:
    def __init__(self) -> None:
        self.generations: list[FakeGenerationObs] = []

    def open_trace(self, name: str, **kwargs: Any) -> TraceObservation:
        raise NotImplementedError

    def open_span(self, name: str, **kwargs: Any) -> TraceObservation:
        raise NotImplementedError

    def open_generation(self, name: str, **kwargs: Any) -> TraceObservation:
        obs = FakeGenerationObs(name, **kwargs)
        self.generations.append(obs)
        return obs  # type: ignore[return-value]

    def score(self, name: str, value: Any, **kwargs: Any) -> None:
        pass

    def flush(self, timeout: float | None = None) -> None:
        pass


class FakeCompletions:
    def __init__(self, message: SimpleNamespace | None = None, should_error: bool = False) -> None:
        self.request: dict[str, object] | None = None
        self.message = message or SimpleNamespace(content='{"verdict":"deny"}', refusal=None)
        self.should_error = should_error

    async def create(self, **request: object) -> SimpleNamespace:
        self.request = request
        if self.should_error:
            raise APIError(
                "provider timeout", request=Request("POST", "https://example.test"), body=None
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=self.message,
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(model_dump=lambda: {"total_tokens": 50}),
            model="test-model",
        )


class FallbackCompletions(FakeCompletions):
    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    async def create(self, **request: object) -> SimpleNamespace:
        self.attempts += 1
        if self.attempts == 1:
            response = Response(400, request=Request("POST", "https://example.test/v1"))
            raise BadRequestError("json_schema unsupported", response=response, body={})
        return await super().create(**request)


@pytest.mark.asyncio
async def test_traced_plain_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = FakeCompletions()
    tracer = FakeTracer()
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    model = openai_compatible.OpenAICompatibleModel(
        "https://example.test/v1", "key", "test-model", trace_port=tracer
    )

    result = await model.complete("hello")
    assert result["content"] == '{"verdict":"deny"}'
    assert len(tracer.generations) == 1
    gen = tracer.generations[0]
    assert gen.ended is True
    assert gen.model == "test-model"
    assert gen.output == result
    assert gen.usage == {"total_tokens": 50}


@pytest.mark.asyncio
async def test_traced_structured_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = FakeCompletions()
    tracer = FakeTracer()
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    model = openai_compatible.OpenAICompatibleModel(
        "https://example.test/v1", "key", "test-model", trace_port=tracer
    )

    result = await model.complete_structured(
        "Evidence", system="System", json_schema={"type": "object"}, schema_name="test_schema"
    )
    assert result["content"] == '{"verdict":"deny"}'
    assert len(tracer.generations) == 1
    gen = tracer.generations[0]
    assert gen.ended is True
    assert gen.output == result


@pytest.mark.asyncio
async def test_traced_structured_fallback_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = FallbackCompletions()
    tracer = FakeTracer()
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    model = openai_compatible.OpenAICompatibleModel(
        "https://example.test/v1", "key", "test-model", trace_port=tracer
    )

    result = await model.complete_structured(
        "Evidence", system="System", json_schema={"type": "object"}
    )
    assert result["content"] == '{"verdict":"deny"}'
    assert len(tracer.generations) == 1
    assert tracer.generations[0].ended is True


@pytest.mark.asyncio
async def test_traced_multimodal_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = FakeCompletions()
    tracer = FakeTracer()
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    model = openai_compatible.OpenAICompatibleModel(
        "https://example.test/v1", "key", "test-model", trace_port=tracer
    )
    image = ModelImage("upload-1", "image/png", b"data")

    result = await model.complete_multimodal_structured(
        "Look at this",
        images=[image],
        system="System",
        json_schema={"type": "object"},
        schema_name="multimodal_schema",
    )
    assert result["content"] == '{"verdict":"deny"}'
    assert len(tracer.generations) == 1
    assert tracer.generations[0].ended is True


@pytest.mark.asyncio
async def test_traced_chat_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    message = SimpleNamespace(
        content="hello back",
        role="assistant",
        model_dump=lambda **kw: {"role": "assistant", "content": "hello back"},
    )
    completions = FakeCompletions(message=message)
    tracer = FakeTracer()
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    model = openai_compatible.OpenAICompatibleModel(
        "https://example.test/v1", "key", "test-model", trace_port=tracer
    )

    result = await model.chat([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
    assert result["message"]["content"] == "hello back"
    assert len(tracer.generations) == 1
    assert tracer.generations[0].ended is True


@pytest.mark.asyncio
async def test_traced_provider_error_records_error_and_re_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completions = FakeCompletions(should_error=True)
    tracer = FakeTracer()
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    model = openai_compatible.OpenAICompatibleModel(
        "https://example.test/v1", "key", "test-model", trace_port=tracer
    )

    with pytest.raises(APIError, match="provider timeout"):
        await model.complete("hello")

    assert len(tracer.generations) == 1
    assert tracer.generations[0].ended is True
    assert tracer.generations[0].error is not None


def _trace_chunk(
    *,
    content: str | None = None,
    reasoning: str | None = None,
    finish_reason: str | None = None,
    usage: CompletionUsage | None = None,
) -> ChatCompletionChunk:
    delta_data: dict[str, Any] = {"content": content}
    if reasoning is not None:
        delta_data["reasoning"] = reasoning
    delta = cast(Any, ChoiceDelta)(**delta_data)
    return ChatCompletionChunk(
        id="trace-stream",
        choices=[
            Choice(index=0, delta=delta, finish_reason=cast(Any, finish_reason))
        ],
        created=1,
        model="trace-model",
        object="chat.completion.chunk",
        usage=usage,
    )


class TraceStreamingCompletions:
    def __init__(self, chunks: list[ChatCompletionChunk]) -> None:
        self.chunks = chunks

    async def create(self, **_request: object) -> Any:
        async def stream() -> Any:
            for chunk in self.chunks:
                yield chunk

        return stream()


def _streaming_trace_model(
    monkeypatch: pytest.MonkeyPatch,
    tracer: FakeTracer,
    completions: TraceStreamingCompletions,
    callback: Any,
) -> openai_compatible.OpenAICompatibleModel:
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: SimpleNamespace(
            chat=SimpleNamespace(completions=completions)
        ),
    )
    return openai_compatible.OpenAICompatibleModel(
        "https://example.test/v1",
        "key",
        "test-model",
        trace_port=tracer,
        stream_callback=callback,
    )


@pytest.mark.asyncio
async def test_traced_streaming_completion_ends_one_generation_with_final_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usage = CompletionUsage(completion_tokens=3, prompt_tokens=2, total_tokens=5)
    completions = TraceStreamingCompletions(
        [
            _trace_chunk(reasoning="plan "),
            _trace_chunk(content="answer"),
            _trace_chunk(finish_reason="stop"),
            _trace_chunk(usage=usage),
        ]
    )
    tracer = FakeTracer()
    model = _streaming_trace_model(monkeypatch, tracer, completions, lambda _event: None)

    result = await model.complete("hello")

    assert result["content"] == "answer"
    assert result["reasoning"] == "plan "
    assert result["usage"] == usage.model_dump()
    assert len(tracer.generations) == 1
    generation = tracer.generations[0]
    assert generation.ended is True
    assert generation.output == result
    assert generation.usage == usage.model_dump()


@pytest.mark.asyncio
async def test_stream_callback_failure_does_not_change_traced_model_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completions = TraceStreamingCompletions(
        [_trace_chunk(content="answer"), _trace_chunk(finish_reason="stop")]
    )
    tracer = FakeTracer()

    def fail_callback(_event: object) -> None:
        raise RuntimeError("console failed")

    model = _streaming_trace_model(monkeypatch, tracer, completions, fail_callback)

    result = await model.complete("hello")

    assert result["content"] == "answer"
    assert len(tracer.generations) == 1
    assert tracer.generations[0].ended is True
