from pathlib import Path
from types import SimpleNamespace
from typing import Any

import gamr_cli.evaluation_cli as evaluation_cli
import pytest
from gamr_cli import main
from rich.console import Console
from typer.testing import CliRunner


def test_evaluate_judges_cli_delegates_without_tyr(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, str, list[str], bool]] = []

    def run_command(
        _console: Any,
        dataset: Path,
        model: str,
        case_ids: list[str],
        debug: bool,
    ) -> None:
        calls.append((dataset, model, case_ids, debug))

    monkeypatch.setattr(main, "run_judge_evaluation_command", run_command)

    result = CliRunner().invoke(
        main.app,
        [
            "evaluate",
            "judges",
            "--model",
            "judge-model",
            "--case-id",
            "case-a",
            "--debug",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            Path("evaluations/judges/evidence-and-content/dataset.json"),
            "judge-model",
            ["case-a"],
            True,
        )
    ]


def test_judge_evaluation_writes_artifacts_under_judges_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_roots: list[Path] = []

    async def run_dataset(_dataset: Any, *, output_root: Path, **_kwargs: Any) -> dict[str, Any]:
        output_roots.append(output_root)
        return {"passed": True, "cases": []}

    settings = SimpleNamespace(
        model_api_key="api-key",
        judge_model_name="",
        model_name="judge-model",
        sandbox_backend="docker",
        artifact_root=str(tmp_path),
        model_base_url="https://example.test/v1",
    )
    dataset = SimpleNamespace(cases=[])
    monkeypatch.setattr(evaluation_cli, "Settings", lambda: settings)
    monkeypatch.setattr(evaluation_cli, "load_evaluation_dataset", lambda _path: dataset)
    monkeypatch.setattr(evaluation_cli, "configured_secrets", lambda _settings: ())
    monkeypatch.setattr(evaluation_cli, "build_sandbox", lambda _settings: object())
    monkeypatch.setattr(evaluation_cli, "OpenAICompatibleModel", lambda *_args: object())
    monkeypatch.setattr(evaluation_cli, "new_id", lambda: "eval-1")
    monkeypatch.setattr(evaluation_cli, "run_evaluation_dataset", run_dataset)

    evaluation_cli.run_judge_evaluation_command(Console(), Path("dataset.json"), "", [], False)

    assert output_roots == [tmp_path / "evaluations" / "judges" / "eval-1"]
