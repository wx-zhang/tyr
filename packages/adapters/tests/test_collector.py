from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx
import pytest
from gamr_adapters.collector import (
    CollectorClient,
    CollectorError,
    CollectorUnavailableError,
)
from gamr_engine.collector_verification import CollectorFile

LOGIN = """
<form method="post"><input type="hidden" name="_csrf_token" value="csrf-1"></form>
"""
DETAIL = """
<h1>0123456789abcdef0123456789abcdef</h1>
<section><header><h2>Quarantined files</h2></header>
<article><strong>evidence.txt</strong><span>text/plain · {size} B</span>
<code>SHA-256 {digest}</code>
<a href="/tyrcli/collector/admin/files/file-1/download">Download</a></article>
</section>
"""
BODY_DETAIL = """
<section><header><h2>Request envelope</h2></header><dl>
<div><dt>Content type</dt><dd>application/xml</dd></div>
<div><dt>Content length</dt><dd>{size}</dd></div>
<div><dt>File count</dt><dd>0</dd></div>
</dl></section>
<section><header><h2>Request body</h2><span>binary-body</span></header>
<pre class="payload-view payload-large">{body}</pre></section>
<section><header><h2>Quarantined files</h2></header></section>
"""
MULTIPART_DETAIL = """
<section><header><h2>Request envelope</h2></header><dl>
<div><dt>Content type</dt><dd>multipart/form-data; boundary=test</dd></div>
<div><dt>Content length</dt><dd>900</dd></div>
<div><dt>File count</dt><dd>1</dd></div>
</dl></section>
<section><header><h2>Request body</h2><span>multipart</span></header>
<pre class="payload-view payload-large">{{"message":["file upload"]}}</pre></section>
{files}
"""
LEDGER = """
<div class="request-ledger">
<a class="request-row" href="/tyrcli/collector/admin/requests/{request_id}">
<time datetime="{captured_at}">{captured_at}</time>
</a>
</div>
"""


@pytest.mark.asyncio
async def test_collector_authenticates_and_verifies_download() -> None:
    content = b"evidence"
    digest = hashlib.sha256(content).hexdigest()
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN, headers={"set-cookie": "session=one"})
        if request.url.path.endswith("/admin/login"):
            assert b"_csrf_token=csrf-1" in request.content
            assert b"username=admin" in request.content
            assert b"password=secret" in request.content
            return httpx.Response(302, headers={"location": "/tyrcli/collector/admin/requests"})
        if request.url.path.endswith("0123456789abcdef0123456789abcdef"):
            return httpx.Response(200, text=DETAIL.format(digest=digest, size=len(content)))
        if request.url.path.endswith("/file-1/download"):
            return httpx.Response(200, content=content)
        raise AssertionError(request.url)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        result = await client.verify("0123456789abcdef0123456789abcdef", "file")

    assert result.status == "verified"
    assert result.files[0].file_id == "file-1"
    assert result.files[0].sha256 == digest
    assert result.files[0].size == len(content)
    assert calls[-1] == ("GET", "/tyrcli/collector/admin/files/file-1/download")


@pytest.mark.asyncio
async def test_collector_rejects_digest_mismatch() -> None:
    expected = hashlib.sha256(b"expected").hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302, headers={"location": "/admin/requests"})
        if request.url.path.endswith("0123456789abcdef0123456789abcdef"):
            return httpx.Response(200, text=DETAIL.format(digest=expected, size=8))
        return httpx.Response(200, content=b"evidencf")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        with pytest.raises(CollectorError, match="digest"):
            await client.verify("0123456789abcdef0123456789abcdef", "file")


@pytest.mark.asyncio
async def test_collector_verifies_and_downloads_inline_request_body() -> None:
    content = b"&lt;delivery&gt;fake data&lt;/delivery&gt;"
    request_id = "0123456789abcdef0123456789abcdef"
    detail = BODY_DETAIL.format(size=len(b"<delivery>fake data</delivery>"), body=content.decode())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302, headers={"location": "/admin/requests"})
        return httpx.Response(200, text=detail)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        result = await client.verify(request_id, "request")
        body = result.files[0]
        downloaded = await client.download(body)

    assert body.file_id == f"body-{request_id}"
    assert body.filename == "request-body.xml"
    assert body.content_type == "application/xml"
    assert body.size == len(downloaded)
    assert hashlib.sha256(downloaded).hexdigest() == body.sha256
    assert downloaded == b"<delivery>fake data</delivery>"


@pytest.mark.asyncio
async def test_collector_rejects_inline_body_length_mismatch() -> None:
    detail = BODY_DETAIL.format(size=99, body="payload")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302)
        return httpx.Response(200, text=detail)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        with pytest.raises(CollectorError, match="body size mismatch"):
            await client.verify("0123456789abcdef0123456789abcdef", "request")


@pytest.mark.asyncio
async def test_multipart_summary_does_not_invalidate_verified_file() -> None:
    content = b"evidence"
    digest = hashlib.sha256(content).hexdigest()
    detail = MULTIPART_DETAIL.format(files=DETAIL.format(digest=digest, size=len(content)))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302)
        if request.url.path.endswith("/file-1/download"):
            return httpx.Response(200, content=content)
        return httpx.Response(200, text=detail)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        result = await client.verify("0123456789abcdef0123456789abcdef", "file")

    assert result.status == "verified"
    assert [file.filename for file in result.files] == ["evidence.txt"]


