"""Command flow for the interactive Tyr CLI.

The default chat mode exposes read-only Tyr MCP tools to the model. A structured
Read-only rejection can be upgraded once after terminal confirmation; other
Action tools require ``--allow-actions`` and still require confirmation.
"""

from __future__ import annotations

import argparse
from typing import Any

from ..mcp_client import TyrMCPError
from .session import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    CliAgentError,
    check_openrouter,
    connect_tyr,
    make_openrouter_client,
    run_turn,
    tool_definitions,
)
from .ui import TerminalUI


def run_check(model: str, base_url: str, ui: TerminalUI | None = None) -> int:
    """Check both connections and return a shell-friendly exit status."""
    ui = ui or TerminalUI()
    exit_status = 0
    try:
        with ui.status(f"Checking OpenRouter · {model}"):
            client = make_openrouter_client(base_url)
            reply = check_openrouter(client, model)
        ui.check_result("OpenRouter", f"Connected · {reply}", success=True)
    except Exception as exc:
        ui.check_result("OpenRouter", f"{type(exc).__name__}: {exc}", success=False)
        exit_status = 1

    try:
        with ui.status("Connecting to Tyr MCP"):
            _, tools, server_info = connect_tyr()
        server_name = server_info.get("serverInfo", {}).get("name") or server_info.get("server", "unknown")
        ui.check_result("Tyr MCP", f"{server_name} · {len(tools)} tools advertised", success=True)
    except (TyrMCPError, CliAgentError) as exc:
        ui.check_result("Tyr MCP", f"{type(exc).__name__}: {exc}", success=False)
        exit_status = 1
    return exit_status


def run_chat(
    model: str,
    base_url: str,
    allow_actions: bool,
    ui: TerminalUI | None = None,
) -> int:
    ui = ui or TerminalUI()
    with ui.status("Starting secure session…"):
        client = make_openrouter_client(base_url)
        tyr, advertised_tools, server_info = connect_tyr()
    tool_specs, tool_names, read_only_by_name = tool_definitions(advertised_tools, allow_actions)

    server_name = server_info.get("serverInfo", {}).get("name") or "Tyr MCP"
    ui.connection_summary(server_name, len(tool_specs), model, base_url, allow_actions)
    ui.info("Type /help for commands · Ctrl-D to exit")

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        try:
            command = ui.prompt().strip()
        except (EOFError, KeyboardInterrupt):
            ui.goodbye()
            return 0
        if not command:
            continue
        if command in {"/quit", "/exit"}:
            ui.goodbye()
            return 0
        if command == "/help":
            ui.help()
            continue
        if command == "/reset":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            ui.success("Conversation reset")
            continue
        if command == "/tools":
            ui.tools(tool_names)
            continue

        messages.append({"role": "user", "content": command})
        try:
            answer = run_turn(
                client,
                model,
                tyr,
                messages,
                tool_specs,
                tool_names,
                read_only_by_name,
                allow_actions,
                ui,
            )
        except (CliAgentError, TyrMCPError) as exc:
            ui.error(f"{type(exc).__name__}: {exc}")
            continue
        ui.assistant(answer)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("check", "chat"), default="chat")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenRouter model slug")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenRouter-compatible base URL")
    parser.add_argument(
        "--allow-actions",
        action="store_true",
        help="Expose non-read-only MCP tools; every call still needs confirmation",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ui = TerminalUI()
    ui.banner()
    try:
        if args.mode == "check":
            return run_check(args.model, args.base_url, ui)
        return run_chat(args.model, args.base_url, args.allow_actions, ui)
    except (CliAgentError, TyrMCPError) as exc:
        ui.error(f"{type(exc).__name__}: {exc}")
        return 1
