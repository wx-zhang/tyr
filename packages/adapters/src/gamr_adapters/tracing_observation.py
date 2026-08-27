from __future__ import annotations

from typing import Any

from .tracing_diagnostics import DiagnosticReporter


class LangfuseObservation:
    def __init__(
        self,
        name: str,
        kind: str,
        client: Any | None,
        reporter: DiagnosticReporter,
    ) -> None:
        self.name = name
        self.kind = kind
        self._client = client
        self._reporter = reporter

    def update(
        self,
        *,
        output: object = None,
        metadata: dict[str, object] | None = None,
        usage: dict[str, object] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        if self._client is None:
            return
        try:
            kwargs: dict[str, Any] = {}
            if output is not None:
                kwargs["output"] = output
            if metadata:
                kwargs["metadata"] = metadata
            if self.kind == "generation" and usage:
                usage_details = {
                    k: int(v) for k, v in usage.items() if isinstance(v, (int, float))
                }
                kwargs["usage_details"] = usage_details
                kwargs["usage"] = usage
            if self.kind in ("span", "generation"):
                if level:
                    kwargs["level"] = level
                if status_message:
                    kwargs["status_message"] = status_message
            if hasattr(self._client, "update"):
                try:
                    self._client.update(**kwargs)
                except TypeError:
                    kwargs.pop("usage", None)
                    self._client.update(**kwargs)
        except Exception as exc:
            self._reporter.report("observation_update", str(exc), self.name)

    def end(
        self,
        *,
        output: object = None,
        metadata: dict[str, object] | None = None,
        usage: dict[str, object] | None = None,
        error: Exception | str | None = None,
    ) -> None:
        if self._client is None:
            return
        try:
            self.update(
                output=output,
                metadata=metadata,
                usage=usage,
                level="ERROR" if error is not None else None,
                status_message=str(error) if error is not None else None,
            )
            if hasattr(self._client, "end"):
                try:
                    self._client.end()
                except TypeError:
                    kwargs: dict[str, Any] = {}
                    if output is not None:
                        kwargs["output"] = output
                    self._client.end(**kwargs)
        except Exception as exc:
            self._reporter.report("observation_end", str(exc), self.name)

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if self._client is None:
            return
        try:
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
            if hasattr(self._client, "score"):
                self._client.score(**kwargs)
        except Exception as exc:
            self._reporter.report("observation_score", str(exc), name)
