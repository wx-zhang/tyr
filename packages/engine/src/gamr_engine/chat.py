from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import uuid4

from .ports.models import ChatModelGateway
from .ports.targets import TargetGateway

ApprovalCallback = Callable[[str, dict[str, object]], Awaitable[bool]]

LEGACY_READ_ONLY_TOOLS = frozenset(
    {
        "tyr_assistant_query",
        "tyr_operation_status",
        "tyr_workspace_bridge_list",
        "tyr_workspace_bridge_status",
        "tyr_workspace_bridge_history",
    }
)
ASSISTANT_CONVERSATION_TOOLS = frozenset({"tyr_assistant_query", "tyr_assistant_request"})


@dataclass
class ChatSession:
    model: ChatModelGateway
    target: TargetGateway
    action_mode: str = "read_only"
    approve: ApprovalCallback | None = None
    max_tool_rounds: int = 8
    max_tokens: int = 1024
    conversation_id: str | None = None

    @staticmethod
    def _is_action_tool(name: str) -> bool:
        return name not in LEGACY_READ_ONLY_TOOLS

    @staticmethod
    def _tool_is_read_only(tool: dict[str, object]) -> bool:
        annotations = tool.get("annotations")
        if isinstance(annotations, dict) and isinstance(annotations.get("readOnlyHint"), bool):
            return bool(annotations["readOnlyHint"])
        name = tool.get("name")
        return isinstance(name, str) and name in LEGACY_READ_ONLY_TOOLS

    @classmethod
    def _tool_specs(
        cls, advertised: list[dict[str, object]], action_mode: str
    ) -> tuple[list[dict[str, object]], set[str], dict[str, bool]]:
        specs: list[dict[str, object]] = []
        names: set[str] = set()
        read_only_by_name: dict[str, bool] = {}
        for tool in advertised:
            name = tool.get("name")
            if not isinstance(name, str) or not name:
                continue
            if name == "tyr_assistant_start_conversation":
                continue
            read_only = cls._tool_is_read_only(tool)
            read_only_by_name[name] = read_only
            if action_mode != "approval_required" and not read_only:
                continue
            schema = tool.get("inputSchema")
            if not isinstance(schema, dict):
                schema = {"type": "object", "properties": {}}
            specs.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": str(tool.get("description") or f"Call Tyr MCP tool {name}."),
                        "parameters": schema,
                    },
                }
            )
            names.add(name)
        return specs, names, read_only_by_name

    async def connect(self) -> tuple[str, ...]:
        await self.target.initialize()
        await self._ensure_conversation()
        tools = await self.target.list_tools()
        _, names, _ = self._tool_specs(tools, self.action_mode)
        return tuple(sorted(names))

    async def _ensure_conversation(self) -> str:
        if self.conversation_id is None:
            result = await self.target.start_conversation(idempotency_key=str(uuid4()))
            conversation_id = result.get("conversationId")
            if not isinstance(conversation_id, str) or not conversation_id:
                raise RuntimeError("Tyr conversation start returned no conversationId")
            self.conversation_id = conversation_id
        return self.conversation_id

    async def run_turn(
        self,
        messages: list[dict[str, object]],
        prompt: str,
    ) -> str:
        await self._ensure_conversation()
        messages.append({"role": "user", "content": prompt})
        advertised = await self.target.list_tools()
        tool_specs, tool_names, read_only_by_name = self._tool_specs(advertised, self.action_mode)
        action_upgrade_decided = False

        for _ in range(self.max_tool_rounds):
            completion = await self.model.chat(
                messages,
                tools=tool_specs,
                max_tokens=self.max_tokens,
            )
            message = completion.get("message")
            if not isinstance(message, dict):
                raise RuntimeError("model returned no assistant message")
            messages.append(message)
            tool_calls = message.get("tool_calls")
            if not isinstance(tool_calls, list) or not tool_calls:
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise RuntimeError("model returned an empty assistant message")
                return content.strip()

            for tool_call in tool_calls:
                result, action_upgrade_decided = await self._run_tool_call(
                    tool_call,
                    tool_names,
                    read_only_by_name,
                    action_upgrade_decided,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": (
                            tool_call.get("id") if isinstance(tool_call, dict) else None
                        ),
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
        raise RuntimeError(f"reached the {self.max_tool_rounds}-round MCP tool-call limit")

    async def _run_tool_call(
        self,
        tool_call: object,
        tool_names: set[str],
        read_only_by_name: dict[str, bool],
        action_upgrade_decided: bool,
    ) -> tuple[dict[str, object], bool]:
        if not isinstance(tool_call, dict):
            return {"error": "invalid tool call"}, action_upgrade_decided
        function = tool_call.get("function")
        if not isinstance(function, dict):
            return {"error": "invalid tool function"}, action_upgrade_decided
        name = function.get("name")
        raw_arguments = function.get("arguments", "{}")
        if not isinstance(name, str) or name not in tool_names:
            return (
                {"error": f"tool {name!r} is not enabled in this session"},
                action_upgrade_decided,
            )
        try:
            arguments = (
                json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            )
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            return {"error": f"invalid tool arguments: {exc}"}, action_upgrade_decided
        normalized = {str(key): value for key, value in arguments.items()}
        read_only = read_only_by_name.get(name, False)
        if not read_only:
            if self.action_mode != "approval_required":
                return (
                    {"error": "action tools are disabled in read-only mode"},
                    action_upgrade_decided,
                )
            if self.approve is None or not await self.approve(name, normalized):
                return {"error": "operator declined this tool call"}, action_upgrade_decided
            normalized.setdefault("idempotencyKey", str(uuid4()))
        if name in ASSISTANT_CONVERSATION_TOOLS:
            normalized["conversationId"] = await self._ensure_conversation()
        try:
            result = await self.target.call_tool(name, normalized)
            required_tool = self._required_action_upgrade(result)
            original_message = normalized.get("message")
            can_upgrade = (
                required_tool is not None
                and read_only
                and read_only_by_name.get(required_tool) is False
                and isinstance(original_message, str)
                and bool(original_message.strip())
                and not action_upgrade_decided
            )
            if can_upgrade:
                action_upgrade_decided = True
                if required_tool is None or not isinstance(original_message, str):
                    return {"error": "invalid Action upgrade request"}, action_upgrade_decided
                upgrade_message = str(original_message)
                upgrade_args: dict[str, object] = {"message": upgrade_message}
                if self.approve is None or not await self.approve(required_tool, upgrade_args):
                    return {
                        "error": (
                            "operator declined the one-time Action upgrade. "
                            "No Action operation was created."
                        ),
                        "blockedQuery": result,
                    }, action_upgrade_decided
                result = await self.target.request(
                    upgrade_message,
                    conversation_id=await self._ensure_conversation(),
                    idempotency_key=str(uuid4()),
                )
                name = required_tool
            operation_id = result.get("operationId")
            if isinstance(operation_id, str) and name in {
                "tyr_assistant_query",
                "tyr_assistant_request",
                "tyr_workspace_bridge_send",
            }:
                result = await self.target.settle(result)
            return result, action_upgrade_decided
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}, action_upgrade_decided

    @staticmethod
    def _required_action_upgrade(result: dict[str, object]) -> str | None:
        error = result.get("error")
        if not isinstance(error, dict):
            return None
        if (
            error.get("actionModeRequired") is True
            and error.get("newOperationRequired") is True
            and error.get("requiredTool") == "tyr_assistant_request"
        ):
            return "tyr_assistant_request"
        return None


async def chat_once(prompt: str) -> str:
    """Compatibility placeholder for callers without configured adapters."""

    return f"Read-only chat scaffold received: {prompt}"
