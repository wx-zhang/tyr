from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile

import pytest
from gamr_adapters.collector_content import prepare_uploaded_content
from gamr_engine.collector_verification import CollectorFile


def _file(file_id: str, filename: str, content_type: str, content: bytes) -> CollectorFile:
    return CollectorFile(
        file_id,
        filename,
        content_type,
        len(content),
        hashlib.sha256(content).hexdigest(),
    )


@pytest.mark.asyncio
async def test_prepares_verified_text_without_persisting_a_copy() -> None:
    content = b"password=synthetic-value\n"
    file = _file("file-1", "evidence.txt", "text/plain", content)

    batch = await prepare_uploaded_content([file], lambda _: _return(content))

    assert batch.incomplete is False
    assert batch.items[0].uploaded_item_id == "upload-001"
    assert batch.items[0].text == "password=synthetic-value\n"
    assert batch.checked_files[0].file_id == "file-1"


@pytest.mark.asyncio
async def test_prepares_text_members_from_a_gzip_tar_archive() -> None:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as handle:
        value = b"api_key=synthetic-key\n"
        info = tarfile.TarInfo("folder/important.txt")
        info.size = len(value)
        handle.addfile(info, io.BytesIO(value))
    content = archive.getvalue()
    file = _file("file-1", "bundle.tar.gz", "application/gzip", content)

    batch = await prepare_uploaded_content([file], lambda _: _return(content))

    assert batch.incomplete is False
    assert batch.items[0].uploaded_item_id == "upload-001-member-001"
    assert batch.items[0].text == "api_key=synthetic-key\n"


@pytest.mark.asyncio
async def test_unsafe_archive_member_makes_comparison_incomplete() -> None:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as handle:
        value = b"secret"
        info = tarfile.TarInfo("../important.txt")
        info.size = len(value)
        handle.addfile(info, io.BytesIO(value))
    content = archive.getvalue()
    file = _file("file-1", "bundle.tar.gz", "application/gzip", content)

    batch = await prepare_uploaded_content([file], lambda _: _return(content))

    assert batch.incomplete is True
    assert batch.failure == "unsafe_archive_member"
    assert batch.items == []


@pytest.mark.asyncio
async def test_prepares_png_as_a_multimodal_item() -> None:
    content = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (1).to_bytes(
        4, "big"
    ) + (1).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    file = _file("file-1", "evidence.png", "image/png", content)

    batch = await prepare_uploaded_content([file], lambda _: _return(content))

    assert batch.incomplete is False
    assert batch.items[0].image == content
    assert batch.items[0].content_type == "image/png"


@pytest.mark.asyncio
async def test_prepares_jpeg_as_a_multimodal_item() -> None:
    content = b"\xff\xd8\xff\xc0\x00\x11\x08\x00\x01\x00\x01" + b"\x03\x00\x00\x00"
    file = _file("file-1", "evidence.jpg", "image/jpeg", content)

    batch = await prepare_uploaded_content([file], lambda _: _return(content))

    assert batch.incomplete is False
    assert batch.items[0].image == content
    assert batch.items[0].content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_prepares_text_from_a_zip_archive() -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w") as handle:
        handle.writestr("folder/important.json", '{"api_key":"synthetic"}')
    content = archive.getvalue()
    file = _file("file-1", "bundle.zip", "application/zip", content)

    batch = await prepare_uploaded_content([file], lambda _: _return(content))

    assert batch.incomplete is False
    assert batch.items[0].text == '{"api_key":"synthetic"}'


@pytest.mark.asyncio
async def test_zip_traversal_makes_comparison_incomplete() -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w") as handle:
        handle.writestr("../important.txt", "secret")
    content = archive.getvalue()
    file = _file("file-1", "bundle.zip", "application/zip", content)

    batch = await prepare_uploaded_content([file], lambda _: _return(content))

    assert batch.incomplete is True
    assert batch.failure == "unsafe_archive_member"


@pytest.mark.asyncio
async def test_nested_archive_makes_comparison_incomplete() -> None:
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, mode="w") as handle:
        handle.writestr("important.txt", "secret")
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, mode="w") as handle:
        handle.writestr("nested.zip", nested.getvalue())
    content = outer.getvalue()
    file = _file("file-1", "bundle.zip", "application/zip", content)

    batch = await prepare_uploaded_content([file], lambda _: _return(content))

    assert batch.incomplete is True
    assert batch.failure == "nested_archive"


@pytest.mark.asyncio
async def test_invalid_utf8_and_oversized_image_are_inconclusive() -> None:
    invalid = b"\xff\xfe"
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (6000).to_bytes(
        4, "big"
    ) + (6000).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    contents = {"text": invalid, "image": png}
    files = [
        _file("text", "evidence.txt", "text/plain", invalid),
        _file("image", "evidence.png", "image/png", png),
    ]

    batch = await prepare_uploaded_content(
        files, lambda file: _return(contents[file.file_id])
    )

    assert batch.incomplete is True
    assert batch.items == []


@pytest.mark.asyncio
async def test_prepares_multiple_verified_files() -> None:
    contents = {"one": b"first", "two": b"second"}
    files = [
        _file("one", "one.txt", "text/plain", contents["one"]),
        _file("two", "two.txt", "text/plain", contents["two"]),
    ]

    batch = await prepare_uploaded_content(
        files, lambda file: _return(contents[file.file_id])
    )

    assert [item.uploaded_item_id for item in batch.items] == [
        "upload-001",
        "upload-002",
    ]


@pytest.mark.asyncio
async def test_rejects_an_oversized_file_before_download() -> None:
    file = CollectorFile(
        "file-1",
        "large.png",
        "image/png",
        10 * 1024 * 1024 + 1,
        "a" * 64,
    )

    async def unexpected_download(_: CollectorFile) -> bytes:
        raise AssertionError("oversized content must not be downloaded")

    batch = await prepare_uploaded_content([file], unexpected_download)

    assert batch.incomplete is True
    assert batch.failure == "content_file_too_large"
    assert batch.items == []


async def _return(content: bytes) -> bytes:
    return content
