from __future__ import annotations

import pytest
from gamr_adapters.config import Settings
from gamr_cli.composition import build_chat_session
from gamr_cli.runner_cli import build_experiment_execution
from gamr_engine.ports.tracing import TraceObservation


class FakeRecordingTracePort:
    def __init__(self) -> None:
        self.flushed = False

    def open_trace(
        self,
        name: str,
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
        metadata: dict[str, object] | None = None,
        tags: list[str] | None = None,
        input: object = None,
        output: object = None,
    ) -> TraceObservation:
        raise NotImplementedError

    def open_span(
        self,
        name: str,
        *,
        metadata: dict[str, object] | None = None,
        input: object = None,
        output: object = None,
        parent: TraceObservation | None = None,
    ) -> TraceObservation:
        raise NotImplementedError

    def open_generation(
        self,
        name: str,
        *,
        model: str | None = None,
        model_parameters: dict[str, object] | None = None,
        input: object = None,
        output: object = None,
        usage: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        parent: TraceObservation | None = None,
    ) -> TraceObservation:
        raise NotImplementedError

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        observation: TraceObservation | None = None,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        pass

    def flush(self, timeout: float | None = None) -> None:
        self.flushed = True


def test_composition_creates_trace_adapter_when_langfuse_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        tyr_mcp_token="mcp-token",
        model_api_key="or-key",
        model_name="test-model",
        langfuse_enabled=True,
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        langfuse_host_url="http://127.0.0.1:2300",
    )
    fake_port = FakeRecordingTracePort()
    import gamr_cli.composition as comp
    import gamr_cli.runner_cli as rc

    monkeypatch.setattr(rc, "create_trace_port", lambda _s: fake_port)
    monkeypatch.setattr(comp, "create_trace_port", lambda _s: fake_port)

    # CLI experiment build
    res = build_experiment_execution(settings, "test-model", "test-model", "test-model")
    model_gateway = res[4]
    assert getattr(model_gateway, "trace_port", None) is fake_port

    # CLI chat build
    session, _ = build_chat_session(settings)
    assert session.trace_port is fake_port


def test_composition_has_no_trace_adapter_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        tyr_mcp_token="mcp-token",
        model_api_key="or-key",
        model_name="test-model",
        langfuse_enabled=False,
    )
    res = build_experiment_execution(settings, "test-model", "test-model", "test-model")
    model_gateway = res[4]
    assert getattr(model_gateway, "trace_port", None) is None

    session, _ = build_chat_session(settings)
    assert session.trace_port is None
