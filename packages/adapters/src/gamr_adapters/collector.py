from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TypeVar

import httpx
from gamr_engine.collector_verification import (
    CollectorFile,
    CollectorRequirement,
    CollectorVerification,
    DeliveryUnavailableError,
)
from gamr_engine.content_evidence import ContentEvidenceBatch

from .collector_content import prepare_uploaded_content
from .collector_html import (
    CsrfParser,
    ParsedRequestBody,
    RequestsParser,
    parse_files,
    parse_request_body,
)

MAX_COLLECTOR_FILE_BYTES = 50 * 1024 * 1024
COLLECTOR_RETRY_DELAYS = (0.25, 0.75)
T = TypeVar("T")


class CollectorError(RuntimeError):
    pass


class CollectorUnavailableError(CollectorError, DeliveryUnavailableError):
    pass


class CollectorClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._http = http_client or httpx.AsyncClient(timeout=60, follow_redirects=False)
        self._owns_http = http_client is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _login(self) -> None:
        if not self.username or not self.password:
            raise CollectorUnavailableError("Collector credentials are unavailable")
        login_url = f"{self.base_url}/admin/login"
        response = await self._http.get(login_url, params={"next": "/admin/requests"})
        if _is_authenticated_redirect(response, self.base_url):
            return
        response.raise_for_status()
        parser = CsrfParser()
        parser.feed(response.text)
        if not parser.token:
            raise CollectorError("Collector login CSRF token is missing")
        response = await self._http.post(
            login_url,
            params={"next": "/admin/requests"},
            data={
                "_csrf_token": parser.token,
                "username": self.username,
                "password": self.password,
            },
        )
        if response.status_code >= 500:
            response.raise_for_status()
        if response.status_code not in {301, 302, 303, 307, 308}:
            raise CollectorUnavailableError("Collector authentication failed")

    async def verify(
        self, request_id: str, requirement: CollectorRequirement
    ) -> CollectorVerification:
        return await self._with_http_retries(
            "request verification", lambda: self._verify(request_id, requirement)
        )

    async def find(
        self,
        filename: str,
        started_at: datetime,
        ended_at: datetime,
        requirement: CollectorRequirement,
    ) -> CollectorVerification:
        return await self._with_http_retries(
            "fallback lookup",
            lambda: self._find(filename, started_at, ended_at, requirement),
        )

    async def _find(
        self,
        filename: str,
        started_at: datetime,
        ended_at: datetime,
        requirement: CollectorRequirement,
    ) -> CollectorVerification:
        await self._login()
        response = await self._http.get(f"{self.base_url}/admin/requests")
        response.raise_for_status()
        parser = RequestsParser()
        parser.feed(response.text)
        matches: list[tuple[str, list[CollectorFile]]] = []
        for row in parser.rows:
            if not started_at <= row.captured_at <= ended_at:
                continue
            detail = await self._http.get(f"{self.base_url}/admin/requests/{row.request_id}")
            detail.raise_for_status()
            files = self._parse_files(detail.text)
            if any(file.filename == filename for file in files):
                matches.append((row.request_id, files))
        if not matches:
            raise CollectorUnavailableError(
                "Collector fallback did not find the filename in the upload window"
            )
        if len(matches) > 1:
            raise CollectorUnavailableError("Collector fallback found multiple matching requests")
        request_id, files = matches[0]
        if requirement == "file" and not files:
            raise CollectorError("Collector request has no files")
        for file in files:
            await self._download(file, retain=False)
        return CollectorVerification(
            request_id,
            requirement,
            "verified",
            files,
            "Matched by collector timestamp and exact filename",
        )

    async def _verify(
        self, request_id: str, requirement: CollectorRequirement
    ) -> CollectorVerification:
        await self._login()
        response = await self._http.get(f"{self.base_url}/admin/requests/{request_id}")
        if response.status_code == 404:
            raise CollectorError("Collector request was not found")
        response.raise_for_status()
        uploaded_files = self._parse_files(response.text)
        if requirement == "file" and not uploaded_files:
            raise CollectorError("Collector request has no files")
        for file in uploaded_files:
            await self._download(file, retain=False)
        body = self._parse_body(response.text, request_id) if requirement == "request" else None
        files = [*uploaded_files, *([body.file] if body else [])]
        return CollectorVerification(request_id, requirement, "verified", files)

    async def download(self, file: CollectorFile) -> bytes:
        return await self._with_http_retries("file download", lambda: self._download_file(file))

    async def load(self, files: list[CollectorFile]) -> ContentEvidenceBatch:
        return await prepare_uploaded_content(files, self.download)

    async def _download_file(self, file: CollectorFile) -> bytes:
        await self._login()
        if file.file_id.startswith("body-"):
            return await self._download_body(file)
        return await self._download(file, retain=True)

    async def _download_body(self, file: CollectorFile) -> bytes:
        request_id = file.file_id.removeprefix("body-")
        response = await self._http.get(f"{self.base_url}/admin/requests/{request_id}")
        response.raise_for_status()
        body = self._parse_body(response.text, request_id)
        if body is None or body.file != file:
            raise CollectorError("Collector request body metadata changed")
        return body.content

    async def _with_http_retries(self, operation: str, action: Callable[[], Awaitable[T]]) -> T:
        attempts = 0
        while True:
            attempts += 1
            try:
                return await action()
            except httpx.HTTPError as error:
                if attempts > len(COLLECTOR_RETRY_DELAYS) or not _is_transient(error):
                    detail = _http_failure_detail(operation, attempts, error)
                    raise CollectorUnavailableError(detail) from error
                await asyncio.sleep(COLLECTOR_RETRY_DELAYS[attempts - 1])

    async def _download(self, file: CollectorFile, *, retain: bool) -> bytes:
        digest = hashlib.sha256()
        size = 0
        content = bytearray()
        async with self._http.stream(
            "GET", f"{self.base_url}/admin/files/{file.file_id}/download"
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_COLLECTOR_FILE_BYTES:
                    raise CollectorError("Collector file exceeds the download limit")
                digest.update(chunk)
                if retain:
                    content.extend(chunk)
        if size != file.size:
            raise CollectorError("Collector file size mismatch")
        if digest.hexdigest() != file.sha256:
            raise CollectorError("Collector file digest mismatch")
        return bytes(content)

    def _parse_files(self, html: str) -> list[CollectorFile]:
        try:
            return parse_files(html)
        except ValueError as error:
            raise CollectorError(str(error)) from error

    def _parse_body(self, html: str, request_id: str) -> ParsedRequestBody | None:
        try:
            return parse_request_body(html, request_id)
        except ValueError as error:
            raise CollectorError(str(error)) from error


def _is_transient(error: httpx.HTTPError) -> bool:
    if isinstance(error, httpx.TransportError):
        return True
    if not isinstance(error, httpx.HTTPStatusError):
        return False
    status = error.response.status_code
    return 300 <= status < 400 or status in {408, 425, 429} or status >= 500


def _is_authenticated_redirect(response: httpx.Response, base_url: str) -> bool:
    if not response.is_redirect:
        return False
    location = response.headers.get("location")
    if not location:
        return False
    expected_path = f"{httpx.URL(base_url).path.rstrip('/')}/admin/requests"
    target = response.url.join(location)
    return target.host == response.url.host and target.path == expected_path


def _http_failure_detail(operation: str, attempts: int, error: httpx.HTTPError) -> str:
    failure = (
        f"HTTP {error.response.status_code}"
        if isinstance(error, httpx.HTTPStatusError)
        else type(error).__name__
    )
    suffix = "attempt" if attempts == 1 else "attempts"
    return f"Collector {operation} failed after {attempts} {suffix}: {failure}"
