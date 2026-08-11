from typing import cast

import pytest
from gamr_adapters.config import Settings
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_cli.composition import build_chat_session


def _settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("TYR_MCP_TOKEN", "token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("TYR_LOOP_MODEL", "anthropic/claude-sonnet-5")
    return Settings()


def test_chat_session_defaults_to_the_chat_model_not_the_loop_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _ = build_chat_session(_settings(monkeypatch))

    model = cast(OpenAICompatibleModel, session.model)
    assert model.model == "x-ai/grok-4.5"


def test_chat_session_honors_an_explicit_model_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _ = build_chat_session(_settings(monkeypatch), model_name="example/override")

    model = cast(OpenAICompatibleModel, session.model)
    assert model.model == "example/override"
