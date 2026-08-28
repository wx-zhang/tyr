from typing import cast

import pytest
from gamr_adapters.config import Settings
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_cli.composition import build_chat_session
from gamr_cli.runner_cli import build_experiment_execution


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


def test_experiment_builder_uses_researcher_endpoint_only_for_researcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    settings.model_base_url = "https://openrouter.example/v1"
    settings.adversarial_researcher_base_url = "http://ollama.example/v1"
    settings.adversarial_researcher_api_key = "research-key"
    captures: list[tuple[str, str, str]] = []

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

    from gamr_cli import main as main_cli

    monkeypatch.setattr(main_cli, "OpenAICompatibleModel", CapturingModel, raising=False)
    monkeypatch.setattr(main_cli, "build_sandbox", lambda _settings: object(), raising=False)

    result = build_experiment_execution(settings, "loop-model", "research-model", "judge-model")

    assert captures == [
        ("https://openrouter.example/v1", "key", "loop-model"),
        ("http://ollama.example/v1", "research-key", "research-model"),
        ("https://openrouter.example/v1", "key", "judge-model"),
    ]
    assert "research-key" in result[0].secrets
    assert result[4] is not result[5]
    assert result[4] is not result[6]


def test_experiment_builder_falls_back_and_separates_same_model_researcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    settings.model_base_url = "https://openrouter.example/v1"
    settings.adversarial_researcher_base_url = "http://ollama.example/v1"
    settings.adversarial_researcher_api_key = "research-key"
    captures: list[tuple[str, str]] = []

    class CapturingModel:
        def __init__(
            self,
            base_url: str,
            api_key: str,
            _model: str,
            *,
            trace_port: object = None,
        ) -> None:
            captures.append((base_url, api_key))

    from gamr_cli import main as main_cli

    monkeypatch.setattr(main_cli, "OpenAICompatibleModel", CapturingModel, raising=False)
    monkeypatch.setattr(main_cli, "build_sandbox", lambda _settings: object(), raising=False)

    result = build_experiment_execution(settings, "same-model", "same-model", "same-model")

    assert captures == [
        ("https://openrouter.example/v1", "key"),
        ("http://ollama.example/v1", "research-key"),
    ]
    assert result[4] is result[6]
    assert result[4] is not result[5]

    settings.adversarial_researcher_base_url = ""
    settings.adversarial_researcher_api_key = None
    captures.clear()
    fallback_result = build_experiment_execution(
        settings, "same-model", "same-model", "same-model"
    )

    assert captures == [("https://openrouter.example/v1", "key")]
    assert fallback_result[4] is fallback_result[5]

    settings.adversarial_researcher_base_url = "http://ollama.example/v1"
    settings.adversarial_researcher_api_key = ""
    captures.clear()
    no_auth_result = build_experiment_execution(
        settings, "same-model", "same-model", "same-model"
    )

    assert captures == [
        ("https://openrouter.example/v1", "key"),
        ("http://ollama.example/v1", ""),
    ]
    assert no_auth_result[4] is not no_auth_result[5]
