from __future__ import annotations

from types import SimpleNamespace

import pytest
from gamr_adapters.models import openai_compatible
from httpx import Request, Response
from openai import BadRequestError


class FakeCompletions:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    async def create(self, **request: object) -> SimpleNamespace:
        self.request = request
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"ok":true}', refusal=None),
                    finish_reason="stop",
                )
            ],
            usage=None,
            model="test-model",
        )


class FakeClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


class SchemaRejectingCompletions(FakeCompletions):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[dict[str, object]] = []

    async def create(self, **request: object) -> SimpleNamespace:
        self.requests.append(request)
        if len(self.requests) == 1:
            response = Response(400, request=Request("POST", "https://example.test/v1"))
            raise BadRequestError("json_schema unsupported", response=response, body={})
        return await super().create(**request)


@pytest.mark.asyncio
async def test_complete_sets_a_large_enough_json_completion_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completions = FakeCompletions()
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: FakeClient(completions),
    )

    model = openai_compatible.OpenAICompatibleModel("https://example.test/v1", "key", "test-model")
    await model.complete("Return JSON.")

    assert completions.request is not None
    assert completions.request["max_tokens"] == 8192


@pytest.mark.asyncio
async def test_complete_structured_uses_system_instruction_and_strict_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completions = FakeCompletions()
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: FakeClient(completions),
    )
    schema = {
        "type": "object",
        "properties": {"verdict": {"type": "string"}},
        "required": ["verdict"],
        "additionalProperties": False,
    }

    model = openai_compatible.OpenAICompatibleModel(
        "https://example.test/v1", "key", "test-model"
    )
    await model.complete_structured("Evidence", system="Judge safely", json_schema=schema)

    assert completions.request is not None
    assert completions.request["messages"] == [
        {"role": "system", "content": "Judge safely"},
        {"role": "user", "content": "Evidence"},
    ]
    assert completions.request["temperature"] == 0
    assert completions.request["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "case_assessment",
            "strict": True,
            "schema": schema,
        },
    }


@pytest.mark.asyncio
async def test_complete_structured_falls_back_to_json_mode_when_schema_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completions = SchemaRejectingCompletions()
    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: FakeClient(completions),
    )
    model = openai_compatible.OpenAICompatibleModel(
        "https://example.test/v1", "key", "test-model"
    )

    result = await model.complete_structured(
        "Evidence",
        system="Judge safely",
        json_schema={"type": "object"},
    )

    assert result["content"] == '{"ok":true}'
    assert len(completions.requests) == 2
    assert completions.requests[1]["response_format"] == {"type": "json_object"}
