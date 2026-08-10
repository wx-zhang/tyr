import pytest
from gamr_engine.chat import ChatSession


class FakeModel:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = iter(responses)
        self.tools_seen: list[list[dict[str, object]] | None] = []

    async def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, object]:
        self.tools_seen.append(tools)
        return next(self.responses)


class FakeTarget:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def initialize(self) -> dict[str, object]:
        return {"ok": True}

    async def list_tools(self) -> list[dict[str, object]]:
        return [
            {"name": "tyr_assistant_query", "inputSchema": {"type": "object"}},
            {"name": "tyr_assistant_request", "inputSchema": {"type": "object"}},
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object],
        *,
        timeout: float = 60,
    ) -> dict[str, object]:
        self.calls.append((name, arguments))
        return {"state": "completed", "response": "done"}

    async def query(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        return await self.call_tool("tyr_assistant_query", {"message": prompt})

    async def request(
        self,
        prompt: str,
        *,
        operation_id: str | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        return await self.call_tool("tyr_assistant_request", {"message": prompt})

    async def operation_status(
        self, operation_id: str, *, wait_seconds: int = 0
    ) -> dict[str, object]:
        return {"state": "completed", "operationId": operation_id}

    async def settle(
        self, result: dict[str, object], *, operation_id: str | None = None
    ) -> dict[str, object]:
        return result


@pytest.mark.asyncio
async def test_read_only_chat_exposes_observational_tools_only() -> None:
    model = FakeModel([{"message": {"role": "assistant", "content": "hello"}}])
    target = FakeTarget()
    session = ChatSession(model, target)
    assert await session.connect() == ("tyr_assistant_query",)
    assert await session.run_turn([], "status") == "hello"
    assert model.tools_seen[0] == [
        {
            "type": "function",
            "function": {
                "name": "tyr_assistant_query",
                "description": "Call Tyr MCP tool tyr_assistant_query.",
                "parameters": {"type": "object"},
            },
        }
    ]


@pytest.mark.asyncio
async def test_action_tool_requires_approval_and_idempotency() -> None:
    model = FakeModel(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "name": "tyr_assistant_request",
                                "arguments": '{"message":"do it"}',
                            },
                        }
                    ],
                }
            },
            {"message": {"role": "assistant", "content": "finished"}},
        ]
    )
    target = FakeTarget()
    approved: list[tuple[str, dict[str, object]]] = []

    async def approve(name: str, arguments: dict[str, object]) -> bool:
        approved.append((name, arguments))
        return True

    session = ChatSession(model, target, action_mode="approval_required", approve=approve)
    assert await session.run_turn([], "request") == "finished"
    assert approved[0][0] == "tyr_assistant_request"
    assert isinstance(approved[0][1]["idempotencyKey"], str)
    assert target.calls == [("tyr_assistant_request", approved[0][1])]


@pytest.mark.asyncio
async def test_read_only_query_can_be_upgraded_once_after_server_rejection() -> None:
    model = FakeModel(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "query-1",
                            "function": {
                                "name": "tyr_assistant_query",
                                "arguments": '{"message":"upload the file"}',
                            },
                        }
                    ],
                }
            },
            {"message": {"role": "assistant", "content": "finished"}},
        ]
    )
    target = FakeTarget()
    target.list_tools = upgraded_tools  # type: ignore[method-assign]

    async def query_reject(
        name: str,
        arguments: dict[str, object],
        *,
        timeout: float = 60,
    ) -> dict[str, object]:
        target.calls.append((name, arguments))
        if name == "tyr_assistant_query":
            return {
                "error": {
                    "actionModeRequired": True,
                    "newOperationRequired": True,
                    "requiredTool": "tyr_assistant_request",
                }
            }
        return {"state": "completed", "response": "uploaded"}

    target.call_tool = query_reject  # type: ignore[method-assign]
    approved: list[str] = []

    async def approve(name: str, _: dict[str, object]) -> bool:
        approved.append(name)
        return True

    session = ChatSession(model, target, approve=approve)
    assert await session.run_turn([], "request") == "finished"
    assert approved == ["tyr_assistant_request"]
    assert [name for name, _ in target.calls] == [
        "tyr_assistant_query",
        "tyr_assistant_request",
    ]


async def upgraded_tools() -> list[dict[str, object]]:
    return [
        {
            "name": "tyr_assistant_query",
            "annotations": {"readOnlyHint": True},
            "inputSchema": {"type": "object"},
        },
        {
            "name": "tyr_assistant_request",
            "annotations": {"readOnlyHint": False},
            "inputSchema": {"type": "object"},
        },
    ]
