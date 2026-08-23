from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any, cast

from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_engine.ports.models import ModelImage

from .judge_evaluation_debug import DebugSink, format_llm_debug


class TracedModel:
    def __init__(
        self,
        model: Any,
        store: FilesystemArtifactStore,
        evaluation_id: str,
        progress: Callable[[str], None] | None = None,
        debug: DebugSink | None = None,
    ) -> None:
        self.wrapped = model
        self.model = getattr(model, "model", type(model).__name__)
        self.store = store
        self.evaluation_id = evaluation_id
        self.progress = progress or (lambda _message: None)
        self.debug = debug
        self.case_id = "unassigned"
        self.calls = 0
        self.usage: dict[str, int] = {}

    def set_case(self, case_id: str) -> None:
        self.case_id = case_id

    def _debug(self, direction: str, call_number: int, method: str, payload: Any) -> None:
        if self.debug is None:
            return
        self.debug(format_llm_debug(direction, self.case_id, call_number, method, payload))

    @staticmethod
    def _safe_usage(value: Any) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        return {
            re.sub("tokens?", "units", str(key), flags=re.IGNORECASE): item
            for key, item in value.items()
            if isinstance(item, int)
        }

    async def _call(self, method: str, request: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        call_number = self.calls
        self.progress(f"[{self.case_id}] LLM call {call_number} started: {method}")
        self._debug("request", call_number, method, request)
        serialized = json.dumps(request, sort_keys=True, default=str).encode()
        request_digest = hashlib.sha256(serialized).hexdigest()
        try:
            response = cast(dict[str, Any], await getattr(self.wrapped, method)(**kwargs))
        except Exception as error:
            self._debug("response", call_number, method, {"error": type(error).__name__})
            self.progress(
                f"[{self.case_id}] LLM call {call_number} failed: "
                f"{method} ({type(error).__name__})"
            )
            self.store.append_event(
                self.evaluation_id,
                {
                    "eventType": "model.response",
                    "method": method,
                    "requestSha256": request_digest,
                    "error": type(error).__name__,
                },
            )
            raise
        self._debug("response", call_number, method, response)
        content = response.get("content", response.get("message", ""))
        response_digest = hashlib.sha256(
            json.dumps(content, sort_keys=True, default=str).encode()
        ).hexdigest()
        usage = self._safe_usage(response.get("usage", {}))
        for key, value in usage.items():
            self.usage[key] = self.usage.get(key, 0) + value
        self.store.append_event(
            self.evaluation_id,
            {
                "eventType": "model.response",
                "method": method,
                "model": response.get("model", self.model),
                "requestSha256": request_digest,
                "responseSha256": response_digest,
                "finishReason": response.get("finishReason"),
                "refusal": bool(response.get("refusal")),
                "usage": usage,
            },
        )
        self.progress(f"[{self.case_id}] LLM call {call_number} completed: {method}")
        return response

    async def complete(self, prompt: str) -> dict[str, Any]:
        return await self._call("complete", prompt, prompt=prompt)

    async def complete_structured(
        self, prompt: str, *, system: str, json_schema: dict[str, Any]
    ) -> dict[str, Any]:
        request = {"prompt": prompt, "system": system, "jsonSchema": json_schema}
        return await self._call(
            "complete_structured",
            request,
            prompt=prompt,
            system=system,
            json_schema=json_schema,
        )

    async def complete_multimodal_structured(
        self,
        prompt: str,
        *,
        images: list[ModelImage],
        system: str,
        json_schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        image_meta = [
            {
                "uploadedItemId": item.uploaded_item_id,
                "contentType": item.content_type,
                "size": len(item.content),
                "sha256": hashlib.sha256(item.content).hexdigest(),
            }
            for item in images
        ]
        request = {"prompt": prompt, "images": image_meta, "system": system, "schema": json_schema}
        return await self._call(
            "complete_multimodal_structured",
            request,
            prompt=prompt,
            images=images,
            system=system,
            json_schema=json_schema,
            schema_name=schema_name,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        request = {"messages": messages, "tools": tools, "maxTokens": max_tokens}
        return await self._call(
            "chat", request, messages=messages, tools=tools, max_tokens=max_tokens
        )
