from __future__ import annotations

from types import SimpleNamespace

import pytest
from gamr_adapters.models import openai_compatible


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
