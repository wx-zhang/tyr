"""Terminal presentation for the interactive Tyr CLI."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Any, Iterator

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console, Group
from rich.json import JSON
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text
from rich.theme import Theme


COMMANDS = ("/help", "/tools", "/reset", "/quit", "/exit")

THEME = Theme({
    "accent": "bold cyan",
    "muted": "dim",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "tool": "magenta",
})

PROMPT_STYLE = Style.from_dict({
    "prompt": "bold ansicyan",
    "chevron": "ansibrightblack",
})


class TerminalUI:
    """Render CLI state consistently and provide an enhanced input prompt."""

    def __init__(self) -> None:
        self.console = Console(theme=THEME)
        self.error_console = Console(theme=THEME, stderr=True)
        self._session: PromptSession[str] | None = None

    def banner(self) -> None:
        title = Text("TYR", style="bold white")
        title.append("  CLI Agent", style="accent")
        subtitle = Text("Secure, human-approved access to Tyr MCP", style="muted")
        self.console.print(Panel(Group(title, subtitle), border_style="cyan", padding=(0, 2)))

    def connection_summary(
        self,
        server_name: str,
        tool_count: int,
        model: str,
        base_url: str,
        allow_actions: bool,
    ) -> None:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="muted", justify="right")
        table.add_column()
        table.add_row("Server", f"[success]{server_name}[/success]")
        table.add_row("Tools", f"{tool_count} enabled")
        table.add_row("Model", model)
        table.add_row("Endpoint", f"[muted]{base_url}[/muted]")
        mode = "[warning]Actions enabled · confirmation required[/warning]" if allow_actions else "[success]Read-only[/success]"
        table.add_row("Mode", mode)
        self.console.print(Panel(table, title="Session", border_style="bright_black"))

    def help(self) -> None:
        table = Table(box=None, show_header=False, pad_edge=False)
        table.add_column(style="accent", no_wrap=True)
        table.add_column(style="muted")
        table.add_row("/help", "Show available commands")
        table.add_row("/tools", "List enabled Tyr MCP tools")
        table.add_row("/reset", "Start a fresh conversation")
        table.add_row("/quit", "Leave the chat")
        self.console.print(Panel(table, title="Commands", border_style="bright_black"))

    def tools(self, names: set[str]) -> None:
        table = Table("Tool", box=None, header_style="muted", pad_edge=False)
        for name in sorted(names):
            table.add_row(Text(name, style="tool"))
        self.console.print(Panel(table, title=f"Enabled tools · {len(names)}", border_style="bright_black"))

    def prompt(self) -> str:
        if not sys.stdin.isatty():
            return self.console.input("[accent]You[/accent] [muted]›[/muted] ")
        if self._session is None:
            self._session = PromptSession(
                history=InMemoryHistory(),
                auto_suggest=AutoSuggestFromHistory(),
                completer=WordCompleter(COMMANDS, sentence=True),
                complete_while_typing=False,
                style=PROMPT_STYLE,
            )
        return self._session.prompt([("class:prompt", "You "), ("class:chevron", "› ")])

    @contextmanager
    def status(self, message: str) -> Iterator[None]:
        if self.console.is_terminal:
            with self.console.status(message, spinner="dots", spinner_style="accent"):
                yield
        else:
            self.info(message)
            yield

    def assistant(self, content: str) -> None:
        self.console.print(Panel(Markdown(content), title="Tyr Agent", title_align="left", border_style="cyan"))

    def tool_call(self, name: str) -> None:
        self.console.print(f"[tool]◆ MCP[/tool] [bold]{name}[/bold]")

    def confirm_action(self, name: str, arguments: dict[str, Any]) -> bool:
        body = Group(
            Text(name, style="bold warning"),
            Text("This tool can act outside the local process.", style="muted"),
            JSON.from_data(arguments),
        )
        self.console.print(Panel(body, title="Action approval", border_style="yellow"))
        try:
            return Confirm.ask("Run this tool?", console=self.console, default=False)
        except (EOFError, KeyboardInterrupt):
            return False

    def confirm_action_upgrade(self, name: str, arguments: dict[str, Any]) -> bool:
        body = Group(
            Text("The Read-only request was not executed.", style="bold warning"),
            Text(
                "Create one new Action operation with the same request? The blocked query operation ID will not be reused.",
                style="muted",
            ),
            Text(name, style="bold warning"),
            JSON.from_data(arguments),
        )
        self.console.print(Panel(body, title="One-time Action approval", border_style="yellow"))
        try:
            return Confirm.ask("Create this one Action operation?", console=self.console, default=False)
        except (EOFError, KeyboardInterrupt):
            return False

    def check_result(self, service: str, detail: str, success: bool) -> None:
        symbol = "✓" if success else "✗"
        style = "success" if success else "error"
        console = self.console if success else self.error_console
        console.print(f"[{style}]{symbol} {service}[/{style}]  {detail}")

    def info(self, message: str) -> None:
        self.console.print(f"[muted]{message}[/muted]")

    def success(self, message: str) -> None:
        self.console.print(f"[success]✓[/success] {message}")

    def error(self, message: str) -> None:
        self.error_console.print(f"[error]Error:[/error] {message}")

    def goodbye(self) -> None:
        self.console.print("[muted]Session closed. Goodbye.[/muted]")
