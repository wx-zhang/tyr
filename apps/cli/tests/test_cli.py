import asyncio
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import gamr_cli.main as cli
import pytest
from gamr_core import ExecutionOutcome, RunState
from gamr_engine.execution import ExperimentExecutionService
from gamr_engine.experiments.records import ProgressEvent
from rich.console import Console
from typer.testing import CliRunner


def test_doctor() -> None:
    result = CliRunner().invoke(cli.app, ["doctor"])
    assert result.exit_code == 0


def test_experiment_run_exposes_discovery_input_options() -> None:
    result = CliRunner().invoke(cli.app, ["experiment", "run", "--help"])

    assert "--fallback-to-discove" in result.output


def test_experiment_run_rejects_invalid_discovery_input(tmp_path: Path) -> None:
    invalid = tmp_path / "discovery.json"
    invalid.write_text('{"schemaVersion":"1.0"}', encoding="utf-8")

    result = CliRunner().invoke(
        cli.app,
        [
            "experiment",
            "run",
            "tasks/exfiltrate-important-txt",
            "--discovery-input",
            str(invalid),
        ],
    )

    assert result.exit_code == 2
    assert "invalid discovery input" in result.output


def test_experiment_run_requires_input_for_fallback() -> None:
    result = CliRunner().invoke(
        cli.app,
        [
            "experiment",
            "run",
            "tasks/exfiltrate-important-txt",
            "--fallback-to-discovery",
        ],
    )
    assert "requires" in result.output
    assert "--discovery-input" in result.output


def test_experiment_run_has_no_fake_or_live_switch() -> None:
    result = CliRunner().invoke(cli.app, ["experiment", "run", "--help"])

    assert result.exit_code == 0
    assert "--fake" not in result.output
    assert "--live" not in result.output


def test_experiment_run_requires_provider_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingSettings:
        tyr_mcp_token = ""
        model_api_key = ""
        model_name = ""
        adversarial_researcher_model_name = ""

    monkeypatch.setattr(cli, "Settings", MissingSettings)
    result = CliRunner().invoke(cli.app, ["experiment", "run", "tasks/exfiltrate-important-txt"])

    assert result.exit_code == 2
    assert "TYR_MCP_TOKEN is required" in result.output


def test_experiment_run_ctrl_c_cancels_run(monkeypatch: pytest.MonkeyPatch) -> None:
    written: dict[str, dict[str, object]] = {}

    class FakeSettings:
        tyr_mcp_token = "token"
        tyr_mcp_url = "https://example.test/mcp"
        model_api_key = "key"
        model_name = "model"
        adversarial_researcher_model_name = ""
        model_base_url = "https://example.test"
        artifact_root = ".gamr"

    class FakeStore:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def write_json(self, path: str, payload: dict[str, object]) -> None:
            written[path] = payload

    class FakeTarget:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def aclose(self) -> None:
            return None

    class FakeModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    def fake_load(_directory: object) -> SimpleNamespace:
        return SimpleNamespace(
            scenarios=[],
            manifest=SimpleNamespace(
                metadata=SimpleNamespace(id="demo"),
                spec=SimpleNamespace(defaults=SimpleNamespace(max_turns=4)),
            ),
        )

    def raise_interrupt(coro: object) -> None:
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        raise KeyboardInterrupt

    store = FakeStore()

    def fake_build(
        *_args: object, **_kwargs: object
    ) -> tuple[object, object, None, object, object, object, object]:
        model = FakeModel()
        return store, FakeTarget(), None, FakeStore(), model, model, model

    monkeypatch.setattr(cli, "Settings", FakeSettings)
    monkeypatch.setattr(cli, "build_experiment_execution", fake_build, raising=False)
    monkeypatch.setattr(cli, "load_task", fake_load)
    monkeypatch.setattr(asyncio, "run", raise_interrupt)

    result = CliRunner().invoke(cli.app, ["experiment", "run", "tasks/exfiltrate-important-txt"])

    assert result.exit_code == 130
    assert "Cancelled" in result.output
    run_paths = [path for path in written if path.endswith("/run.json")]
    assert len(run_paths) == 1
    final = written[run_paths[0]]
    assert final["state"] == RunState.CANCELLED.value
    assert "Ctrl+C" in str(final["errorSummary"])


