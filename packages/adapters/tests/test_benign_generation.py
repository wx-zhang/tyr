import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from gamr_adapters.benign_model import BenignModel, RecordedModel
from gamr_adapters.benign_store import BenignStore


def completion(content: str | None, finish: str = "stop") -> dict[str, Any]:
    return {
        "id": "test",
        "created": 0,
        "object": "chat.completion",
        "model": "test",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "reasoning": '{"input":"echo"}',
                },
            }
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content,finish,expected",
    [
        (None, "length", "token limit"),
        (None, "stop", "no final answer"),
        ('{"ok": true}', "length", "token limit"),
    ],
)
async def test_incomplete_response_never_recovers_reasoning(
    tmp_path: Path,
    content: str | None,
    finish: str,
    expected: str,
) -> None:
    model = RecordedModel(
        "https://openrouter.ai/api/v1", "test", "test", BenignStore(tmp_path), "run"
    )
    await model.client.close()
    model.client = model.client.with_options(
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=completion(content, finish))
            ),
        )
    )
    try:
        with pytest.raises(RuntimeError, match=expected):
            await model.complete_structured("input", system="compile", json_schema={})
        assert list((tmp_path / "run" / "evidence").glob("*.json"))
    finally:
        await model.client.close()


@pytest.mark.asyncio
async def test_draft_sends_reasoning_control_and_accepts_final_json(tmp_path: Path) -> None:
    model = RecordedModel(
        "https://openrouter.ai/api/v1",
        "test",
        "test",
        BenignStore(tmp_path),
        "run",
        disable_reasoning=True,
    )
    captured = []

    def reply(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=completion('{"ok":true}'))

    await model.client.close()
    model.client = model.client.with_options(
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(reply),
        )
    )
    try:
        result = await model.complete_structured("input", system="compile", json_schema={})
        assert result["content"] == '{"ok":true}'
        assert captured[0]["reasoning"] == {"effort": "none"}
    finally:
        await model.client.close()


@pytest.mark.asyncio
async def test_generation_deadline_is_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr("gamr_adapters.benign_model.MODEL_TIMEOUT_SECONDS", 0.01)
    cancelled = asyncio.Event()

    async def slow(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            await asyncio.sleep(5)
        finally:
            cancelled.set()
        return {}

    monkeypatch.setattr(RecordedModel, "complete_structured", slow)
    with pytest.raises(RuntimeError, match="timed out"):
        await BenignModel(BenignStore(tmp_path)).complete("run", "compile", {}, {})
    assert cancelled.is_set()
    assert any(
        '"type": "model.error"' in path.read_text()
        for path in (tmp_path / "run" / "evidence").glob("*.json")
    )
