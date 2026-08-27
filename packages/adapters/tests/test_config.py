from __future__ import annotations

from pathlib import Path

import pytest
from gamr_adapters.config import Settings
from pydantic import ValidationError


def test_settings_load_provider_env_names(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def test_chat_model_can_be_overridden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def test_max_concurrent_decoders_defaults_to_two(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GAMR_MAX_CONCURRENT_DECODERS", raising=False)

    settings = Settings()

    assert settings.max_concurrent_decoders == 2


@pytest.mark.parametrize("value", [1, 2, 5, 10, 100])
def test_max_concurrent_decoders_accepts_positive_integers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: int
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_MAX_CONCURRENT_DECODERS", str(value))

    settings = Settings()

    assert settings.max_concurrent_decoders == value


@pytest.mark.parametrize("invalid_value", [0, -1, -5, "abc", "1.5", ""])
def test_max_concurrent_decoders_rejects_zero_negative_and_non_integer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, invalid_value: object
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_MAX_CONCURRENT_DECODERS", str(invalid_value))

    with pytest.raises(ValidationError):
        Settings()


def test_scientist_output_tokens_defaults_to_eight_thousand(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GAMR_SCIENTIST_OUTPUT_TOKENS", raising=False)

    settings = Settings()

    assert settings.scientist_output_tokens == 8192


def test_scientist_output_tokens_uses_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_SCIENTIST_OUTPUT_TOKENS", "12288")

    settings = Settings()

    assert settings.scientist_output_tokens == 12288


@pytest.mark.parametrize("invalid_value", [0, -1, "abc", "1.5", ""])
def test_scientist_output_tokens_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, invalid_value: object
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_SCIENTIST_OUTPUT_TOKENS", str(invalid_value))

    with pytest.raises(ValidationError):
        Settings()


def test_settings_langfuse_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GAMR_LANGFUSE_ENABLED", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    settings = Settings()

    assert settings.langfuse_enabled is False
    assert settings.is_langfuse_valid is False


def test_settings_langfuse_credentials_without_enablement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GAMR_LANGFUSE_ENABLED", raising=False)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-123")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-456")
    monkeypatch.setenv("LANGFUSE_HOST", "http://127.0.0.1:3000")

    settings = Settings()

    assert settings.langfuse_enabled is False
    assert settings.langfuse_public_key == "pk-lf-123"
    assert settings.langfuse_secret_key == "sk-lf-456"
    assert settings.is_langfuse_valid is False


def test_settings_langfuse_valid_local_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-123")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-456")
    monkeypatch.setenv("LANGFUSE_HOST", "http://127.0.0.1:3000")
    monkeypatch.setenv("GAMR_LANGFUSE_CONTAINER_URL", "http://langfuse-server:3000")
    monkeypatch.setenv("GAMR_LANGFUSE_ENVIRONMENT", "staging")

    settings = Settings()

    assert settings.langfuse_enabled is True
    assert settings.langfuse_public_key == "pk-lf-123"
    assert settings.langfuse_secret_key == "sk-lf-456"
    assert settings.langfuse_host_url == "http://127.0.0.1:3000"
    assert settings.langfuse_container_url == "http://langfuse-server:3000"
    assert settings.langfuse_environment == "staging"
    assert settings.is_langfuse_valid is True


def test_settings_langfuse_invalid_enabled_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAMR_LANGFUSE_ENABLED", "true")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    settings = Settings()

    assert settings.langfuse_enabled is True
    assert settings.is_langfuse_valid is False
