from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI


class OpenAICompatibleModel:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    async def complete(self, prompt: str) -> dict[str, object]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        choice = response.choices[0] if response.choices else None
        message = choice.message.content if choice and choice.message.content else ""
        return {
            "content": message,
            "usage": response.usage.model_dump() if response.usage else {},
            "model": response.model,
            "finishReason": choice.finish_reason if choice else "empty",
            "refusal": getattr(choice.message, "refusal", None) if choice else None,
        }

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"
        response = await self.client.chat.completions.create(**request)
        if not response.choices:
            return {"message": {"role": "assistant", "content": ""}, "usage": {}}
        message = response.choices[0].message
        return {
            "message": message.model_dump(exclude_none=True),
            "usage": response.usage.model_dump() if response.usage else {},
            "model": response.model,
            "finishReason": response.choices[0].finish_reason,
        }
