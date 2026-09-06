from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import uuid4

from openai.lib.streaming.chat import ChatCompletionStreamState


@dataclass(frozen=True)
class ModelStreamEvent:
    request_id: str
    model: str
    method: str
    kind: Literal["started", "thinking", "completed", "failed"]
    delta: str = ""


ModelStreamCallback = Callable[[ModelStreamEvent], None]


def _emit(callback: ModelStreamCallback, event: ModelStreamEvent) -> None:
    try:
        callback(event)
    except Exception:
        pass


def _reasoning_deltas(delta: Any) -> list[str]:
    values: list[str] = []
    extra = getattr(delta, "model_extra", None)
    for name in ("reasoning", "reasoning_content"):
        value = getattr(delta, name, None)
        if not isinstance(value, str) and isinstance(extra, dict):
            value = extra.get(name)
        if isinstance(value, str) and value:
            values.append(value)
    return values


async def stream_chat_completion(
    create: Callable[..., Awaitable[Any]],
    request: dict[str, object],
    *,
    model: str,
    method: str,
    callback: ModelStreamCallback,
) -> Any:
    request_id = uuid4().hex
    _emit(callback, ModelStreamEvent(request_id, model, method, "started"))
    state = ChatCompletionStreamState()
    reasoning: list[str] = []
    try:
        stream = await create(
            **request,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            state.handle_chunk(chunk)
            choices = getattr(chunk, "choices", ())
            for choice in choices:
                for value in _reasoning_deltas(getattr(choice, "delta", None)):
                    reasoning.append(value)
                    _emit(callback, ModelStreamEvent(request_id, model, method, "thinking", value))
        response = state.get_final_completion()
        cast(Any, response)._gamr_reasoning = "".join(reasoning)
        _emit(callback, ModelStreamEvent(request_id, model, method, "completed"))
        return response
    except BaseException:
        _emit(callback, ModelStreamEvent(request_id, model, method, "failed"))
        raise
