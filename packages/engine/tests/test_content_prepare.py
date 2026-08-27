from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile

from gamr_engine.collector_verification import CollectorFile
from gamr_engine.content_prepare import (
    DerivedContentSnapshot,
    prepare_content_evidence,
    prepare_derived_content_evidence,
)
from gamr_engine.content_source import VerifiedContentSnapshot


def _file(file_id: str, filename: str, content_type: str, content: bytes) -> CollectorFile:
    return CollectorFile(
        file_id=file_id,
        filename=filename,
        content_type=content_type,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _snapshot(
    snapshot_id: str,
    file_id: str,
    filename: str,
    content_type: str,
    content: bytes,
) -> VerifiedContentSnapshot:
    return VerifiedContentSnapshot(
        snapshot_id=snapshot_id,
        source_file_id=file_id,
        filename=filename,
        content_type=content_type,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
    )


# --- Tests for Original Verified Snapshots ---


def test_prepare_verified_text_snapshot() -> None:
    content = b"password=synthetic-value\n"
    file = _file("file-1", "evidence.txt", "text/plain", content)
    snapshot = _snapshot("upload-001", file.file_id, file.filename, file.content_type, content)

    batch = prepare_content_evidence([file], [snapshot])

    assert batch.incomplete is False
    assert len(batch.items) == 1
    assert batch.items[0].uploaded_item_id == "upload-001"
    assert batch.items[0].file_id == "file-1"
    assert batch.items[0].text == "password=synthetic-value\n"
    assert batch.checked_files[0].file_id == "file-1"


def test_prepare_tar_archive_snapshot() -> None:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as handle:
        value = b"api_key=synthetic-key\n"
        info = tarfile.TarInfo("folder/important.txt")
        info.size = len(value)
        handle.addfile(info, io.BytesIO(value))
    content = archive.getvalue()
    file = _file("file-1", "bundle.tar.gz", "application/gzip", content)
    snapshot = _snapshot("upload-001", file.file_id, file.filename, file.content_type, content)

    batch = prepare_content_evidence([file], [snapshot])

    assert batch.incomplete is False
    assert batch.items[0].uploaded_item_id == "upload-001-member-001"
    assert batch.items[0].text == "api_key=synthetic-key\n"


def test_prepare_unsafe_tar_snapshot_fails() -> None:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as handle:
        value = b"secret"
        info = tarfile.TarInfo("../important.txt")
        info.size = len(value)
        handle.addfile(info, io.BytesIO(value))
    content = archive.getvalue()
    file = _file("file-1", "bundle.tar.gz", "application/gzip", content)
    snapshot = _snapshot("upload-001", file.file_id, file.filename, file.content_type, content)

    batch = prepare_content_evidence([file], [snapshot])

    assert batch.incomplete is True
    assert batch.failure == "unsafe_archive_member"
    assert batch.items == []


def test_prepare_png_snapshot() -> None:
    content = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + (1).to_bytes(4, "big")
        + (1).to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )
    file = _file("file-1", "evidence.png", "image/png", content)
    snapshot = _snapshot("upload-001", file.file_id, file.filename, file.content_type, content)

    batch = prepare_content_evidence([file], [snapshot])

    assert batch.incomplete is False
    assert batch.items[0].image == content
    assert batch.items[0].content_type == "image/png"


# --- Tests for Derived Sandbox Outputs ---


def test_prepare_derived_content_preserves_lineage_and_assigns_new_item_ids() -> None:
    file = _file("file-1", "evidence.enc", "application/octet-stream", b"encrypted")
    # Output path relative to attempt root: <source_id>/<relative_path>
    derived_snapshots = [
        DerivedContentSnapshot(
            relative_path="upload-001/decoded.txt",
            content=b"decrypted text content\n",
        )
    ]
    # Source mapping: upload-001 -> CollectorFile (file-1)
    source_map = {"upload-001": file}

    batch = prepare_derived_content_evidence([file], source_map, derived_snapshots)

    assert batch.incomplete is False
    assert len(batch.items) == 1
    assert batch.items[0].uploaded_item_id == "upload-001-derived-001"
    assert batch.items[0].file_id == "file-1"
    assert batch.items[0].text == "decrypted text content\n"
    assert batch.items[0].kind == "text"


