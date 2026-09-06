from __future__ import annotations

import base64
import json
from typing import Any, cast

from gamr_engine.ports.models import ModelImage
from gamr_engine.ports.tracing import TracePort, trace_generation
from openai import AsyncOpenAI, BadRequestError

from .streaming import ModelStreamCallback, stream_chat_completion


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
    stream_reasoning = getattr(response, "_gamr_reasoning", None)
    reasoning = (
        stream_reasoning
        if isinstance(stream_reasoning, str)
        else _reasoning_text(message)
    )
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
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        trace_port: TracePort | None = None,
        stream_callback: ModelStreamCallback | None = None,
    ) -> None:
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.trace_port = trace_port
        self.stream_callback = stream_callback

    async def _response(self, request: dict[str, Any], method: str) -> Any:
        if self.stream_callback is None:
            return await self.client.chat.completions.create(**cast(Any, request))
        return await stream_chat_completion(
            self.client.chat.completions.create,
            request,
            model=self.model,
            method=method,
            callback=self.stream_callback,
        )


    async def complete(self, prompt: str) -> dict[str, object]:
        with trace_generation(
            self.trace_port,
            "complete",
            model=self.model,
            input={"prompt": prompt},
        ) as gen_obs:
            response = await self._response(
                {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 8192,
                },
                "complete",
            )
            payload = _completion_payload(response)
            if gen_obs is not None:
                gen_obs.end(
                    output=payload,
                    usage=cast(dict[str, object], payload.get("usage")),
                    metadata={
                        "finishReason": payload.get("finishReason"),
                        "refusal": payload.get("refusal"),
                        "reasoning": payload.get("reasoning"),
                    },
                )
            return payload

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str,
        json_schema: dict[str, object],
        schema_name: str = "case_assessment",
        max_tokens: int = 8192,
    ) -> dict[str, object]:
        request: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
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
        with trace_generation(
            self.trace_port,
            "complete_structured",
            model=self.model,
            input=request,
            metadata={"schema_name": schema_name},
        ) as gen_obs:
            payload = await self._structured_response(request, "complete_structured")
            if gen_obs is not None:
                gen_obs.end(
                    output=payload,
                    usage=cast(dict[str, object], payload.get("usage")),
                    metadata={
                        "finishReason": payload.get("finishReason"),
                        "refusal": payload.get("refusal"),
                        "reasoning": payload.get("reasoning"),
                    },
                )
            return payload

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
        with trace_generation(
            self.trace_port,
            "complete_multimodal_structured",
            model=self.model,
            input=request,
            metadata={"schema_name": schema_name},
        ) as gen_obs:
            payload = await self._structured_response(
                request, "complete_multimodal_structured"
            )
            if gen_obs is not None:
                gen_obs.end(
                    output=payload,
                    usage=cast(dict[str, object], payload.get("usage")),
                    metadata={
                        "finishReason": payload.get("finishReason"),
                        "refusal": payload.get("refusal"),
                        "reasoning": payload.get("reasoning"),
                    },
                )
            return payload

    async def _structured_response(
        self, request: dict[str, object], method: str
    ) -> dict[str, object]:
        try:
            response = await self._response(request, method)
        except BadRequestError:
            request["response_format"] = {"type": "json_object"}
            response = await self._response(request, method)
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
        with trace_generation(
            self.trace_port,
            "chat",
            model=self.model,
            input=request,
        ) as gen_obs:
            response = await self._response(request, "chat")
            if not response.choices:
                payload: dict[str, Any] = {
                    "message": {"role": "assistant", "content": ""},
                    "usage": {},
                }
            else:
                message = response.choices[0].message
                payload = {
                    "message": message.model_dump(exclude_none=True),
                    "usage": response.usage.model_dump() if response.usage else {},
                    "model": response.model,
                    "finishReason": response.choices[0].finish_reason,
                }
            if gen_obs is not None:
                gen_obs.end(
                    output=payload,
                    usage=cast(dict[str, object], payload.get("usage")),
                    metadata={"finishReason": payload.get("finishReason")},
                )
            return payload
