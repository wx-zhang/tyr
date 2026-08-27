from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelImage:
    uploaded_item_id: str
    content_type: str
    content: bytes


class ModelGateway(Protocol):
    async def complete(self, prompt: str) -> dict[str, object]: ...


class StructuredModelGateway(ModelGateway, Protocol):
    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str,
        json_schema: dict[str, object],
        schema_name: str = "case_assessment",
        max_tokens: int = 8192,
    ) -> dict[str, object]: ...


class MultimodalStructuredModelGateway(StructuredModelGateway, Protocol):
    async def complete_multimodal_structured(
        self,
        prompt: str,
        *,
        images: list[ModelImage],
        system: str,
        json_schema: dict[str, object],
        schema_name: str,
    ) -> dict[str, object]: ...


class ChatModelGateway(Protocol):
    async def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, object]: ...
