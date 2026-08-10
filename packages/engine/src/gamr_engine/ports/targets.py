from __future__ import annotations

from typing import Protocol


class TargetGateway(Protocol):
    async def initialize(self) -> dict[str, object]: ...

    async def list_tools(self) -> list[dict[str, object]]: ...

    async def call_tool(
        self, name: str, arguments: dict[str, object], *, timeout: float = 60
    ) -> dict[str, object]: ...

    async def request(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]: ...

    async def query(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]: ...

    async def operation_status(
        self, operation_id: str, *, wait_seconds: int = 0
    ) -> dict[str, object]: ...

    async def settle(
        self, result: dict[str, object], *, operation_id: str | None = None
    ) -> dict[str, object]: ...


class ApprovalGateway(Protocol):
    async def request(self, tool_name: str, arguments: dict[str, object]) -> bool: ...
