"""OpenRouter and Tyr MCP orchestration for the interactive CLI."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

from .ui import TerminalUI

load_dotenv()

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - exercised by the CLI itself
    OpenAI = None  # type: ignore[assignment,misc]
    OPENAI_IMPORT_ERROR = exc

try:
    from ..mcp_client import TyrMCPClient, TyrMCPError
except ImportError as exc:  # pragma: no cover - exercised by the CLI itself
    TyrMCPClient = None  # type: ignore[assignment,misc]
    TyrMCPError = RuntimeError  # type: ignore[assignment,misc]
    MCP_IMPORT_ERROR = exc


DEFAULT_MODEL = os.environ.get("TYR_AGENT_MODEL", os.environ.get("TYR_LOOP_MODEL", "openai/gpt-4o-mini"))
DEFAULT_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MAX_TOOL_ROUNDS = int(os.environ.get("TYR_AGENT_MAX_TOOL_ROUNDS", "8"))

LEGACY_READ_ONLY_TOOLS = {
    "tyr_assistant_query",
    "tyr_operation_status",
    "tyr_workspace_bridge_list",
    "tyr_workspace_bridge_status",
    "tyr_workspace_bridge_history",
}

SYSTEM_PROMPT = """You are a small command-line assistant connected to Tyr through MCP.

Help the operator investigate Tyr and carry out requests they explicitly ask
for. Use the available Tyr tools when a question is about Tyr, its agents,
operations, workspaces, or bridges. Do not claim that a tool succeeded unless
its result says so. Keep responses concise and mention useful next steps when
Tyr is waiting for input or approval. When a Tyr tool returns an operationId
for work that is not finished, use tyr_operation_status before reporting the
final outcome. A Read-only rejection does not mean the action ran. The CLI may
ask the operator to approve one new Action operation; rely only on the result
of that new operation.
"""


class CliAgentError(RuntimeError):
    """A configuration or provider error that should be shown cleanly."""


def require_openrouter_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise CliAgentError("Missing OPENROUTER_API_KEY. Set it before running this command.")
    return key


def require_openai_package() -> None:
    if OpenAI is None:
        raise CliAgentError(f"Missing dependency ({OPENAI_IMPORT_ERROR}). Install it with:\n  uv sync")


def require_mcp_package() -> None:
    if TyrMCPClient is None:
        raise CliAgentError(f"Missing dependency ({MCP_IMPORT_ERROR}). Install it with:\n  uv sync")


def make_openrouter_client(base_url: str = DEFAULT_BASE_URL) -> Any:
    require_openai_package()
    return OpenAI(
        base_url=base_url,
        api_key=require_openrouter_key(),
        default_headers={"X-Title": "Tyr CLI Agent"},
    )


def connect_tyr() -> tuple[TyrMCPClient, list[dict[str, Any]], dict[str, Any]]:
    """Initialize Tyr and return its advertised MCP tools."""
    require_mcp_package()
    try:
        tyr = TyrMCPClient()
        server_info = tyr.initialize()
        tools = tyr.list_tools()
    except TyrMCPError:
        raise
    except Exception as exc:
        raise CliAgentError(f"Unexpected error connecting to Tyr: {type(exc).__name__}: {exc}") from exc
    return tyr, tools, server_info


def check_openrouter(client: Any, model: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with exactly OPENROUTER_OK."}],
        max_tokens=1024,
        temperature=0,
    )
    choices = getattr(response, "choices", None) or []
    text = ((choices[0].message.content if choices else None) or "").strip()
    if not text:
        raise CliAgentError("OpenRouter returned an empty response.")
    return text


def tool_definitions(
    advertised_tools: list[dict[str, Any]], allow_actions: bool
) -> tuple[list[dict[str, Any]], set[str], dict[str, bool]]:
    """Convert MCP's tools/list shape to OpenAI chat-completions tool shape."""
    definitions: list[dict[str, Any]] = []
    names: set[str] = set()
    read_only_by_name: dict[str, bool] = {}
    for tool in advertised_tools:
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            continue
        read_only = tool_is_read_only(tool)
        read_only_by_name[name] = read_only
        if not allow_actions and not read_only:
            continue
        schema = tool.get("inputSchema") or {"type": "object", "properties": {}}
        definitions.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool.get("description") or f"Call Tyr MCP tool {name}.",
                "parameters": schema,
            },
        })
        names.add(name)
    return definitions, names, read_only_by_name


def tool_is_read_only(tool: dict[str, Any]) -> bool:
    """Prefer MCP annotations and fail closed for unknown legacy tools."""
    annotations = tool.get("annotations")
    if isinstance(annotations, dict):
        read_only_hint = annotations.get("readOnlyHint")
        if isinstance(read_only_hint, bool):
            return read_only_hint
    name = tool.get("name")
    return isinstance(name, str) and name in LEGACY_READ_ONLY_TOOLS


