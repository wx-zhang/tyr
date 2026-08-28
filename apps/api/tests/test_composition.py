from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from gamr_adapters.config import Settings
from gamr_api import composition
from gamr_api.registry import InMemoryRegistry, JsonRegistry
from gamr_core import ExperimentPresetConfig, RunSource


@pytest.mark.asyncio
async def test_run_executor_uses_researcher_endpoint_only_for_researcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TYR_MCP_TOKEN", "token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.example/v1")
    monkeypatch.setenv(
        "GAMR_ADVERSARIAL_RESEARCHER_BASE_URL", "http://ollama.example/v1"
    )
    monkeypatch.setenv("GAMR_ADVERSARIAL_RESEARCHER_API_KEY", "research-key")
    settings = Settings()
    registry = cast(JsonRegistry, InMemoryRegistry())
    run = registry.create_run(
        None,
        "tasks/example",
        ExperimentPresetConfig(
            model="loop-model",
            adversarial_researcher_model="research-model",
            judge_model="judge-model",
            research_iterations=1,
        ),
        source=RunSource.SERVICE,
    )
    captures: list[tuple[str, str, str]] = []
    artifact_secrets: list[str] = []

    class CapturingArtifactStore:
        def __init__(self, *_args: object, secrets: tuple[str, ...]) -> None:
            artifact_secrets.extend(secrets)

    class CapturingModel:
        def __init__(
            self,
            base_url: str,
            api_key: str,
            model: str,
            *,
            trace_port: object = None,
        ) -> None:
            captures.append((base_url, api_key, model))

    class FakeTarget:
        def __init__(self, *_args: object) -> None:
            pass

        async def aclose(self) -> None:
            return None

    class FakeExecutionService:
        async def execute(self, *args: object, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(result_path="runs/result.json")

    monkeypatch.setattr(composition, "OpenAICompatibleModel", CapturingModel)
    monkeypatch.setattr(composition, "TyrMcpClient", FakeTarget)
    monkeypatch.setattr(composition, "FilesystemArtifactStore", CapturingArtifactStore)
    monkeypatch.setattr(composition, "FilesystemActivitySink", lambda *args, **kwargs: object())
    monkeypatch.setattr(composition, "build_sandbox", lambda _settings: object())
    monkeypatch.setattr(composition, "resolve_task_directory", lambda *_args: "task-path")
    monkeypatch.setattr(composition, "load_task", lambda _path: object())
    monkeypatch.setattr(composition, "ExperimentExecutionService", FakeExecutionService)

    execute = composition.build_run_executor(settings, registry)

    assert await execute(run.id) == "runs/result.json"
    assert captures == [
        ("https://openrouter.example/v1", "key", "loop-model"),
        ("http://ollama.example/v1", "research-key", "research-model"),
        ("https://openrouter.example/v1", "key", "judge-model"),
    ]
    assert "research-key" in artifact_secrets
