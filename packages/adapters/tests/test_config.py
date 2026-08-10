from __future__ import annotations

from pathlib import Path

import pytest
from gamr_adapters.config import Settings


def test_settings_load_provider_env_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TYR_MCP_TOKEN", raising=False)
    monkeypatch.delenv("TYR_MCP_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("TYR_LOOP_MODEL", raising=False)
    monkeypatch.delenv("GAMR_TYR_MCP_TOKEN", raising=False)
    monkeypatch.delenv("GAMR_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("GAMR_MODEL_NAME", raising=False)

    monkeypatch.setenv("TYR_MCP_TOKEN", "token")
    monkeypatch.setenv("TYR_MCP_URL", "https://example.test/mcp")
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("TYR_LOOP_MODEL", "example/model")

    settings = Settings()

    assert settings.tyr_mcp_token == "token"
    assert settings.tyr_mcp_url == "https://example.test/mcp"
    assert settings.model_api_key == "key"
    assert settings.model_base_url == "https://example.test/v1"
    assert settings.model_name == "example/model"


def test_settings_ignore_removed_gamr_provider_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TYR_MCP_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("TYR_LOOP_MODEL", raising=False)
    monkeypatch.setenv("GAMR_TYR_MCP_TOKEN", "gamr-token")
    monkeypatch.setenv("GAMR_MODEL_API_KEY", "gamr-key")
    monkeypatch.setenv("GAMR_MODEL_NAME", "gamr/model")

    settings = Settings()

    assert settings.tyr_mcp_token == ""
    assert settings.model_api_key == ""
    assert settings.model_name == ""
