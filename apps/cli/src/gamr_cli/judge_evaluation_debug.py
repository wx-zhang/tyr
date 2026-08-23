from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from gamr_adapters.artifacts.redaction import redact_payload
from gamr_engine.ports.sandbox import (
    ExecutionResult,
    Sandbox,
    SandboxEntry,
    SandboxId,
    SandboxIsolation,
    SandboxSource,
)
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

type DebugSink = Callable[[RenderableType], None]


def new_debug_log_path(artifact_root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return artifact_root / "evaluations" / "judges" / f"{timestamp}-{uuid4().hex[:8]}.log"


class RichDebugOutput:
    def __init__(
        self,
        console: Console,
        log_path: Path,
        *,
        secrets: Iterable[str] = (),
    ) -> None:
        self.console = console
        self.log_path = log_path
        self.secrets = tuple(secrets)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch(exist_ok=False)

    def __call__(self, renderable: RenderableType) -> None:
        self.console.print(renderable)
        buffer = StringIO()
        log_console = Console(file=buffer, width=160, color_system=None, highlight=False)
        log_console.print(renderable)
        persisted = redact_payload(buffer.getvalue(), self.secrets)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(str(persisted))


def _render_value(value: Any, *, lexer: str = "json") -> RenderableType:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return Text("(empty)", style="dim italic")
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            if lexer != "json":
                return Syntax(value, lexer, theme="ansi_dark", word_wrap=True)
            return Text(value)
    else:
        parsed = value
    rendered = json.dumps(parsed, indent=2, ensure_ascii=False, default=str)
    return Syntax(rendered, "json", theme="ansi_dark", word_wrap=True)


def _section(title: str, value: Any, *, border_style: str = "dim") -> Panel:
    return Panel(
        _render_value(value),
        title=title,
        title_align="left",
        border_style=border_style,
        padding=(0, 1),
    )


def _format_messages(messages: Any) -> Panel:
    if not isinstance(messages, list):
        return _section("Messages", messages)
    rendered: list[RenderableType] = []
    role_styles = {"system": "yellow", "user": "cyan", "assistant": "green", "tool": "magenta"}
    for index, message in enumerate(messages, 1):
        if not isinstance(message, dict):
            rendered.append(_section(str(index), message))
            continue
        role = str(message.get("role", "unknown"))
        content: list[RenderableType] = [_render_value(message.get("content", ""))]
        extras = {key: value for key, value in message.items() if key not in {"role", "content"}}
        if extras:
            content.append(_section("Message metadata", extras))
        rendered.append(
            Panel(
                Group(*content),
                title=f"{index} · {role}",
                title_align="left",
                border_style=role_styles.get(role, "dim"),
            )
        )
    return Panel(Group(*rendered), title="Messages", title_align="left", border_style="blue")


def _format_tools(tools: Any) -> Panel:
    if not isinstance(tools, list):
        return _section("Tools", tools)
    rendered: list[RenderableType] = []
    for index, tool in enumerate(tools, 1):
        function = tool.get("function", {}) if isinstance(tool, dict) else {}
        name = function.get("name", "unknown") if isinstance(function, dict) else "unknown"
        rendered.append(_section(f"{index} · {name}", tool, border_style="magenta"))
    return Panel(Group(*rendered), title="Tools", title_align="left", border_style="magenta")


def format_llm_debug(
    direction: str,
    case_id: str,
    call_number: int,
    method: str,
    payload: Any,
) -> Panel:
    labels = {
        "system": "System",
        "prompt": "Prompt",
        "images": "Images",
        "jsonSchema": "JSON schema",
        "schema": "JSON schema",
        "maxTokens": "Max tokens",
        "content": "Content",
        "message": "Message",
        "model": "Model",
        "finishReason": "Finish reason",
        "refusal": "Refusal",
        "usage": "Usage",
        "error": "Error",
    }
    sections: list[RenderableType] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "messages":
                sections.append(_format_messages(value))
            elif key == "tools":
                sections.append(_format_tools(value))
            else:
                label = labels.get(str(key), str(key))
                sections.append(_section(label, value))
    else:
        sections.append(_render_value(payload))
    return Panel(
        Group(*sections),
        title=f"{case_id} · LLM {direction} {call_number} · {method}",
        title_align="left",
        border_style="cyan" if direction == "request" else "green",
        padding=(1, 1),
    )


def _entry_metadata(entries: Sequence[SandboxEntry]) -> list[dict[str, Any]]:
    return [
        {
            "path": entry.path,
            "size": len(entry.content),
            "sha256": hashlib.sha256(entry.content).hexdigest(),
        }
        for entry in entries
    ]


def _sandbox_panel(title: str, value: Any, *, lexer: str = "json") -> Panel:
    return Panel(
        _render_value(value, lexer=lexer),
        title=title,
        title_align="left",
        border_style="magenta",
        padding=(0, 1),
    )


class DebugSandbox:
    def __init__(self, wrapped: Sandbox, debug: DebugSink) -> None:
        self.wrapped = wrapped
        self.debug = debug

    @property
    def isolation(self) -> SandboxIsolation:
        return self.wrapped.isolation

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        self.debug(_sandbox_panel("Sandbox start inputs", _entry_metadata(entries)))
        sandbox_id = await self.wrapped.start(entries)
        self.debug(_sandbox_panel("Sandbox started", str(sandbox_id)))
        return sandbox_id

    async def execute(self, sandbox_id: SandboxId, source: SandboxSource) -> ExecutionResult:
        rendered_source = (
            source.decode("utf-8", errors="replace") if isinstance(source, bytes) else source
        )
        self.debug(_sandbox_panel("Sandbox execute input", rendered_source, lexer="python"))
        result = await self.wrapped.execute(sandbox_id, source)
        metadata = {
            "exitCode": result.exit_code,
            "elapsedSeconds": result.elapsed_seconds,
            "timedOut": result.timed_out,
            "outputLimited": result.output_limited,
        }
        self.debug(
            Panel(
                Group(
                    _section("Result", metadata),
                    _section("Stdout", result.stdout, border_style="green"),
                    _section("Stderr", result.stderr, border_style="red"),
                ),
                title="Sandbox execute output",
                title_align="left",
                border_style="magenta",
            )
        )
        return result

    async def collect_output(
        self, sandbox_id: SandboxId, output_dir: str
    ) -> Sequence[SandboxEntry]:
        self.debug(_sandbox_panel("Sandbox collect output", output_dir))
        entries = await self.wrapped.collect_output(sandbox_id, output_dir)
        self.debug(_sandbox_panel("Sandbox output files", _entry_metadata(entries)))
        return entries

    async def close(self, sandbox_id: SandboxId) -> None:
        try:
            await self.wrapped.close(sandbox_id)
        finally:
            self.debug(_sandbox_panel("Sandbox closed", str(sandbox_id)))
