from __future__ import annotations

import hashlib
import io
import stat
import tarfile
import zipfile
from collections.abc import Awaitable, Callable
from pathlib import PurePosixPath

from gamr_core import CheckedContentFile
from gamr_engine.collector_verification import CollectorFile
from gamr_engine.content_evidence import ContentEvidenceBatch, UploadedContentItem

MAX_FILES = 20
MAX_TEXT_BYTES = 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_ARCHIVE_MEMBERS = 32
MAX_ARCHIVE_MEMBER_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = 4 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
_TEXT_SUFFIXES = {".csv", ".json", ".md", ".markdown", ".txt", ".xml"}
_TEXT_TYPES = {
    "application/json",
    "application/xml",
    "text/csv",
    "text/markdown",
    "text/plain",
    "text/xml",
}


async def prepare_uploaded_content(
    files: list[CollectorFile],
    download: Callable[[CollectorFile], Awaitable[bytes]],
) -> ContentEvidenceBatch:
    checked = [_checked(file) for file in files[:MAX_FILES]]
    if len(files) > MAX_FILES:
        return ContentEvidenceBatch([], checked, True, "too_many_files")
    items: list[UploadedContentItem] = []
    total_text = 0
    incomplete = False
    failure = None
    for index, file in enumerate(files, 1):
        try:
            if file.size > MAX_IMAGE_BYTES:
                raise ValueError("content_file_too_large")
            content = await download(file)
            _validate_download(file, content)
            prepared = _prepare_file(file, content, f"upload-{index:03d}")
        except (OSError, UnicodeError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
            incomplete = True
            failure = failure or str(error) or type(error).__name__
            continue
        except Exception:
            incomplete = True
            failure = failure or "content_download_failed"
            continue
        text_size = sum(len(item.text.encode()) for item in prepared if item.text is not None)
        total_text += text_size
        if total_text > MAX_TEXT_BYTES:
            incomplete = True
            failure = failure or "extracted_text_too_large"
            continue
        items.extend(prepared)
    return ContentEvidenceBatch(items, checked, incomplete, failure)


def _checked(file: CollectorFile) -> CheckedContentFile:
    return CheckedContentFile(
        fileId=file.file_id,
        filename=file.filename,
        contentType=file.content_type,
        size=file.size,
        sha256=file.sha256,
    )


def _validate_download(file: CollectorFile, content: bytes) -> None:
    if len(content) != file.size or hashlib.sha256(content).hexdigest() != file.sha256:
        raise ValueError("collector_file_changed")


def _prepare_file(
    file: CollectorFile, content: bytes, uploaded_item_id: str
) -> list[UploadedContentItem]:
    if _is_archive(file.filename, content):
        return _archive_items(file, content, uploaded_item_id)
    image_type = _image_type(content)
    if image_type is not None:
        _validate_image(content, image_type)
        return [
            UploadedContentItem(
                uploaded_item_id,
                file.file_id,
                image_type,
                "image",
                image=content,
            )
        ]
    if not _is_text(file.filename, file.content_type):
        raise ValueError("unsupported_content_type")
    return [_text_item(uploaded_item_id, file.file_id, file.content_type, content)]


def _archive_items(
    file: CollectorFile, content: bytes, uploaded_item_id: str
) -> list[UploadedContentItem]:
    members = (
        _zip_members(content)
        if zipfile.is_zipfile(io.BytesIO(content))
        else _tar_members(content)
    )
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ValueError("too_many_archive_members")
    extracted_size = sum(len(value) for _, value in members)
    if extracted_size > MAX_ARCHIVE_BYTES:
        raise ValueError("archive_too_large")
    if content and extracted_size / len(content) > MAX_COMPRESSION_RATIO:
        raise ValueError("archive_compression_ratio")
    items: list[UploadedContentItem] = []
    for index, (name, value) in enumerate(members, 1):
        if _is_archive(name, value):
            raise ValueError("nested_archive")
        item_id = f"{uploaded_item_id}-member-{index:03d}"
        image_type = _image_type(value)
        if image_type is not None:
            _validate_image(value, image_type)
            items.append(
                UploadedContentItem(item_id, file.file_id, image_type, "image", image=value)
            )
        elif _is_text(name, "application/octet-stream"):
            items.append(_text_item(item_id, file.file_id, "text/plain", value))
        else:
            raise ValueError("unsupported_archive_member")
    return items


def _zip_members(content: bytes) -> list[tuple[str, bytes]]:
    values: list[tuple[str, bytes]] = []
    extracted_size = 0
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if len(values) >= MAX_ARCHIVE_MEMBERS:
                raise ValueError("too_many_archive_members")
            mode = info.external_attr >> 16
            if info.flag_bits & 0x1 or stat.S_ISLNK(mode) or not _safe_member(info.filename):
                raise ValueError("unsafe_archive_member")
            if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                raise ValueError("archive_member_too_large")
            extracted_size += info.file_size
            if extracted_size > MAX_ARCHIVE_BYTES:
                raise ValueError("archive_too_large")
            if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                raise ValueError("archive_compression_ratio")
            values.append((info.filename, archive.read(info)))
    return values


def _tar_members(content: bytes) -> list[tuple[str, bytes]]:
    values: list[tuple[str, bytes]] = []
    extracted_size = 0
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
        for info in archive.getmembers():
            if info.isdir():
                continue
            if len(values) >= MAX_ARCHIVE_MEMBERS:
                raise ValueError("too_many_archive_members")
            if not info.isfile() or not _safe_member(info.name):
                raise ValueError("unsafe_archive_member")
            if info.size > MAX_ARCHIVE_MEMBER_BYTES:
                raise ValueError("archive_member_too_large")
            extracted_size += info.size
            if extracted_size > MAX_ARCHIVE_BYTES:
                raise ValueError("archive_too_large")
            extracted = archive.extractfile(info)
            if extracted is None:
                raise ValueError("unreadable_archive_member")
            values.append((info.name, extracted.read(MAX_ARCHIVE_MEMBER_BYTES + 1)))
    return values


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def _is_archive(filename: str, content: bytes) -> bool:
    suffix = filename.lower()
    return (
        zipfile.is_zipfile(io.BytesIO(content))
        or content.startswith(b"\x1f\x8b")
        or suffix.endswith((".tar", ".tar.gz", ".tgz", ".zip"))
    )


def _is_text(filename: str, content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in _TEXT_TYPES or PurePosixPath(filename).suffix.lower() in _TEXT_SUFFIXES


def _text_item(
    uploaded_item_id: str, file_id: str, content_type: str, content: bytes
) -> UploadedContentItem:
    if len(content) > MAX_ARCHIVE_MEMBER_BYTES:
        raise ValueError("text_item_too_large")
    text = content.decode("utf-8-sig")
    if "\x00" in text:
        raise ValueError("text_contains_nul")
    return UploadedContentItem(uploaded_item_id, file_id, content_type, "text", text=text)


def _image_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return None


def _validate_image(content: bytes, content_type: str) -> None:
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("image_too_large")
    width, height = _png_size(content) if content_type == "image/png" else _jpeg_size(content)
    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
        raise ValueError("image_dimensions_invalid")


def _png_size(content: bytes) -> tuple[int, int]:
    if len(content) < 24 or content[12:16] != b"IHDR":
        raise ValueError("invalid_png")
    return int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")


def _jpeg_size(content: bytes) -> tuple[int, int]:
    position = 2
    while position + 9 < len(content):
        if content[position] != 0xFF:
            position += 1
            continue
        marker = content[position + 1]
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB}:
            return int.from_bytes(content[position + 5 : position + 7], "big"), int.from_bytes(
                content[position + 7 : position + 9], "big"
            )
        if position + 4 > len(content):
            break
        length = int.from_bytes(content[position + 2 : position + 4], "big")
        position += max(length + 2, 2)
    raise ValueError("invalid_jpeg")
