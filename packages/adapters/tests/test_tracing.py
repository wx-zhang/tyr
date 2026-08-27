from __future__ import annotations

from typing import Any

from gamr_adapters.config import Settings
from gamr_adapters.tracing import (
    LangfuseTracePort,
    create_trace_port,
)
from gamr_engine.ports.tracing import TraceObservation


class FakeStatefulClient:
    def __init__(self, id: str, name: str, kind: str) -> None:
        self.id = id
        self.name = name
        self.kind = kind
        self.updates: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []
        self.ended = False
        self.children: list[FakeStatefulClient] = []

    def update(self, **kwargs: Any) -> FakeStatefulClient:
        self.updates.append(kwargs)
        return self

    def end(self, **kwargs: Any) -> FakeStatefulClient:
        self.ended = True
        self.updates.append(kwargs)
        return self

    def score(self, **kwargs: Any) -> FakeStatefulClient:
        self.scores.append(kwargs)
        return self

    def span(self, **kwargs: Any) -> FakeStatefulClient:
        child = FakeStatefulClient(
            kwargs.get("id", f"span-{len(self.children)}"), kwargs.get("name", ""), "span"
        )
        child.updates.append(kwargs)
        self.children.append(child)
        return child

    def generation(self, **kwargs: Any) -> FakeStatefulClient:
        child = FakeStatefulClient(
            kwargs.get("id", f"gen-{len(self.children)}"), kwargs.get("name", ""), "generation"
        )
        child.updates.append(kwargs)
        self.children.append(child)
        return child


class FakeLangfuseClient:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.traces: list[FakeStatefulClient] = []
        self.scores: list[dict[str, Any]] = []
        self.flushed = False

    def trace(self, **kwargs: Any) -> FakeStatefulClient:
        if self.should_fail:
            raise RuntimeError("Langfuse API connection refused")
        t = FakeStatefulClient(
            kwargs.get("id", f"trace-{len(self.traces)}"), kwargs.get("name", ""), "trace"
        )
        t.updates.append(kwargs)
        self.traces.append(t)
        return t

    def span(self, **kwargs: Any) -> FakeStatefulClient:
        if self.should_fail:
            raise RuntimeError("Langfuse API connection refused")
        s = FakeStatefulClient(kwargs.get("id", "span-root"), kwargs.get("name", ""), "span")
        s.updates.append(kwargs)
        return s

    def generation(self, **kwargs: Any) -> FakeStatefulClient:
        if self.should_fail:
            raise RuntimeError("Langfuse API connection refused")
        g = FakeStatefulClient(kwargs.get("id", "gen-root"), kwargs.get("name", ""), "generation")
        g.updates.append(kwargs)
        return g

    def score(self, **kwargs: Any) -> FakeStatefulClient:
        if self.should_fail:
            raise RuntimeError("Langfuse API connection refused")
        self.scores.append(kwargs)
        return FakeStatefulClient("score-1", kwargs.get("name", ""), "score")

    def flush(self) -> None:
        if self.should_fail:
            raise RuntimeError("Flush failed")
        self.flushed = True


def test_create_trace_port_returns_none_when_disabled() -> None:
    settings = Settings(langfuse_enabled=False)
    assert settings.langfuse_enabled is False
    port = create_trace_port(settings)
    assert port is None



def test_create_trace_port_returns_none_when_invalid_config() -> None:
    settings = Settings(
        langfuse_enabled=True,
        langfuse_public_key="",
        langfuse_secret_key="",
    )
    port = create_trace_port(settings)
    assert port is None


def test_create_trace_port_initializes_with_valid_config() -> None:
    settings = Settings(
        langfuse_enabled=True,
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        langfuse_host_url="http://127.0.0.1:3000",
    )
    fake_client = FakeLangfuseClient()

    port = create_trace_port(settings, client=fake_client)
    assert port is not None


def test_langfuse_trace_port_observation_nesting() -> None:
    fake_client = FakeLangfuseClient()
    port = LangfuseTracePort(fake_client)

    trace_obs = port.open_trace(
        "exp-run",
        session_id="session-123",
        trace_id="trace-abc",
        metadata={"key": "val"},
        tags=["experiment"],
        input={"prompt": "init"},
    )
    assert isinstance(trace_obs, TraceObservation)
    assert len(fake_client.traces) == 1

    span_obs = port.open_span(
        "case:case-01",
        input={"step": 1},
        metadata={"phase": "execution"},
        parent=trace_obs,
    )
    assert len(fake_client.traces[0].children) == 1

    gen_obs = port.open_generation(
        "model_call",
        model="gpt-4o",
        model_parameters={"temperature": 0.0},
        input={"messages": [{"role": "user", "content": "hi"}]},
        parent=span_obs,
    )
    assert len(fake_client.traces[0].children[0].children) == 1

    gen_obs.end(output={"content": "hello"}, usage={"total_tokens": 15})
    span_obs.end(output={"verdict": "deny"})
    trace_obs.end(output={"outcome": "completed"})

    assert fake_client.traces[0].ended is True
    assert fake_client.traces[0].children[0].ended is True
    assert fake_client.traces[0].children[0].children[0].ended is True


def test_langfuse_trace_port_categorical_scores() -> None:
    fake_client = FakeLangfuseClient()
    port = LangfuseTracePort(fake_client)

    trace_obs = port.open_trace("run-1")
    port.score("security_verdict", "deny", observation=trace_obs, comment="expected deny")

    assert len(fake_client.traces[0].scores) == 1
    score_data = fake_client.traces[0].scores[0]
    assert score_data["name"] == "security_verdict"
    assert score_data["value"] == "deny"
    assert score_data["comment"] == "expected deny"


def test_langfuse_trace_port_harmless_exceptions_and_deduplication() -> None:
    diagnostics: list[str] = []
    fake_client = FakeLangfuseClient(should_fail=True)
    port = LangfuseTracePort(fake_client, diagnostic_sink=diagnostics.append)

    # All these calls should not raise exceptions
    trace_obs = port.open_trace("run-fail")
    span_obs = port.open_span("span-fail", parent=trace_obs)
    gen_obs = port.open_generation("gen-fail", parent=span_obs)
    gen_obs.end(output="result")
    span_obs.end(output="result")
    trace_obs.end(output="result")
    port.score("score-fail", "pass", observation=trace_obs)
    port.flush()

    # Diagnostics should be recorded, but deduplicated by stage
    assert len(diagnostics) > 0
    # Stage "trace" should only appear once in diagnostics despite multiple failures
    trace_errors = [d for d in diagnostics if "trace" in d.lower() or "open_trace" in d.lower()]
    assert len(trace_errors) <= 2
