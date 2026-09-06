from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from gamr_adapters.models import ModelStreamCallback, ModelStreamEvent
from rich.console import Console
from rich.text import Text


class LlmLogMode(StrEnum):
    DEFAULT = "default"
    THINKING = "thinking"


@dataclass
class _CallState:
    number: int
    model: str
    method: str
    buffer: str = ""


class ThinkingStreamRenderer:
    def __init__(self, console: Console) -> None:
        self.console = console
        self._calls: dict[str, _CallState] = {}
        self._next_call_number = 1

    def __call__(self, event: ModelStreamEvent) -> None:
        if event.kind == "started":
            self._calls[event.request_id] = _CallState(
                self._next_call_number, event.model, event.method
            )
            self._next_call_number += 1
            return

        state = self._calls.get(event.request_id)
        if state is None:
            return
        if event.kind == "thinking":
            state.buffer += event.delta
            self._render_complete_lines(state)
            return
        if event.kind in {"completed", "failed"}:
            self._render_line(state, state.buffer)
            del self._calls[event.request_id]

    def _render_complete_lines(self, state: _CallState) -> None:
        lines = state.buffer.split("\n")
        state.buffer = lines.pop()
        for line in lines:
            self._render_line(state, line.rstrip("\r"))

    def _render_line(self, state: _CallState, line: str) -> None:
        if not line.strip():
            return
        label = f"LLM #{state.number} · {state.method} · {state.model} · "
        self.console.print(Text(label + line, style="dim"))


def model_stream_callback(console: Console, mode: LlmLogMode) -> ModelStreamCallback | None:
    if mode is LlmLogMode.DEFAULT:
        return None
    return ThinkingStreamRenderer(console)