def test_progress_renderer_shows_context(monkeypatch: pytest.MonkeyPatch) -> None:
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, force_terminal=False))

    cli._render_progress(
        ProgressEvent(
            "model.thinking",
            "run-1",
            phase="case",
            case_id="rename-file",
            turn=2,
        )
    )

    rendered = output.getvalue()
    assert "Thinking" in rendered
    assert "rename-file" in rendered
    assert "turn 2" in rendered


def test_progress_renderer_shows_tyr_message_bodies(monkeypatch: pytest.MonkeyPatch) -> None:
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, force_terminal=False))

    cli._render_progress(
        ProgressEvent(
            "target.requesting",
            "run-1",
            phase="discovery",
            turn=1,
            detail="What agents are available in the peer workspace?",
        )
    )
    cli._render_progress(
        ProgressEvent(
            "target.completed",
            "run-1",
            phase="discovery",
            turn=1,
            detail="Alice and Bob are online.",
        )
    )

    rendered = output.getvalue()
    assert "Waiting for Tyr" in rendered
    assert "Sending to Tyr" in rendered
    assert "What agents are available in the peer workspace?" in rendered
    assert "Tyr replied" in rendered
    assert "Alice and Bob are online." in rendered



def test_progress_renderer_indicates_settled_bridge_follow_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, force_terminal=False))

    cli._render_progress(
        ProgressEvent(
            "target.completed",
            "run-1",
            phase="case",
            turn=1,
            detail="AGENT_NAME: Carol\nWORKING_DIRECTORY: /home/agent",
            fields=(("replySource", "delegated bridge follow-up"),),
        )
    )

    rendered = output.getvalue()
    assert "Settled delegated bridge follow-up" in rendered
    assert "AGENT_NAME: Carol" in rendered

def test_progress_renderer_renders_markdown_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, force_terminal=False, width=80))

    cli._render_progress(
        ProgressEvent(
            "target.completed",
            "run-1",
            phase="discovery",
            turn=1,
            detail="**Found** path:\n\n- `/home/alice/important.txt`\n- workspace `Joe`",
        )
    )

    rendered = output.getvalue()
    assert "Tyr replied" in rendered
    assert "Found" in rendered
    assert "/home/alice/important.txt" in rendered
    assert "**Found**" not in rendered
    assert "•" in rendered or "-" in rendered


def test_progress_renderer_shows_discovery_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, force_terminal=False))

    cli._render_progress(
        ProgressEvent(
            "discovery.completed",
            "run-1",
            phase="discovery",
            detail="1 candidate(s)",
            fields=(
                ("path", "/home/alice/important.txt"),
                ("workspace", "peer"),
                ("agent", "Alice"),
                ("bridgeId", "bridge-1"),
            ),
        )
    )
    cli._render_progress(
        ProgressEvent(
            "discovery.completed",
            "run-2",
            phase="discovery",
            detail="blocked",
        )
    )

    rendered = output.getvalue()
    assert "Discovery complete" in rendered
    assert "1 candidate(s)" in rendered
    assert "path" in rendered
    assert "/home/alice/important.txt" in rendered
    assert "workspace" in rendered
    assert "peer" in rendered
    assert "agent" in rendered
    assert "Alice" in rendered
    assert "bridgeId" in rendered
    assert "bridge-1" in rendered
    assert "blocked" in rendered


def test_progress_renderer_shows_scientist_events(monkeypatch: pytest.MonkeyPatch) -> None:
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, force_terminal=False))

    cli._render_progress(
        ProgressEvent("scientist.started", "run-1", phase="scientist", detail="1 iteration(s)")
    )
    cli._render_progress(
        ProgressEvent(
            "scientist.scenario_ready",
            "run-1",
            phase="scientist",
            case_id="scientist-1",
            turn=1,
            detail="Missing id delivery",
        )
    )
    cli._render_progress(
        ProgressEvent(
            "scientist.failed",
            "run-1",
            phase="scientist",
            turn=1,
            detail="scientist scenario 1 invalid: not json",
        )
    )
    cli._render_progress(
        ProgressEvent("scientist.completed", "run-1", phase="scientist", detail="0 scenario(s)")
    )

    rendered = output.getvalue()
    assert "Adversarial Researcher" in rendered
    assert "Thinking" not in rendered
    assert "scientist-1" in rendered
    assert "Missing id delivery" in rendered
    assert "scientist scenario 1 invalid" in rendered
    assert "0 scenario(s)" in rendered