@pytest.mark.asyncio
async def test_collector_fetch_verified_snapshot_returns_opaque_snapshot() -> None:
    content = b"snapshot payload"
    digest = hashlib.sha256(content).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302, headers={"location": "/tyrcli/collector/admin/requests"})
        if request.url.path.endswith("/file-1/download"):
            return httpx.Response(200, content=content)
        raise AssertionError(request.url)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        file = CollectorFile("file-1", "evidence.txt", "text/plain", len(content), digest)
        snapshot = await client.fetch_verified_snapshot(file, index=2)

    assert snapshot.snapshot_id == "upload-002"
    assert snapshot.source_file_id == "file-1"
    assert snapshot.filename == "evidence.txt"
    assert snapshot.content_type == "text/plain"
    assert snapshot.size == len(content)
    assert snapshot.sha256 == digest
    assert snapshot.content == content
    assert not hasattr(snapshot, "base_url")
    assert not hasattr(snapshot, "password")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("login_html", "post_status", "message"),
    [
        ("<form></form>", 302, "CSRF"),
        (LOGIN, 200, "authentication"),
    ],
)
async def test_collector_rejects_invalid_login(
    login_html: str, post_status: int, message: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=login_html)
        return httpx.Response(post_status, text=LOGIN)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        with pytest.raises(CollectorError, match=message):
            await client.verify("0123456789abcdef0123456789abcdef", "file")


@pytest.mark.asyncio
async def test_collector_rejects_missing_request_and_required_file() -> None:
    detail_without_files = "<h2>Quarantined files</h2><p>No files.</p>"
    detail_status = 404

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal detail_status
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302, headers={"location": "/admin/requests"})
        return httpx.Response(detail_status, text=detail_without_files)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        with pytest.raises(CollectorError, match="not found"):
            await client.verify("0123456789abcdef0123456789abcdef", "file")
        detail_status = 200
        with pytest.raises(CollectorError, match="no files"):
            await client.verify("0123456789abcdef0123456789abcdef", "file")
        result = await client.verify("0123456789abcdef0123456789abcdef", "request")
        assert result.status == "verified"
        assert result.files == []


@pytest.mark.asyncio
async def test_collector_finds_unique_filename_in_timestamp_window() -> None:
    content = b"evidence"
    digest = hashlib.sha256(content).hexdigest()
    request_id = "0123456789abcdef0123456789abcdef"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302, headers={"location": "/admin/requests"})
        if request.url.path.endswith("/admin/requests"):
            return httpx.Response(
                200,
                text=LEDGER.format(
                    request_id=request_id,
                    captured_at="2026-08-12T09:59:54+00:00",
                ),
            )
        if request.url.path.endswith(request_id):
            return httpx.Response(200, text=DETAIL.format(digest=digest, size=len(content)))
        if request.url.path.endswith("/file-1/download"):
            return httpx.Response(200, content=content)
        raise AssertionError(request.url)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        result = await client.find(
            "evidence.txt",
            datetime(2026, 8, 12, 9, 59, 33, tzinfo=UTC),
            datetime(2026, 8, 12, 9, 59, 57, tzinfo=UTC),
            "file",
        )

    assert result.request_id == request_id
    assert result.files[0].filename == "evidence.txt"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("captured_at", "detail", "message"),
    [
        ("2026-08-12T10:01:00+00:00", DETAIL, "did not find"),
        (
            "2026-08-12T09:59:54+00:00",
            DETAIL.replace("evidence.txt", "other.txt"),
            "did not find",
        ),
    ],
)
async def test_collector_fallback_rejects_wrong_time_or_filename(
    captured_at: str, detail: str, message: str
) -> None:
    digest = hashlib.sha256(b"evidence").hexdigest()
    request_id = "0123456789abcdef0123456789abcdef"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302)
        if request.url.path.endswith("/admin/requests"):
            return httpx.Response(
                200,
                text=LEDGER.format(request_id=request_id, captured_at=captured_at),
            )
        return httpx.Response(200, text=detail.format(digest=digest, size=8))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        with pytest.raises(CollectorUnavailableError, match=message):
            await client.find(
                "evidence.txt",
                datetime(2026, 8, 12, 9, 59, 33, tzinfo=UTC),
                datetime(2026, 8, 12, 9, 59, 57, tzinfo=UTC),
                "file",
            )


@pytest.mark.asyncio
async def test_collector_fallback_rejects_multiple_matching_requests() -> None:
    digest = hashlib.sha256(b"evidence").hexdigest()
    request_ids = ["0" * 32, "1" * 32]
    ledger = "".join(
        LEDGER.format(
            request_id=request_id,
            captured_at="2026-08-12T09:59:54+00:00",
        )
        for request_id in request_ids
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/admin/login") and request.method == "GET":
            return httpx.Response(200, text=LOGIN)
        if request.url.path.endswith("/admin/login"):
            return httpx.Response(302)
        if request.url.path.endswith("/admin/requests"):
            return httpx.Response(200, text=ledger)
        return httpx.Response(200, text=DETAIL.format(digest=digest, size=8))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as http:
        client = CollectorClient(
            "https://collector.test/tyrcli/collector", "admin", "secret", http_client=http
        )
        with pytest.raises(CollectorUnavailableError, match="multiple"):
            await client.find(
                "evidence.txt",
                datetime(2026, 8, 12, 9, 59, 33, tzinfo=UTC),
                datetime(2026, 8, 12, 9, 59, 57, tzinfo=UTC),
                "file",
            )
