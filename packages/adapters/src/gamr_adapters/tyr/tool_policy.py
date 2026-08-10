from __future__ import annotations

READ_ONLY_TOOLS = frozenset(
    {
        "tyr_assistant_query",
        "tyr_operation_status",
        "tyr_workspace_bridge_list",
        "tyr_workspace_bridge_history",
    }
)
ACTION_TOOLS = frozenset(
    {
        "tyr_assistant_request",
        "tyr_approval_resolve",
        "tyr_workspace_bridge_send",
    }
)


def is_action_tool(name: str) -> bool:
    return name not in READ_ONLY_TOOLS


def tools_for_mode(tools: list[dict[str, object]], action_mode: str) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for tool in tools:
        name = tool.get("name")
        if isinstance(name, str) and (
            action_mode == "approval_required" or not is_action_tool(name)
        ):
            selected.append(tool)
    return selected


def require_approval(action_mode: str, approved: bool) -> None:
    if action_mode == "approval_required" and not approved:
        raise PermissionError("explicit human approval is required for this action")
