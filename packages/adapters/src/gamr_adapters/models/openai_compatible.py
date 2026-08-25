from __future__ import annotations

import base64
from typing import Any, cast

from gamr_engine.ports.models import ModelImage
from openai import AsyncOpenAI, BadRequestError


class OpenAICompatibleModel:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    async def complete(self, prompt: str) -> dict[str, object]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
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

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str,
        json_schema: dict[str, object],
    ) -> dict[str, object]:
        request: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 8192,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "case_assessment",
                    "strict": True,
                    "schema": json_schema,
                },
            },
        }
        return await self._structured_response(request)

    async def complete_multimodal_structured(
        self,
        prompt: str,
        *,
        images: list[ModelImage],
        system: str,
        json_schema: dict[str, object],
        schema_name: str,
    ) -> dict[str, object]:
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        for image in images:
            encoded = base64.b64encode(image.content).decode()
            content.extend(
                [
                    {
                        "type": "text",
                        "text": f"Uploaded image item: {image.uploaded_item_id}",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image.content_type};base64,{encoded}",
                            "detail": "high",
                        },
                    },
                ]
            )
        request: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "max_tokens": 8192,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": json_schema,
                },
            },
        }
        return await self._structured_response(request)

    async def _structured_response(self, request: dict[str, object]) -> dict[str, object]:
        try:
            response = await self.client.chat.completions.create(**cast(Any, request))
        except BadRequestError:
            request["response_format"] = {"type": "json_object"}
            response = await self.client.chat.completions.create(**cast(Any, request))
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
