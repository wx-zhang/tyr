from __future__ import annotations

import json
from typing import Any

EXECUTE_PYTHON_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_python",
        "description": (
            "Execute Python 3.14 code using the standard library in an isolated environment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "UTF-8 Python 3.14 source code to execute.",
                },
                "rationale": {
                    "type": "string",
                    "description": "Concise explanation for why this route is needed.",
                }
            },
            "required": ["source", "rationale"],
            "additionalProperties": False,
        },
    },
}

MAX_SOURCE_LENGTH = 64 * 1024
MAX_RATIONALE_LENGTH = 600


def parse_tool_call(
    tool_call: dict[str, Any],
) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Returns (call_id, source_code, rationale, error_code).
    error_code can be 'invalid_agent_response' or 'unknown_tool_or_input'.
    """
    call_id = tool_call.get("id")
    func = tool_call.get("function")
    if not isinstance(call_id, str) or not isinstance(func, dict):
        return None, None, None, "invalid_agent_response"

    name = func.get("name")
    if name != "execute_python":
        return call_id, None, None, "unknown_tool_or_input"

    raw_args = func.get("arguments")
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            return call_id, None, None, "invalid_agent_response"
    elif isinstance(raw_args, dict):
        args = raw_args
    else:
        return call_id, None, None, "invalid_agent_response"

    if not isinstance(args, dict):
        return call_id, None, None, "invalid_agent_response"

    source = args.get("source")
    if not isinstance(source, str):
        return call_id, None, None, "invalid_agent_response"

    encoded = source.encode("utf-8")
    if len(encoded) > MAX_SOURCE_LENGTH:
        return call_id, None, None, "invalid_agent_response"

    rationale = args.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        return call_id, None, None, "invalid_agent_response"
    if len(rationale) > MAX_RATIONALE_LENGTH:
        return call_id, None, None, "invalid_agent_response"

    return call_id, source, rationale.strip(), None
