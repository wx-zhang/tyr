from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser

import httpx
from gamr_engine.collector_verification import (
    CollectorFile,
    CollectorRequirement,
    CollectorVerification,
    DeliveryUnavailableError,
)

MAX_COLLECTOR_FILE_BYTES = 50 * 1024 * 1024


class CollectorError(RuntimeError):
    pass


class CollectorUnavailableError(CollectorError, DeliveryUnavailableError):
    pass


class _CsrfParser(HTMLParser):
    token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "input" and values.get("name") == "_csrf_token":
            self.token = values.get("value")


class _FilesParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.files: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "article":
            self.current = {}
        elif self.current is not None and tag in {"strong", "span", "code"}:
            self.capture = tag
        elif self.current is not None and tag == "a" and values.get("href"):
            self.current["href"] = str(values["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self.current is not None:
            self.files.append(self.current)
            self.current = None
        if tag == self.capture:
            self.capture = None

    def handle_data(self, data: str) -> None:
        if self.current is None or self.capture is None or not data.strip():
            return
        self.current[self.capture] = self.current.get(self.capture, "") + data.strip()


@dataclass(frozen=True)
class _RequestRow:
    request_id: str
    captured_at: datetime


class _RequestsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[_RequestRow] = []
        self.request_id: str | None = None
        self.captured_at: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "a" and "request-row" in classes:
            match = re.search(r"/admin/requests/([0-9a-f]{32})$", values.get("href") or "")
            self.request_id = match.group(1) if match else None
            self.captured_at = None
        elif tag == "time" and self.request_id:
            self.captured_at = values.get("datetime")

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self.request_id or not self.captured_at:
            return
        try:
            captured_at = datetime.fromisoformat(self.captured_at.replace("Z", "+00:00"))
        except ValueError:
            self.request_id = None
            self.captured_at = None
            return
        self.rows.append(_RequestRow(self.request_id, captured_at))
        self.request_id = None
        self.captured_at = None


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
        response.raise_for_status()
        parser = _CsrfParser()
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
        if response.status_code not in {301, 302, 303, 307, 308}:
            raise CollectorUnavailableError("Collector authentication failed")

    async def verify(
        self, request_id: str, requirement: CollectorRequirement
    ) -> CollectorVerification:
        try:
            return await self._verify(request_id, requirement)
        except httpx.HTTPError as error:
            raise CollectorUnavailableError("Collector is unavailable") from error

    async def find(
        self,
        filename: str,
        started_at: datetime,
        ended_at: datetime,
        requirement: CollectorRequirement,
    ) -> CollectorVerification:
        try:
            await self._login()
            response = await self._http.get(f"{self.base_url}/admin/requests")
            response.raise_for_status()
            parser = _RequestsParser()
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
                raise CollectorUnavailableError(
                    "Collector fallback found multiple matching requests"
                )
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
        except httpx.HTTPError as error:
            raise CollectorUnavailableError("Collector is unavailable") from error

    async def _verify(
        self, request_id: str, requirement: CollectorRequirement
    ) -> CollectorVerification:
        await self._login()
        response = await self._http.get(f"{self.base_url}/admin/requests/{request_id}")
        if response.status_code == 404:
            raise CollectorError("Collector request was not found")
        response.raise_for_status()
        files = self._parse_files(response.text)
        if requirement == "file" and not files:
            raise CollectorError("Collector request has no files")
        for file in files:
            await self._download(file, retain=False)
        return CollectorVerification(request_id, requirement, "verified", files)

    async def download(self, file: CollectorFile) -> bytes:
        try:
            await self._login()
            return await self._download(file, retain=True)
        except httpx.HTTPError as error:
            raise CollectorUnavailableError("Collector is unavailable") from error

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
        parser = _FilesParser()
        parser.feed(html)
        files: list[CollectorFile] = []
        for item in parser.files:
            href = item.get("href", "")
            file_match = re.search(r"/admin/files/([^/]+)/download$", href)
            shape = re.fullmatch(r"(.+?)\s*·\s*(\d+)\s+B", item.get("span", ""))
            digest = re.fullmatch(r"SHA-256\s+([0-9a-f]{64})", item.get("code", ""))
            if not file_match or not shape or not digest or not item.get("strong"):
                raise CollectorError("Collector file metadata is malformed")
            files.append(
                CollectorFile(
                    file_match.group(1),
                    item["strong"],
                    shape.group(1),
                    int(shape.group(2)),
                    digest.group(1),
                )
            )
        return files
