from pathlib import Path

import pytest
from gamr_cli.judge_evaluation_debug import (
    DebugSandbox,
    RichDebugOutput,
    format_llm_debug,
    new_debug_log_path,
)
from gamr_engine.ports.sandbox import ExecutionResult, SandboxEntry, SandboxId
from rich.console import Console, RenderableType
from rich.panel import Panel


def _render_text(*renderables: RenderableType) -> str:
    console = Console(record=True, width=120, color_system=None)
    for renderable in renderables:
        console.print(renderable)
    return console.export_text()


def test_formats_chat_request_as_readable_sections_and_parses_message_json() -> None:
    rendered = format_llm_debug(
        "request",
        "case-a",
        2,
        "chat",
        {
            "messages": [
                {"role": "system", "content": "Choose a route."},
                {"role": "user", "content": '{"task":"inspect","items":[1,2]}'},
            ],
            "tools": [{"type": "function", "function": {"name": "execute_python"}}],
            "maxTokens": 2048,
        },
    )

    assert isinstance(rendered, Panel)
    text = _render_text(rendered)
    assert "case-a · LLM request 2 · chat" in text
    assert "1 · system" in text and "Choose a route." in text
    assert '2 · user' in text and '"task": "inspect"' in text
    assert "Tools" in text and "execute_python" in text
    assert "Max tokens" in text and "2048" in text
    assert '\\"task\\"' not in text


def test_formats_structured_response_content_and_metadata() -> None:
    rendered = format_llm_debug(
        "response",
        "case-a",
        2,
        "complete_structured",
        {
            "content": '{"status":"confirmed","matches":[]}',
            "model": "judge-model",
            "finishReason": "stop",
            "usage": {"total_tokens": 42},
        },
    )

    assert isinstance(rendered, Panel)
    text = _render_text(rendered)
    assert "case-a · LLM response 2 · complete_structured" in text
    assert "Content" in text and '"status": "confirmed"' in text
    assert "Model" in text and "judge-model" in text
    assert "Usage" in text and '"total_tokens": 42' in text
    assert '\\"status\\"' not in text


class _Sandbox:
    isolation = "contained"

    async def start(self, entries: list[SandboxEntry]) -> SandboxId:
        assert entries[0].content == b"mounted content"
        return SandboxId("sandbox-1")

    async def execute(self, sandbox_id: SandboxId, source: str) -> ExecutionResult:
        assert sandbox_id == "sandbox-1"
        assert source == 'print("hello")'
        return ExecutionResult(0, "hello\n", "", 0.125)

    async def collect_output(
        self, sandbox_id: SandboxId, output_dir: str
    ) -> list[SandboxEntry]:
        assert sandbox_id == "sandbox-1"
        assert output_dir == "output/attempt-001"
        return [SandboxEntry("result.txt", b"decoded")]

    async def close(self, sandbox_id: SandboxId) -> None:
        assert sandbox_id == "sandbox-1"


@pytest.mark.asyncio
async def test_debug_sandbox_prints_source_results_and_file_metadata() -> None:
    debug: list[RenderableType] = []
    sandbox = DebugSandbox(_Sandbox(), debug.append)  # type: ignore[arg-type]

    sandbox_id = await sandbox.start([SandboxEntry("upload/file.txt", b"mounted content")])
    result = await sandbox.execute(sandbox_id, 'print("hello")')
    outputs = await sandbox.collect_output(sandbox_id, "output/attempt-001")
    await sandbox.close(sandbox_id)

    assert result.stdout == "hello\n"
    assert outputs[0].content == b"decoded"
    rendered = _render_text(*debug)
    assert "Sandbox start inputs" in rendered
    assert '"path": "upload/file.txt"' in rendered
    assert "mounted content" not in rendered
    assert "Sandbox execute input" in rendered and 'print("hello")' in rendered
    assert "Stdout" in rendered and "hello" in rendered
    assert '"path": "result.txt"' in rendered
    assert "Sandbox closed" in rendered


def test_rich_debug_output_prints_and_persists_plain_text_verbatim(tmp_path: Path) -> None:
    terminal = Console(record=True, width=100, color_system=None)
    log_path = tmp_path / "evaluation.log"
    output = RichDebugOutput(terminal, log_path, secrets=("sensitive-value",))

    output(Panel("sensitive-value", title="Debug record"))

    assert "sensitive-value" in terminal.export_text()
    persisted = log_path.read_text()
    assert "Debug record" in persisted
    assert "sensitive-value" in persisted
    assert "[REDACTED]" not in persisted


def test_debug_log_path_uses_timestamp_and_short_uuid(tmp_path: Path) -> None:
    path = new_debug_log_path(tmp_path)

    assert path.parent == tmp_path / "evaluations" / "judges"
    timestamp, short_uuid = path.stem.split("-")
    assert timestamp.endswith("Z") and len(timestamp) == 16
    assert len(short_uuid) == 8
    assert all(character in "0123456789abcdef" for character in short_uuid)