def json_for_message(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return json.dumps({"value": str(value)}, ensure_ascii=False)


def message_as_dict(message: Any) -> dict[str, Any]:
    """Make an SDK message safe to append to the next chat request."""
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True)
    if hasattr(message, "dict"):
        return message.dict(exclude_none=True)
    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", ""),
    }


def confirm_tool_call(name: str, arguments: dict[str, Any], ui: TerminalUI | None = None) -> bool:
    if ui is not None:
        return ui.confirm_action(name, arguments)
    print(f"\n!! Action requested: {name}")
    print(json_for_message(arguments))
    try:
        answer = input("Run this tool? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in {"y", "yes"}


def confirm_action_upgrade(message: str, ui: TerminalUI | None = None) -> bool:
    arguments = {"message": message}
    if ui is not None:
        return ui.confirm_action_upgrade("tyr_assistant_request", arguments)
    print("\n!! Read-only request was not executed.")
    print("Create one new tyr_assistant_request Action operation with the same request?")
    print(json_for_message(arguments))
    try:
        answer = input("Run this one Action? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in {"y", "yes"}


def required_action_upgrade(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
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


def call_model(
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> Any:
    request: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": 1024,
    }
    if tools:
        request["tools"] = tools
        request["tool_choice"] = "auto"
    try:
        return client.chat.completions.create(**request)
    except Exception as exc:
        raise CliAgentError(f"OpenRouter request failed: {type(exc).__name__}: {exc}") from exc


def run_turn(
    client: Any,
    model: str,
    tyr: TyrMCPClient,
    messages: list[dict[str, Any]],
    tool_specs: list[dict[str, Any]],
    tool_names: set[str],
    read_only_by_name: dict[str, bool],
    allow_actions: bool,
    ui: TerminalUI | None = None,
) -> str:
    """Run one user turn, servicing model-requested MCP calls until a reply."""
    action_upgrade_decided = False
    for _ in range(MAX_TOOL_ROUNDS):
        if ui is None:
            response = call_model(client, model, messages, tool_specs)
        else:
            with ui.status("Thinking…"):
                response = call_model(client, model, messages, tool_specs)
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise CliAgentError("OpenRouter returned no choices.")

        assistant_message = choices[0].message
        messages.append(message_as_dict(assistant_message))
        tool_calls = getattr(assistant_message, "tool_calls", None) or []
        if not tool_calls:
            answer = (getattr(assistant_message, "content", None) or "").strip()
            if not answer:
                raise CliAgentError("OpenRouter returned an empty assistant message.")
            return answer

        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            name = getattr(function, "name", "")
            raw_arguments = getattr(function, "arguments", "{}") or "{}"
            try:
                arguments = json.loads(raw_arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                result: Any = {"error": f"Invalid tool arguments: {exc}"}
            else:
                read_only = read_only_by_name.get(name)
                if name not in tool_names:
                    result = {"error": f"Tool {name!r} is not enabled in this session."}
                elif read_only is not True and not allow_actions:
                    result = {"error": "Action tools are disabled. Restart with --allow-actions if needed."}
                elif read_only is not True and not confirm_tool_call(name, arguments, ui):
                    result = {"error": "Operator declined this tool call."}
                else:
                    if ui is None:
                        print(f"[MCP] {name}")
                    else:
                        ui.tool_call(name)
                    try:
                        result = tyr.call_tool(name, arguments)
                    except TyrMCPError as exc:
                        result = {"error": str(exc)}

                    required_tool = required_action_upgrade(result)
                    original_message = arguments.get("message")
                    can_upgrade = (
                        required_tool is not None
                        and read_only is True
                        and read_only_by_name.get(required_tool) is False
                        and isinstance(original_message, str)
                        and bool(original_message.strip())
                    )
                    if can_upgrade and not action_upgrade_decided:
                        action_upgrade_decided = True
                        if confirm_action_upgrade(original_message, ui):
                            if ui is None:
                                print(f"[MCP] {required_tool}")
                            else:
                                ui.tool_call(required_tool)
                            try:
                                # request() creates a new key and omits the query operationId.
                                result = tyr.request(original_message)
                            except TyrMCPError as exc:
                                result = {"error": str(exc)}
                        else:
                            result = {
                                "error": "Operator declined the one-time Action upgrade. No Action operation was created.",
                                "blockedQuery": result,
                            }

            messages.append({
                "role": "tool",
                "tool_call_id": getattr(tool_call, "id", None),
                "content": json_for_message(result),
            })

    raise CliAgentError(f"Reached the {MAX_TOOL_ROUNDS}-round MCP tool-call limit for this turn.")
