from __future__ import annotations

from collections.abc import Callable
from typing import Any

from gamr_engine.ports.tracing import TraceObservation, TracePort

from gamr_adapters.config import Settings

from .tracing_diagnostics import DiagnosticReporter
from .tracing_observation import LangfuseObservation

__all__ = [
    "DiagnosticReporter",
    "LangfuseObservation",
    "LangfuseTracePort",
    "create_trace_port",
]


class LangfuseTracePort:
    def __init__(
        self,
        client: Any,
        *,
        diagnostic_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._client = client
        self._reporter = DiagnosticReporter(diagnostic_sink)

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
        try:
            if hasattr(self._client, "start_observation"):
                from langfuse.types import TraceContext

                clean_tid = trace_id.replace("-", "") if trace_id else None
                trace_ctx = TraceContext(trace_id=clean_tid) if clean_tid else None
                meta = dict(metadata or {})
                if session_id is not None:
                    meta["sessionId"] = session_id
                if tags is not None:
                    meta["tags"] = tags
                trace_client = self._client.start_observation(
                    name=name,
                    as_type="span",
                    input=input,
                    output=output,
                    metadata=meta if meta else None,
                    trace_context=trace_ctx,
                )
                return LangfuseObservation(name, "trace", trace_client, self._reporter)


            kwargs: dict[str, Any] = {"name": name}
            if session_id is not None:
                kwargs["session_id"] = session_id
            if trace_id is not None:
                kwargs["id"] = trace_id
            if metadata:
                kwargs["metadata"] = metadata
            if tags:
                kwargs["tags"] = tags
            if input is not None:
                kwargs["input"] = input
            if output is not None:
                kwargs["output"] = output
            trace_client = self._client.trace(**kwargs)
            return LangfuseObservation(name, "trace", trace_client, self._reporter)
        except Exception as exc:
            self._reporter.report("open_trace", str(exc), name)
            return LangfuseObservation(name, "trace", None, self._reporter)

    def open_span(
        self,
        name: str,
        *,
        metadata: dict[str, object] | None = None,
        input: object = None,
        output: object = None,
        parent: TraceObservation | None = None,
    ) -> TraceObservation:
        try:
            parent_client = (
                parent._client if isinstance(parent, LangfuseObservation) else None
            )
            target = parent_client or self._client
            if target is not None and hasattr(target, "start_observation"):
                span_client = target.start_observation(
                    name=name,
                    as_type="span",
                    input=input,
                    output=output,
                    metadata=metadata,
                )
                return LangfuseObservation(name, "span", span_client, self._reporter)

            kwargs: dict[str, Any] = {"name": name}
            if metadata:
                kwargs["metadata"] = metadata
            if input is not None:
                kwargs["input"] = input
            if output is not None:
                kwargs["output"] = output
            if parent_client is not None and hasattr(parent_client, "span"):
                span_client = parent_client.span(**kwargs)
            else:
                span_client = self._client.span(**kwargs)
            return LangfuseObservation(name, "span", span_client, self._reporter)
        except Exception as exc:
            self._reporter.report("open_span", str(exc), name)
            return LangfuseObservation(name, "span", None, self._reporter)

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
        try:
            parent_client = (
                parent._client if isinstance(parent, LangfuseObservation) else None
            )
            target = parent_client or self._client
            if target is not None and hasattr(target, "start_observation"):
                usage_details = (
                    {
                        k: int(v)
                        for k, v in usage.items()
                        if isinstance(v, (int, float))
                    }
                    if usage
                    else None
                )
                gen_client = target.start_observation(
                    name=name,
                    as_type="generation",
                    model=model,
                    model_parameters=model_parameters,
                    input=input,
                    output=output,
                    metadata=metadata,
                    usage_details=usage_details,
                )
                return LangfuseObservation(name, "generation", gen_client, self._reporter)

            kwargs: dict[str, Any] = {"name": name}
            if model is not None:
                kwargs["model"] = model
            if model_parameters:
                kwargs["model_parameters"] = model_parameters
            if input is not None:
                kwargs["input"] = input
            if output is not None:
                kwargs["output"] = output
            if usage:
                kwargs["usage"] = usage
            if metadata:
                kwargs["metadata"] = metadata
            if parent_client is not None and hasattr(parent_client, "generation"):
                gen_client = parent_client.generation(**kwargs)
            else:
                gen_client = self._client.generation(**kwargs)
            return LangfuseObservation(name, "generation", gen_client, self._reporter)
        except Exception as exc:
            self._reporter.report("open_generation", str(exc), name)
            return LangfuseObservation(name, "generation", None, self._reporter)

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        observation: TraceObservation | None = None,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        try:
            if isinstance(observation, LangfuseObservation) and observation._client is not None:
                observation.score(name, value, comment=comment, metadata=metadata)
                return
            kwargs: dict[str, Any] = {"name": name, "value": value}
            if isinstance(value, str):
                kwargs["data_type"] = "CATEGORICAL"
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                kwargs["data_type"] = "NUMERIC"
            elif isinstance(value, bool):
                kwargs["data_type"] = "BOOLEAN"
            if comment is not None:
                kwargs["comment"] = comment
            if metadata:
                kwargs["metadata"] = metadata
            if hasattr(self._client, "create_score"):
                self._client.create_score(**kwargs)
            elif hasattr(self._client, "score"):
                self._client.score(**kwargs)
        except Exception as exc:
            self._reporter.report("score", str(exc), name)

    def flush(self, timeout: float | None = None) -> None:
        try:
            if hasattr(self._client, "flush"):
                self._client.flush()
        except Exception as exc:
            self._reporter.report("flush", str(exc), "process_flush")



def create_trace_port(
    settings: Settings | None = None,
    *,
    client: Any = None,
    diagnostic_sink: Callable[[str], None] | None = None,
) -> TracePort | None:
    if client is not None:
        return LangfuseTracePort(client, diagnostic_sink=diagnostic_sink)
    if settings is None or not getattr(settings, "is_langfuse_valid", False):
        return None
    try:
        from langfuse import Langfuse

        sdk_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host_url,
            release=getattr(settings, "langfuse_environment", None)
            or getattr(settings, "environment", "development"),
        )
        return LangfuseTracePort(sdk_client, diagnostic_sink=diagnostic_sink)
    except Exception as exc:
        if diagnostic_sink is not None:
            diagnostic_sink(f"[Langfuse Tracing] init: {exc}")
        return None
