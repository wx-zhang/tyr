from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from gamr_engine.ports import ExecutionResult, SandboxEntry, SandboxUnavailableError

sys.path.insert(0, str(Path(__file__).parents[1]))


class FakeSandbox:
    def __init__(self, result: ExecutionResult | None = None) -> None:
        self.result = result or ExecutionResult(0, "ok", "", 0.01)
        self.entries: tuple[SandboxEntry, ...] = ()
        self.source: str | bytes | None = None
        self.closed = 0

    async def start(self, entries: tuple[SandboxEntry, ...] = ()) -> str:
        self.entries = tuple(entries)
        return "opaque-id"

    async def execute(self, sandbox_id: str, source: str | bytes) -> ExecutionResult:
        assert sandbox_id == "opaque-id"
        self.source = source
        return self.result

    async def close(self, sandbox_id: str) -> None:
        assert sandbox_id == "opaque-id"
        self.closed += 1


def test_runner_supports_repeated_attachments_and_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from scripts import sandbox_run

    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    sandbox = FakeSandbox()
    monkeypatch.setattr(sandbox_run, "create_sandbox", lambda settings: sandbox)

    assert (
        sandbox_run.main(["--attach", str(first), "--attach", str(second), "--code", "print(1)"])
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["sandboxId"] == "opaque-id"
    assert payload["result"]["exitCode"] == 0
    assert [entry.path for entry in sandbox.entries] == ["first.txt", "second.txt"]
    assert sandbox.source == "print(1)"
    assert sandbox.closed == 1


def test_runner_reads_utf8_source_file_and_returns_python_failure_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from scripts import sandbox_run

    source = tmp_path / "source.py"
    source.write_text("raise SystemExit(3)", encoding="utf-8")
    sandbox = FakeSandbox(ExecutionResult(3, "", "failed", 0.01))
    monkeypatch.setattr(sandbox_run, "create_sandbox", lambda settings: sandbox)

    assert sandbox_run.main(["--source-file", str(source)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"]["exitCode"] == 3
    assert sandbox.source == b"raise SystemExit(3)"
    assert sandbox.closed == 1


def test_runner_rejects_both_source_options_without_starting_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts import sandbox_run

    sandbox = FakeSandbox()
    monkeypatch.setattr(sandbox_run, "create_sandbox", lambda settings: sandbox)
    source = tmp_path / "source.py"
    source.write_text("print(1)", encoding="utf-8")

    with pytest.raises(SystemExit):
        sandbox_run.main(["--code", "print(1)", "--source-file", str(source)])
    assert sandbox.closed == 0


def test_runner_closes_after_start_or_execution_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import sandbox_run

    class FailingSandbox(FakeSandbox):
        async def execute(self, sandbox_id: str, source: str | bytes) -> ExecutionResult:
            raise SandboxUnavailableError("execution unavailable")

    sandbox = FailingSandbox()
    monkeypatch.setattr(sandbox_run, "create_sandbox", lambda settings: sandbox)

    assert sandbox_run.main(["--code", "print(1)"]) != 0
    assert "execution unavailable" in capsys.readouterr().err
    assert sandbox.closed == 1


def test_sandbox_build_propagates_docker_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import sandbox_build

    class Result:
        returncode = 17

    captured: list[list[str]] = []
    monkeypatch.setattr(
        sandbox_build.subprocess,
        "run",
        lambda command, check: captured.append(command) or Result(),
    )

    assert sandbox_build.main() == 17
    assert captured[0][0:3] == ["docker", "build", "--tag"]


def test_runner_disabled_backend_rejects_without_execution(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from scripts import sandbox_run

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_SANDBOX_BACKEND", "disabled")

    assert sandbox_run.main(["--code", "raise AssertionError('must not run')"]) != 0
    assert "disabled" in capsys.readouterr().err


def test_runner_host_backend_prints_unsafe_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from scripts import sandbox_run

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_SANDBOX_BACKEND", "host-unsafe")

    assert sandbox_run.main(["--code", "print('controlled')"]) == 0
    captured = capsys.readouterr()
    assert "not a security boundary" in captured.err
    assert '"exitCode": 0' in captured.out
