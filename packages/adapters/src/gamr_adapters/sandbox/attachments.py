from __future__ import annotations

import os
import stat
from collections.abc import Iterable, Sequence
from pathlib import Path

from gamr_engine.ports import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENT_FILES,
    SandboxEntry,
    SandboxValidationError,
)


def validate_entries(entries: Iterable[SandboxEntry]) -> tuple[SandboxEntry, ...]:
    validated = tuple(entries)
    if len(validated) > MAX_ATTACHMENT_FILES:
        raise SandboxValidationError(f"attachments exceed {MAX_ATTACHMENT_FILES} files")
    total_bytes = 0
    paths: list[str] = []
    for entry in validated:
        if not isinstance(entry, SandboxEntry) or not isinstance(entry.content, bytes):
            raise SandboxValidationError("attachments must contain byte entries")
        validate_path(entry.path)
        total_bytes += len(entry.content)
        if total_bytes > MAX_ATTACHMENT_BYTES:
            raise SandboxValidationError(f"attachments exceed {MAX_ATTACHMENT_BYTES} bytes")
        paths.append(entry.path)
    if len(paths) != len(set(paths)):
        raise SandboxValidationError("attachment destinations must be unique")
    path_set = set(paths)
    for path in paths:
        if any(ancestor in path_set for ancestor in _ancestors(path)):
            raise SandboxValidationError("attachment destinations cannot overlap")
    return tuple(sorted(validated, key=lambda entry: entry.path))






def snapshot_attachments(
    roots: Sequence[str | os.PathLike[str] | Path],
) -> tuple[SandboxEntry, ...]:
    entries: list[SandboxEntry] = []
    total_bytes = 0
    try:
        for root_value in roots:
            root = Path(root_value)
            root_stat = root.lstat()
            root_name = _validate_component(root.name)
            if stat.S_ISREG(root_stat.st_mode):
                total_bytes = _append_file(root, root_name, entries, total_bytes, root_stat.st_size)
            elif stat.S_ISDIR(root_stat.st_mode):
                total_bytes = _walk_directory(root, root_name, entries, total_bytes)
            else:
                raise SandboxValidationError("attachments must be regular files or directories")
    except SandboxValidationError:
        raise
    except (OSError, UnicodeError) as error:
        raise SandboxValidationError("attachment snapshot failed") from error
    return validate_entries(entries)


def _walk_directory(
    directory: Path, logical_root: str, entries: list[SandboxEntry], total_bytes: int
) -> int:
    try:
        with os.scandir(directory) as iterator:
            children = sorted(iterator, key=lambda entry: entry.name)
    except OSError as error:
        raise SandboxValidationError("attachment directory cannot be read") from error
    for child in children:
        component = _validate_component(child.name)
        child_path = Path(child.path)
        try:
            child_stat = child.stat(follow_symlinks=False)
        except OSError as error:
            raise SandboxValidationError("attachment entry cannot be inspected") from error
        logical_path = f"{logical_root}/{component}"
        if stat.S_ISREG(child_stat.st_mode):
            total_bytes = _append_file(
                child_path, logical_path, entries, total_bytes, child_stat.st_size
            )
        elif stat.S_ISDIR(child_stat.st_mode):
            total_bytes = _walk_directory(child_path, logical_path, entries, total_bytes)
        else:
            raise SandboxValidationError("attachments cannot contain symlinks or special files")
    return total_bytes


def _append_file(
    path: Path,
    logical_path: str,
    entries: list[SandboxEntry],
    total_bytes: int,
    size: int | None = None,
) -> int:
    if len(entries) >= MAX_ATTACHMENT_FILES:
        raise SandboxValidationError(f"attachments exceed {MAX_ATTACHMENT_FILES} files")
    if size is not None and size > MAX_ATTACHMENT_BYTES - total_bytes:
        raise SandboxValidationError(f"attachments exceed {MAX_ATTACHMENT_BYTES} bytes")
    try:
        content = path.read_bytes()
    except (OSError, UnicodeError) as error:
        raise SandboxValidationError("attachment source cannot be read") from error
    if len(content) > MAX_ATTACHMENT_BYTES - total_bytes:
        raise SandboxValidationError(f"attachments exceed {MAX_ATTACHMENT_BYTES} bytes")
    entries.append(SandboxEntry(logical_path, content))
    return total_bytes + len(content)



def validate_path(path: str) -> None:
    if not isinstance(path, str):
        raise SandboxValidationError("attachment paths must be text")
    try:
        path.encode("utf-8")
    except UnicodeError as error:
        raise SandboxValidationError("attachment paths must be valid UTF-8") from error
    if not path or path.startswith(("/", "\\")) or (len(path) > 1 and path[1] == ":"):
        raise SandboxValidationError("attachment paths must be relative")
    if "\x00" in path or "\\" in path:
        raise SandboxValidationError("attachment paths contain an invalid separator")
    components = path.split("/")
    if any(not component or component in {".", ".."} for component in components):
        raise SandboxValidationError("attachment paths contain an invalid component")


def _validate_component(component: str) -> str:
    validate_path(component)
    return component



def _ancestors(path: str) -> Iterable[str]:
    components = path.split("/")
    return ("/".join(components[:index]) for index in range(1, len(components)))
