from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser

from gamr_engine.collector_verification import CollectorFile


class CsrfParser(HTMLParser):
    token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "input" and values.get("name") == "_csrf_token":
            self.token = values.get("value")


class FilesParser(HTMLParser):
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
class RequestRow:
    request_id: str
    captured_at: datetime


class RequestsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[RequestRow] = []
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
        self.rows.append(RequestRow(self.request_id, captured_at))
        self.request_id = None
        self.captured_at = None


def parse_files(html: str) -> list[CollectorFile]:
    parser = FilesParser()
    parser.feed(html)
    files: list[CollectorFile] = []
    for item in parser.files:
        file_match = re.search(r"/admin/files/([^/]+)/download$", item.get("href", ""))
        shape = re.fullmatch(r"(.+?)\s*·\s*(\d+)\s+B", item.get("span", ""))
        digest = re.fullmatch(r"SHA-256\s+([0-9a-f]{64})", item.get("code", ""))
        if not file_match or not shape or not digest or not item.get("strong"):
            raise ValueError("Collector file metadata is malformed")
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
