from __future__ import annotations

import base64
import json
from typing import Any, cast

from gamr_engine.ports.models import ModelImage
from openai import AsyncOpenAI, BadRequestError


def _reasoning_text(message: Any) -> str:
    if message is None:
        return ""
    for attr in ("reasoning", "reasoning_content"):
        value = getattr(message, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    extra = getattr(message, "model_extra", None)
    if isinstance(extra, dict):
        for key in ("reasoning", "reasoning_content"):
            value = extra.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _json_object_text(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
    decoder = json.JSONDecoder()
    try:
        payload, end = decoder.raw_decode(stripped)
        if isinstance(payload, dict):
            return stripped[:end]
    except json.JSONDecodeError:
        pass
    for index, character in enumerate(stripped):
        if character != "{":
            continue
        try:
            payload, end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return stripped[index : index + end]
    return None


def _completion_payload(response: Any) -> dict[str, object]:
    choice = response.choices[0] if response.choices else None
    message = choice.message if choice else None
    content = message.content if message and message.content else ""
    reasoning = _reasoning_text(message)
    if not isinstance(content, str) or not content.strip():
        extracted = _json_object_text(reasoning) if reasoning else None
        if extracted:
            content = extracted
    payload: dict[str, object] = {
        "content": content if isinstance(content, str) else "",
        "usage": response.usage.model_dump() if response.usage else {},
        "model": response.model,
        "finishReason": choice.finish_reason if choice else "empty",
        "refusal": getattr(message, "refusal", None) if message else None,
    }
    if reasoning:
        payload["reasoning"] = reasoning
    return payload


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
        return _completion_payload(response)

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
        return _completion_payload(response)

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
