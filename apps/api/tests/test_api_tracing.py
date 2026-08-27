from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from gamr_api.main import create_app


class FakeTracePort:
    def __init__(self) -> None:
        self.flushed = False

    def flush(self, timeout: float | None = None) -> None:
        self.flushed = True


def test_api_lifespan_flushes_trace_port(monkeypatch: pytest.MonkeyPatch) -> None:
    port = FakeTracePort()
    import gamr_api.main as api_main

    monkeypatch.setattr(api_main, "create_trace_port", lambda _s: port)

    app = create_app()
    with TestClient(app):
        assert port.flushed is False

    assert port.flushed is True
