from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from gamr_adapters.sandbox import attachments as attachments_module
from gamr_adapters.sandbox.attachments import snapshot_attachments, validate_entries
from gamr_engine.ports import SandboxEntry, SandboxValidationError


def test_snapshot_repeats_roots_and_preserves_directory_names(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    first.write_bytes(b"one")
    tree = tmp_path / "tree"
    (tree / "nested").mkdir(parents=True)
    (tree / "nested" / "second.txt").write_bytes(b"two")

    entries = snapshot_attachments([first, tree])

    assert [(entry.path, entry.content) for entry in entries] == [
        ("first.txt", b"one"),
        ("tree/nested/second.txt", b"two"),
    ]


@pytest.mark.parametrize(
    "paths",
    [
        lambda root: [root / "same.txt", root / "same.txt"],
        lambda root: [root / "a", root / "a"],
    ],
)
def test_snapshot_rejects_duplicate_and_ancestor_conflicts(
    tmp_path: Path, paths: object
) -> None:
    (tmp_path / "same.txt").write_bytes(b"one")
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b.txt").write_bytes(b"two")

    with pytest.raises(SandboxValidationError):
        snapshot_attachments(paths(tmp_path))  # type: ignore[operator]


def test_snapshot_rejects_symlinks_and_special_files(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_bytes(b"target")
    (tmp_path / "link.txt").symlink_to(target)

    with pytest.raises(SandboxValidationError):
        snapshot_attachments([tmp_path])

    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    with pytest.raises(SandboxValidationError):
        snapshot_attachments([fifo])


def test_snapshot_enforces_count_and_byte_limits(tmp_path: Path) -> None:
    files = []
    for index in range(257):
        path = tmp_path / f"file-{index}.txt"
        path.write_bytes(b"x")
        files.append(path)

    with pytest.raises(SandboxValidationError):
        snapshot_attachments(files)

    large = tmp_path / "large.bin"
    with large.open("wb") as handle:
        handle.truncate(64 * 1024 * 1024 + 1)
    with pytest.raises(SandboxValidationError):
        snapshot_attachments([large])


def test_snapshot_enforces_aggregate_bytes_across_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(attachments_module, "MAX_ATTACHMENT_BYTES", 3)
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_bytes(b"12")
    second.write_bytes(b"34")

    with pytest.raises(SandboxValidationError):
        snapshot_attachments([first, second])


def test_validate_entries_rejects_unsafe_paths_and_conflicts() -> None:
    invalid = ("", "/absolute", "a/../b", "a//b", "a\\b", "a\x00b")
    for path in invalid:
        with pytest.raises(SandboxValidationError):
            validate_entries([SandboxEntry(path, b"x")])

    with pytest.raises(SandboxValidationError):
        validate_entries([SandboxEntry("a", b"x"), SandboxEntry("a/b", b"y")])


def test_validate_entries_rejects_invalid_names_and_limits() -> None:
    with pytest.raises(SandboxValidationError):
        validate_entries([SandboxEntry("\udcff", b"x")])
    with pytest.raises(SandboxValidationError):
        validate_entries([SandboxEntry("a", b"x") for _ in range(257)])


def test_snapshot_rejects_source_read_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"source")

    def fail(_: Path) -> bytes:
        raise OSError("read failed")

    monkeypatch.setattr(Path, "read_bytes", fail)
    with pytest.raises(SandboxValidationError):
        snapshot_attachments([source])


def test_snapshot_rejects_invalid_file_type(tmp_path: Path) -> None:
    directory = tmp_path / "directory"
    directory.mkdir()
    mode = directory.stat().st_mode
    assert stat.S_ISDIR(mode)
    with pytest.raises(SandboxValidationError):
        snapshot_attachments([directory / "missing"])
