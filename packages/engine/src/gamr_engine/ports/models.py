from __future__ import annotations

from typing import Protocol


class ModelGateway(Protocol):
    async def complete(self, prompt: str) -> dict[str, object]: ...


class ChatModelGateway(Protocol):
    async def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, object]: ...
