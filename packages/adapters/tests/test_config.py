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
    monkeypatch.setenv("TYR_COLLECTOR_USERNAME", "collector-user")
    monkeypatch.setenv("TYR_COLLECTOR_PASSWORD", "collector-password")
    monkeypatch.setenv("TYR_COLLECTOR_BASE_URL", "https://collector.test/base")

    settings = Settings()

    assert settings.tyr_mcp_token == "token"
    assert settings.tyr_mcp_url == "https://example.test/mcp"
    assert settings.model_api_key == "key"
    assert settings.model_base_url == "https://example.test/v1"
    assert settings.model_name == "example/model"
    assert settings.collector_username == "collector-user"
    assert settings.collector_password == "collector-password"
    assert settings.collector_base_url == "https://collector.test/base"


def test_chat_model_defaults_independently_of_loop_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TYR_LOOP_CHAT_MODEL", raising=False)
    monkeypatch.setenv("TYR_LOOP_MODEL", "anthropic/claude-sonnet-5")

    settings = Settings()

    assert settings.model_name == "anthropic/claude-sonnet-5"
    assert settings.chat_model_name == "x-ai/grok-4.5"


def test_chat_model_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TYR_LOOP_CHAT_MODEL", "example/other-model")

    settings = Settings()

    assert settings.chat_model_name == "example/other-model"


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
