from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol, runtime_checkable

_current_observation: contextvars.ContextVar[TraceObservation | None] = contextvars.ContextVar(
    "gamr_trace_current_observation", default=None
)


@runtime_checkable
class TraceObservation(Protocol):
    name: str
    kind: str

    def update(
        self,
        *,
        output: object = None,
        metadata: dict[str, object] | None = None,
        usage: dict[str, object] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None: ...

    def end(
        self,
        *,
        output: object = None,
        metadata: dict[str, object] | None = None,
        usage: dict[str, object] | None = None,
        error: Exception | str | None = None,
    ) -> None: ...

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None: ...


@runtime_checkable
class TracePort(Protocol):
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
    ) -> TraceObservation: ...

    def open_span(
        self,
        name: str,
        *,
        metadata: dict[str, object] | None = None,
        input: object = None,
        output: object = None,
        parent: TraceObservation | None = None,
    ) -> TraceObservation: ...

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
    ) -> TraceObservation: ...

    def score(
        self,
        name: str,
        value: str | float | int,
        *,
        observation: TraceObservation | None = None,
        comment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None: ...

    def flush(self, timeout: float | None = None) -> None: ...


def current_observation() -> TraceObservation | None:
    return _current_observation.get()


@contextmanager
def trace_run(
    port: TracePort | None,
    name: str,
    *,
    session_id: str | None = None,
    trace_id: str | None = None,
    metadata: dict[str, object] | None = None,
    tags: list[str] | None = None,
    input: object = None,
) -> Iterator[TraceObservation | None]:
    if port is None:
        yield None
        return
    obs: TraceObservation | None = None
    try:
        obs = port.open_trace(
            name,
            session_id=session_id,
            trace_id=trace_id,
            metadata=metadata,
            tags=tags,
            input=input,
        )
    except Exception:
        obs = None
    if obs is None:
        yield None
        return
    token = _current_observation.set(obs)
    try:
        yield obs
    except Exception as exc:
        try:
            obs.end(error=exc)
        except Exception:
            pass
        raise
    else:
        try:
            obs.end()
        except Exception:
            pass
    finally:
        _current_observation.reset(token)


@contextmanager
def trace_span(
    port: TracePort | None,
    name: str,
    *,
    input: object = None,
    metadata: dict[str, object] | None = None,
    parent: TraceObservation | None = None,
) -> Iterator[TraceObservation | None]:
    if port is None:
        yield None
        return
    obs: TraceObservation | None = None
    try:
        effective_parent = parent if parent is not None else _current_observation.get()
        obs = port.open_span(
            name,
            metadata=metadata,
            input=input,
            parent=effective_parent,
        )
    except Exception:
        obs = None
    if obs is None:
        yield None
        return
    token = _current_observation.set(obs)
    try:
        yield obs
    except Exception as exc:
        try:
            obs.end(error=exc)
        except Exception:
            pass
        raise
    else:
        try:
            obs.end()
        except Exception:
            pass
    finally:
        _current_observation.reset(token)


@contextmanager
def trace_generation(
    port: TracePort | None,
    name: str,
    *,
    model: str | None = None,
    model_parameters: dict[str, object] | None = None,
    input: object = None,
    metadata: dict[str, object] | None = None,
    parent: TraceObservation | None = None,
) -> Iterator[TraceObservation | None]:
    if port is None:
        yield None
        return
    obs: TraceObservation | None = None
    try:
        effective_parent = parent if parent is not None else _current_observation.get()
        obs = port.open_generation(
            name,
            model=model,
            model_parameters=model_parameters,
            input=input,
            metadata=metadata,
            parent=effective_parent,
        )
    except Exception:
        obs = None
    if obs is None:
        yield None
        return
    token = _current_observation.set(obs)
    try:
        yield obs
    except Exception as exc:
        try:
            obs.end(error=exc)
        except Exception:
            pass
        raise
    else:
        try:
            obs.end()
        except Exception:
            pass
    finally:
        _current_observation.reset(token)


def trace_score(
    port: TracePort | None,
    name: str,
    value: str | float | int,
    *,
    observation: TraceObservation | None = None,
    comment: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    if port is None:
        return
    try:
        target_obs = observation if observation is not None else _current_observation.get()
        port.score(name, value, observation=target_obs, comment=comment, metadata=metadata)
    except Exception:
        pass