def test_prepare_derived_content_empty_output_fails_closed() -> None:
    file = _file("file-1", "evidence.enc", "application/octet-stream", b"encrypted")
    source_map = {"upload-001": file}

    batch = prepare_derived_content_evidence([file], source_map, [])

    assert batch.incomplete is True
    assert batch.failure == "empty_derived_output"
    assert batch.items == []


def test_prepare_derived_content_unknown_source_dir_fails_closed() -> None:
    file = _file("file-1", "evidence.enc", "application/octet-stream", b"encrypted")
    source_map = {"upload-001": file}
    derived_snapshots = [
        DerivedContentSnapshot(
            relative_path="upload-999/decoded.txt",  # Unknown source directory
            content=b"some content\n",
        )
    ]

    batch = prepare_derived_content_evidence([file], source_map, derived_snapshots)

    assert batch.incomplete is True
    assert batch.failure == "unknown_source_directory"
    assert batch.items == []


def test_prepare_derived_content_unsafe_path_fails_closed() -> None:
    file = _file("file-1", "evidence.enc", "application/octet-stream", b"encrypted")
    source_map = {"upload-001": file}
    derived_snapshots = [
        DerivedContentSnapshot(
            relative_path="upload-001/../escaped.txt",
            content=b"escaped content\n",
        )
    ]

    batch = prepare_derived_content_evidence([file], source_map, derived_snapshots)

    assert batch.incomplete is True
    assert batch.failure in {"unsafe_derived_path", "unknown_source_directory"}
    assert batch.items == []


def test_prepare_derived_content_nested_archive_fails_closed() -> None:
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, mode="w") as handle:
        handle.writestr("inner.txt", "content")
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, mode="w") as handle:
        handle.writestr("nested.zip", nested.getvalue())
    content = outer.getvalue()

    file = _file("file-1", "evidence.enc", "application/octet-stream", b"encrypted")
    source_map = {"upload-001": file}
    derived_snapshots = [
        DerivedContentSnapshot(
            relative_path="upload-001/bundle.zip",
            content=content,
        )
    ]

    batch = prepare_derived_content_evidence([file], source_map, derived_snapshots)

    assert batch.incomplete is True
    assert batch.failure == "nested_archive"
    assert batch.items == []


# --- Regression Tests for Task 2.4 ---


def test_prepare_unsupported_content_type_fails_closed() -> None:
    file = _file("file-1", "binary.bin", "application/octet-stream", b"\x00\x01\x02\x03")
    snapshot = _snapshot(
        "upload-001", file.file_id, file.filename, file.content_type, b"\x00\x01\x02\x03"
    )

    batch = prepare_content_evidence([file], [snapshot])

    assert batch.incomplete is True
    assert batch.failure == "unsupported_content_type"
    assert batch.items == []


def test_prepare_incomplete_batch_missing_snapshot() -> None:
    file1 = _file("file-1", "one.txt", "text/plain", b"one")
    file2 = _file("file-2", "two.txt", "text/plain", b"two")
    snapshot1 = _snapshot("upload-001", file1.file_id, file1.filename, file1.content_type, b"one")

    # snapshot for file2 is missing
    batch = prepare_content_evidence([file1, file2], [snapshot1])

    assert batch.incomplete is True
    assert batch.failure == "content_download_failed"
    assert len(batch.items) == 1
    assert batch.items[0].uploaded_item_id == "upload-001"


def test_prepare_changed_download_content_fails_closed() -> None:
    file = _file("file-1", "evidence.txt", "text/plain", b"original")
    # Snapshot content differs from CollectorFile size/digest
    snapshot = _snapshot(
        "upload-001", file.file_id, file.filename, file.content_type, b"tampered content"
    )

    batch = prepare_content_evidence([file], [snapshot])

    assert batch.incomplete is True
    assert batch.failure == "collector_file_changed"
    assert batch.items == []


def test_prepare_derived_decompression_ratio_limit_fails_closed() -> None:
    # Test archive compression ratio limit on derived output
    data = b"0" * (100 * 1024)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("large.txt", data)
    compressed = archive.getvalue()

    file = _file("file-1", "evidence.enc", "application/octet-stream", b"encrypted")
    source_map = {"upload-001": file}
    derived_snapshots = [
        DerivedContentSnapshot(
            relative_path="upload-001/bomb.zip",
            content=compressed,
        )
    ]

    batch = prepare_derived_content_evidence([file], source_map, derived_snapshots)
    # The ratio of 100KB repetitive string is very high (> 100)
    assert batch.incomplete is True
    assert batch.failure == "archive_compression_ratio"
    assert batch.items == []
