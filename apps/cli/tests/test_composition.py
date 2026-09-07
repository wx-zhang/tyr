from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from gamr_adapters.config import ReasoningEffort, Settings
from gamr_adapters.models import ModelStreamEvent, openai_compatible
from gamr_adapters.models.openai_compatible import OpenAICompatibleModel
from gamr_cli.composition import build_chat_session
from gamr_cli.runner_cli import build_experiment_execution


def _settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("TYR_MCP_TOKEN", "token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setenv("TYR_LOOP_MODEL", "anthropic/claude-sonnet-5")
    monkeypatch.delenv("GAMR_MODEL_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("GAMR_ADVERSARIAL_RESEARCHER_REASONING_EFFORT", raising=False)
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
            reasoning_effort: object = None,
            stream_callback: object = None,
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
            reasoning_effort: object = None,
            stream_callback: object = None,
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


def test_experiment_builder_propagates_stream_callback_to_distinct_gateways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    settings.adversarial_researcher_base_url = "http://ollama.example/v1"
    settings.adversarial_researcher_api_key = "research-key"
    callbacks: list[object] = []

    class CapturingModel:
        def __init__(
            self,
            _base_url: str,
            _api_key: str,
            _model: str,
            *,
            trace_port: object = None,
            reasoning_effort: object = None,
            stream_callback: object = None,
        ) -> None:
            callbacks.append(stream_callback)

    from gamr_cli import main as main_cli

    monkeypatch.setattr(main_cli, "OpenAICompatibleModel", CapturingModel, raising=False)
    monkeypatch.setattr(main_cli, "build_sandbox", lambda _settings: object(), raising=False)
    def callback(_event: ModelStreamEvent) -> None:
        pass

    result = build_experiment_execution(
        settings,
        "loop-model",
        "research-model",
        "judge-model",
        stream_callback=callback,
    )

    assert callbacks == [callback, callback, callback]
    assert result[4] is not result[5]
    assert result[4] is not result[6]


def test_experiment_builder_reuses_callback_enabled_main_gateway_for_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    callbacks: list[object] = []

    class CapturingModel:
        def __init__(
            self,
            _base_url: str,
            _api_key: str,
            _model: str,
            *,
            trace_port: object = None,
            reasoning_effort: object = None,
            stream_callback: object = None,
        ) -> None:
            callbacks.append(stream_callback)

    from gamr_cli import main as main_cli

    monkeypatch.setattr(main_cli, "OpenAICompatibleModel", CapturingModel, raising=False)
    monkeypatch.setattr(main_cli, "build_sandbox", lambda _settings: object(), raising=False)
    def callback(_event: ModelStreamEvent) -> None:
        pass

    result = build_experiment_execution(
        settings,
        "same-model",
        "same-model",
        "same-model",
        stream_callback=callback,
    )

    assert callbacks == [callback]
    assert result[4] is result[5] is result[6]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("loop_effort", "researcher_effort", "expected"),
    [
        ("high", None, ("high", None, None)),
        (None, "low", (None, "low", None)),
        ("high", "low", ("high", "low", None)),
        ("high", "high", ("high", "high", None)),
    ],
)
async def test_experiment_gateways_send_role_specific_reasoning_effort(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    loop_effort: ReasoningEffort | None,
    researcher_effort: ReasoningEffort | None,
    expected: tuple[str | None, str | None, str | None],
) -> None:
    requests: list[dict[str, object]] = []

    class CapturingCompletions:
        async def create(self, **request: object) -> SimpleNamespace:
            requests.append(request)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="ok", refusal=None),
                        finish_reason="stop",
                    )
                ],
                usage=None,
                model="test-model",
            )

    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: SimpleNamespace(
            chat=SimpleNamespace(completions=CapturingCompletions())
        ),
    )
    from gamr_cli import main as main_cli

    monkeypatch.setattr(main_cli, "build_sandbox", lambda _settings: object(), raising=False)
    settings = Settings(
        artifact_root=str(tmp_path),
        tyr_mcp_token="token",
        model_api_key="key",
        model_base_url="https://example.test/v1",
        model_reasoning_effort=loop_effort,
        adversarial_researcher_reasoning_effort=researcher_effort,
    )

    gateways = build_experiment_execution(
        settings, "same-model", "same-model", "same-model"
    )
    for gateway in gateways[4:7]:
        assert (await gateway.complete("hello"))["content"] == "ok"

    assert [request.get("reasoning_effort") for request in requests] == list(expected)
    assert [
        "reasoning_effort" in request for request in requests
    ] == [value is not None for value in expected]


@pytest.mark.asyncio
async def test_chat_gateway_ignores_experiment_reasoning_effort_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, object]] = []

    class CapturingCompletions:
        async def create(self, **request: object) -> SimpleNamespace:
            requests.append(request)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="ok", refusal=None),
                        finish_reason="stop",
                    )
                ],
                usage=None,
                model="test-model",
            )

    monkeypatch.setattr(
        openai_compatible,
        "AsyncOpenAI",
        lambda *, base_url, api_key: SimpleNamespace(
            chat=SimpleNamespace(completions=CapturingCompletions())
        ),
    )
    settings = Settings(
        tyr_mcp_token="token",
        model_api_key="key",
        model_base_url="https://example.test/v1",
        model_reasoning_effort="high",
        adversarial_researcher_reasoning_effort="low",
    )

    session, target = build_chat_session(settings, model_name="same-model")
    try:
        chat_model = cast(OpenAICompatibleModel, session.model)
        assert (await chat_model.complete("hello"))["content"] == "ok"
    finally:
        await target.aclose()

    assert "reasoning_effort" not in requests[0]