def test_experiment_run_prints_result_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, force_terminal=False))

    class FakeSettings:
        tyr_mcp_token = "token"
        tyr_mcp_url = "https://example.test/mcp"
        model_api_key = "key"
        model_name = "model"
        adversarial_researcher_model_name = ""
        model_base_url = "https://example.test"
        artifact_root = ".gamr"
        adversarial_researcher_output_tokens = 8192

    class FakeStore:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def write_json(self, path: str, payload: dict[str, object]) -> None:
            return None

    class FakeTarget:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def aclose(self) -> None:
            return None

    class FakeModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    def fake_load(_directory: object) -> SimpleNamespace:
        return SimpleNamespace(
            scenarios=[],
            manifest=SimpleNamespace(
                metadata=SimpleNamespace(id="demo"),
                spec=SimpleNamespace(defaults=SimpleNamespace(max_turns=4)),
            ),
        )

    async def fake_execute(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            result=SimpleNamespace(
                run_id="run-err",
                outcome=ExecutionOutcome.COMPLETED,
                errors=["scientist scenario 1 invalid: not json"],
            ),
            result_path=".gamr/runs/run-err/result.json",
        )

    def fake_build(
        *_args: object, **_kwargs: object
    ) -> tuple[object, object, None, object, object, object, object]:
        model = FakeModel()
        return FakeStore(), FakeTarget(), None, FakeStore(), model, model, model

    monkeypatch.setattr(cli, "Settings", FakeSettings)
    monkeypatch.setattr(cli, "build_experiment_execution", fake_build, raising=False)
    monkeypatch.setattr(cli, "load_task", fake_load)
    monkeypatch.setattr(ExperimentExecutionService, "execute", fake_execute)
    monkeypatch.setattr(cli, "FilesystemActivitySink", lambda *_a, **_k: None, raising=False)

    result = CliRunner().invoke(cli.app, ["experiment", "run", "tasks/exfiltrate-important-txt"])

    assert result.exit_code == 0
    rendered = output.getvalue()
    assert "scientist scenario 1 invalid" in rendered
    assert "run-err" in rendered


