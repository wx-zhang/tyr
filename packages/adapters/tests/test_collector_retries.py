from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from gamr_adapters.collector import CollectorClient, CollectorUnavailableError
from gamr_engine.collector_verification import CollectorFile, CollectorVerification

LOGIN = '<input type="hidden" name="_csrf_token" value="csrf-1">'
REQUEST_ID = "0123456789abcdef0123456789abcdef"
CAPTURED_AT = "2026-08-12T09:59:54+00:00"
LEDGER = f"""
<a class="request-row" href="/tyrcli/collector/admin/requests/{REQUEST_ID}">
<time datetime="{CAPTURED_AT}">{CAPTURED_AT}</time></a>
"""


def _detail(content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()
    return f"""
    <article><strong>evidence.txt</strong><span>text/plain · {len(content)} B</span>
    <code>SHA-256 {digest}</code>
    <a href="/tyrcli/collector/admin/files/file-1/download">Download</a></article>
    """


async def _find(client: CollectorClient) -> CollectorVerification:
    return await client.find(
        "evidence.txt",
        datetime(2026, 8, 12, 9, 59, 33, tzinfo=UTC),
        datetime(2026, 8, 12, 9, 59, 57, tzinfo=UTC),
        "file",
    )


@pytest.mark.asyncio
async def test_collector_retries_transient_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"evidence"
    ledger_attempts = 0
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal ledger_attempts
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302)
        if request.url.path.endswith("/admin/requests"):
            ledger_attempts += 1
            return httpx.Response(503 if ledger_attempts == 1 else 200, text=LEDGER)
        if request.url.path.endswith(REQUEST_ID):
            return httpx.Response(200, text=_detail(content))
        return httpx.Response(200, content=content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await _find(
            CollectorClient(
                "https://collector.test/tyrcli/collector",
                "admin",
                "secret",
                http_client=http,
            )
        )

    assert result.status == "verified"
    assert ledger_attempts == 2
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_collector_reauthenticates_after_lookup_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"evidence"
    ledger_attempts = 0
    login_attempts = 0
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal ledger_attempts, login_attempts
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            login_attempts += 1
            return httpx.Response(302)
        if request.url.path.endswith("/admin/requests"):
            ledger_attempts += 1
            if ledger_attempts == 1:
                return httpx.Response(302, headers={"location": "/admin/login"})
            return httpx.Response(200, text=LEDGER)
        if request.url.path.endswith(REQUEST_ID):
            return httpx.Response(200, text=_detail(content))
        return httpx.Response(200, content=content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await _find(
            CollectorClient(
                "https://collector.test/tyrcli/collector",
                "admin",
                "secret",
                http_client=http,
            )
        )

    assert result.status == "verified"
    assert ledger_attempts == 2
    assert login_attempts == 2
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_collector_reauthenticates_after_download_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"evidence"
    download_attempts = 0
    login_attempts = 0
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal download_attempts, login_attempts
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            login_attempts += 1
            return httpx.Response(302)
        download_attempts += 1
        if download_attempts == 1:
            return httpx.Response(302, headers={"location": "/admin/login"})
        return httpx.Response(200, content=content)

    file = CollectorFile(
        "file-1",
        "evidence.txt",
        "text/plain",
        len(content),
        hashlib.sha256(content).hexdigest(),
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        downloaded = await client.download(file)

    assert downloaded == content
    assert download_attempts == 2
    assert login_attempts == 2
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_collector_accepts_login_redirect_for_authenticated_session() -> None:
    content = b"evidence"
    login_gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_gets
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            login_gets += 1
            if login_gets == 1:
                return httpx.Response(200, text=LOGIN)
            return httpx.Response(
                302,
                headers={"location": "/tyrcli/collector/admin/requests"},
            )
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302)
        if request.url.path.endswith("/admin/requests"):
            return httpx.Response(200, text=LEDGER)
        if request.url.path.endswith(REQUEST_ID):
            return httpx.Response(200, text=_detail(content))
        return httpx.Response(200, content=content)

    file = CollectorFile(
        "file-1",
        "evidence.txt",
        "text/plain",
        len(content),
        hashlib.sha256(content).hexdigest(),
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        await _find(client)
        downloaded = await client.download(file)

    assert downloaded == content
    assert login_gets == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "attempts"), [(302, 3), (503, 3), (400, 1)])
async def test_collector_reports_safe_http_failure_details(
    monkeypatch: pytest.MonkeyPatch, status: int, attempts: int
) -> None:
    ledger_attempts = 0
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal ledger_attempts
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302)
        ledger_attempts += 1
        return httpx.Response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        with pytest.raises(
            CollectorUnavailableError,
            match=rf"fallback lookup failed after {attempts} attempt.*HTTP {status}",
        ):
            await _find(client)

    assert ledger_attempts == attempts


@pytest.mark.asyncio
async def test_collector_reports_transport_error_type_without_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger_attempts = 0
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal ledger_attempts
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302)
        ledger_attempts += 1
        raise httpx.ConnectError("sensitive upstream detail", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        with pytest.raises(CollectorUnavailableError) as raised:
            await _find(client)

    assert str(raised.value) == ("Collector fallback lookup failed after 3 attempts: ConnectError")
    assert "sensitive" not in str(raised.value)
    assert ledger_attempts == 3
