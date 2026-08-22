from __future__ import annotations

from pathlib import Path

import pytest
from gamr_adapters.config import Settings
from gamr_adapters.sandbox.factory import create_sandbox
from gamr_engine.ports import SandboxUnavailableError
from pydantic import ValidationError


def test_sandbox_backend_defaults_to_docker_without_probing_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GAMR_SANDBOX_BACKEND", raising=False)

    settings = Settings()

    assert settings.sandbox_backend == "docker"


@pytest.mark.parametrize("backend", ["docker", "host-unsafe", "disabled"])
def test_sandbox_backend_accepts_only_supported_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, backend: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_SANDBOX_BACKEND", backend)

    assert Settings().sandbox_backend == backend


def test_sandbox_backend_rejects_unknown_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_SANDBOX_BACKEND", "local-root")

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.asyncio
async def test_disabled_backend_is_unavailable_and_close_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    sandbox = create_sandbox(Settings(sandbox_backend="disabled"))

    with pytest.raises(SandboxUnavailableError):
        await sandbox.start()
    await sandbox.close("not-created")  # type: ignore[arg-type]


def test_factory_does_not_construct_docker_until_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    sandbox = create_sandbox(Settings(sandbox_backend="docker"))

    assert sandbox.__class__.__name__ == "DockerSandbox"