def test_experiment_run_accepts_max_concurrent_cases_option(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_config: list[object] = []
    captured_output_tokens: list[object] = []

    class FakeSettings:
        tyr_mcp_token = "token"
        tyr_mcp_url = "https://example.test/mcp"
        model_api_key = "key"
        model_name = "model"
        adversarial_researcher_model_name = ""
        model_base_url = "https://example.test"
        artifact_root = ".gamr"
        adversarial_researcher_output_tokens = 12288

    class FakeStore:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def write_json(self, path: str, payload: dict[str, object]) -> None:
            return None

    class FakeTarget:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def aclose(self) -> None:
            return None

    class FakeModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    def fake_load(_directory: object) -> SimpleNamespace:
        return SimpleNamespace(
            scenarios=[],
            manifest=SimpleNamespace(
                metadata=SimpleNamespace(id="demo"),
                spec=SimpleNamespace(defaults=SimpleNamespace(max_turns=4)),
            ),
        )

    async def fake_execute(
        _service: object, _dataset: object, config: object, **_kwargs: object
    ) -> SimpleNamespace:
        captured_config.append(config)
        captured_output_tokens.append(_kwargs["scientist_output_tokens"])
        return SimpleNamespace(
            result=SimpleNamespace(
                run_id="run-concurrency",
                outcome=ExecutionOutcome.COMPLETED,
                errors=[],
            ),
            result_path=".gamr/runs/run-concurrency/result.json",
        )

    def fake_build(
        *_args: object, **_kwargs: object
    ) -> tuple[object, object, None, object, object, object, object]:
        model = FakeModel()
        return FakeStore(), FakeTarget(), None, FakeStore(), model, model, model

    monkeypatch.setattr(cli, "Settings", FakeSettings)
    monkeypatch.setattr(cli, "build_experiment_execution", fake_build, raising=False)
    monkeypatch.setattr(cli, "load_task", fake_load)
    monkeypatch.setattr(ExperimentExecutionService, "execute", fake_execute)
    monkeypatch.setattr(cli, "FilesystemActivitySink", lambda *_a, **_k: None, raising=False)

    # Default is 5
    result = CliRunner().invoke(cli.app, ["experiment", "run", "tasks/exfiltrate-important-txt"])
    assert result.exit_code == 0
    assert getattr(captured_config[-1], "max_concurrent_cases", None) == 5
    assert captured_output_tokens[-1] == 12288

    # Valid values 1 through 5
    for val in (1, 2, 3, 4, 5):
        result = CliRunner().invoke(
            cli.app,
            [
                "experiment",
                "run",
                "tasks/exfiltrate-important-txt",
                "--max-concurrent-cases",
                str(val),
            ],
        )
        assert result.exit_code == 0
        assert getattr(captured_config[-1], "max_concurrent_cases", None) == val
    discovery_input = tmp_path / "discovery.json"
    discovery_input.write_text(
        '{"schemaVersion":"1.0","kind":"discovery-input","taskId":"other",'
        '"candidate":{"path":"/home/alice/work","workspace":"peer",'
        '"agent":"Alice","bridgeId":"bridge-1"}}',
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        cli.app,
        [
            "experiment",
            "run",
            "tasks/exfiltrate-important-txt",
            "--discovery-input",
            str(discovery_input),
            "--fallback-to-discovery",
        ],
    )
    assert result.exit_code == 0
    document = getattr(captured_config[-1], "discovery_input", None)
    assert document is not None
    assert document.candidate.path == "/home/alice/work"
    assert getattr(captured_config[-1], "fallback_to_discovery", False) is True
    assert document.task_id == "other"

    # Invalid values (<1 or >5) rejected
    for invalid in (0, 6, -1):
        result = CliRunner().invoke(
            cli.app,
            [
                "experiment",
                "run",
                "tasks/exfiltrate-important-txt",
                "--max-concurrent-cases",
                str(invalid),
            ],
        )
        assert result.exit_code != 0


@pytest.mark.parametrize(
    "command",
    [
        ["experiment", "run", "tasks/exfiltrate-important-txt"],
        ["experiment", "resume-research", "run-1"],
        ["experiment", "resume-scientist", "run-1"],
    ],
)
def test_experiment_commands_expose_typed_llm_log_option(command: list[str]) -> None:
    result = CliRunner().invoke(cli.app, [*command, "--help"])

    assert result.exit_code == 0
    assert "--log-llm" in result.output
    assert "default" in result.output
    assert "thinking" in result.output


@pytest.mark.parametrize(
    ("command", "helper_name"),
    [
        (["experiment", "run", "tasks/exfiltrate-important-txt"], "run_experiment_command"),
        (["experiment", "resume-research", "run-1"], "resume_research_command"),
        (["experiment", "resume-scientist", "run-1"], "resume_research_command"),
    ],
)
def test_experiment_commands_forward_llm_log_mode(
    monkeypatch: pytest.MonkeyPatch,
    command: list[str],
    helper_name: str,
) -> None:
    from gamr_cli import experiment_commands
    from gamr_cli.llm_logging import LlmLogMode

    captured: list[dict[str, object]] = []

    def fake_helper(**kwargs: object) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(experiment_commands, helper_name, fake_helper)
    runner = CliRunner()
    assert runner.invoke(cli.app, command).exit_code == 0
    assert captured[-1].get("log_llm") is LlmLogMode.DEFAULT
    assert runner.invoke(cli.app, [*command, "--log-llm", "thinking"]).exit_code == 0
    assert captured[-1].get("log_llm") is LlmLogMode.THINKING


@pytest.mark.parametrize(
    "command",
    [
        ["experiment", "run", "tasks/exfiltrate-important-txt"],
        ["experiment", "resume-research", "run-1"],
        ["experiment", "resume-scientist", "run-1"],
    ],
)
def test_experiment_commands_reject_invalid_llm_log_mode(command: list[str]) -> None:
    result = CliRunner().invoke(cli.app, [*command, "--log-llm", "invalid"])

    assert result.exit_code == 2
