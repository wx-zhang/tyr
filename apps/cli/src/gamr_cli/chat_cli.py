from __future__ import annotations

import json

import typer
from gamr_adapters.config import Settings
from rich.console import Console
from rich.markdown import Markdown

from .composition import build_chat_session


async def run_chat_loop(
    console: Console,
    initial_prompt: str,
    *,
    action_mode: str,
    model: str | None,
    base_url: str | None,
) -> None:
    async def approve(name: str, arguments: dict[str, object]) -> bool:
        console.print(f"[yellow]Action requested:[/yellow] {name}")
        console.print_json(json.dumps(arguments, ensure_ascii=False, default=str))
        return typer.confirm("Run this tool?", default=False)

    session, target = build_chat_session(
        Settings(),
        action_mode=action_mode,
        approve=approve,
        model_name=model,
        base_url=base_url,
    )
    messages: list[dict[str, object]] = [
        {
            "role": "system",
            "content": (
                "You are a concise command-line assistant connected to Tyr through MCP. "
                "Use available tools for Tyr questions. Never claim a tool succeeded unless "
                "its result says so. If an operation is waiting for input, ask the operator "
                "for the next message."
            ),
        }
    ]
    try:
        tools = await session.connect()
        console.print(f"[green]Connected to Tyr[/green] · {len(tools)} tools · mode={action_mode}")
        next_prompt = initial_prompt
        while True:
            if not next_prompt:
                try:
                    next_prompt = typer.prompt("Message")
                except EOFError, KeyboardInterrupt:
                    return
            command = next_prompt.strip()
            next_prompt = ""
            if not command:
                continue
            if command in {"/quit", "/exit"}:
                return
            if command == "/help":
                console.print("/help  /tools  /reset  /quit")
                continue
            if command == "/tools":
                console.print("\n".join(tools))
                continue
            if command == "/reset":
                messages = messages[:1]
                console.print("[green]Conversation reset[/green]")
                continue
            answer = await session.run_turn(messages, command)
            console.print(Markdown(answer) if isinstance(answer, str) else answer)
            if initial_prompt:
                return
    finally:
        await target.aclose()
