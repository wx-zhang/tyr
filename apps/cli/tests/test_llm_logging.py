from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from gamr_adapters.models import ModelStreamEvent
from gamr_cli.llm_logging import LlmLogMode, ThinkingStreamRenderer, model_stream_callback
from rich.console import Console


def _event(
    request_id: str,
    kind: str,
    delta: str = "",
    *,
    model: str = "test-model",
    method: str = "complete",
) -> ModelStreamEvent:
    return ModelStreamEvent(request_id, model, method, kind, delta)  # type: ignore[arg-type]


def test_default_mode_does_not_create_a_stream_callback() -> None:
    console = Console(file=StringIO(), force_terminal=False)

    assert model_stream_callback(console, LlmLogMode.DEFAULT) is None


def test_thinking_renderer_buffers_interleaved_literal_lines() -> None:
    output = StringIO()
    renderer = ThinkingStreamRenderer(Console(file=output, force_terminal=False))

    renderer(_event("a", "started", model="model-a", method="complete"))
    renderer(_event("b", "started", model="model-b", method="chat"))
    renderer(_event("a", "thinking", "first "))
    renderer(_event("b", "thinking", "other\n"))
    renderer(_event("a", "thinking", "line\npartial"))
    renderer(_event("a", "thinking", " line"))
    renderer(_event("a", "completed"))
    renderer(_event("b", "completed"))

    assert "other" in output.getvalue()
    assert "first line" in output.getvalue()
    assert "partial line" in output.getvalue()


def test_terminal_events_flush_nonblank_partial_lines_and_remove_state() -> None:
    output = StringIO()
    renderer = ThinkingStreamRenderer(Console(file=output, force_terminal=False))

    renderer(_event("a", "started", model="model-a", method="complete"))
    renderer(_event("a", "thinking", "[red]literal"))
    renderer(_event("a", "failed"))
    renderer(_event("a", "thinking", "stale"))
    renderer(_event("b", "started", model="model-b", method="complete"))
    renderer(_event("b", "thinking", "\n\n"))
    renderer(_event("b", "completed"))

    assert "[red]literal" in output.getvalue()
    assert "stale" not in output.getvalue()


def test_renderer_uses_plain_text_for_markup_like_reasoning() -> None:
    output = StringIO()
    renderer = ThinkingStreamRenderer(Console(file=output, force_terminal=False))

    renderer(_event("a", "started", model="model-a", method="complete"))
    renderer(_event("a", "thinking", "[red]do not style[/red]\n"))
    renderer(_event("a", "completed"))

    assert "[red]do not style[/red]" in output.getvalue()


def test_thinking_completion_reports_elapsed_time() -> None:
    output = StringIO()
    renderer = ThinkingStreamRenderer(Console(file=output, width=120))
    with patch("gamr_cli.llm_logging.monotonic", side_effect=[10, 75]):
        renderer(_event("a", "started"))
        renderer(_event("a", "thinking", "reasoning"))
        assert "Thinking complete" not in output.getvalue()
        renderer(_event("a", "completed"))
    assert "Thinking complete · 0:01:05" in output.getvalue()
