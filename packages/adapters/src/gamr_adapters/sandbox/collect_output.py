from __future__ import annotations

import io
import os
import stat
import sys
import tarfile
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gamr_engine.ports import SandboxEntry

MAX_OUTPUT_FILES = 256
MAX_OUTPUT_TOTAL_BYTES = 64 * 1024 * 1024
WORKSPACE_ROOT = "/workspace"


def main() -> None:
    if len(sys.argv) < 2:
        raise ValueError("missing target directory argument")
    target_rel = sys.argv[1]
    if not _safe_relpath(target_rel):
        raise ValueError("invalid relative output directory path")
    target_abs = os.path.normpath(os.path.join(WORKSPACE_ROOT, target_rel))
    workspace_real = os.path.realpath(WORKSPACE_ROOT)
    if not (target_abs == workspace_real or target_abs.startswith(workspace_real + "/")):
        raise ValueError("output directory escapes workspace root")
    if not os.path.lexists(target_abs):
        archive = _empty_archive()
        sys.stdout.buffer.write(archive)
        return
    st = os.lstat(target_abs)
    if not stat.S_ISDIR(st.st_mode):
        raise ValueError("output target must be a directory")
    files: list[tuple[str, bytes]] = []
    total_bytes = 0
    for root, dirnames, filenames in os.walk(target_abs, followlinks=False):
        dirnames.sort()
        for d in dirnames:
            dp = os.path.join(root, d)
            dst = os.lstat(dp)
            if not stat.S_ISDIR(dst.st_mode) or stat.S_ISLNK(dst.st_mode):
                raise ValueError("output tree contains symlinks or non-directory in traversal")
            if not _safe_name(d):
                raise ValueError("invalid UTF-8 or unsafe directory name")
        for f in sorted(filenames):
            fp = os.path.join(root, f)
            fst = os.lstat(fp)
            if stat.S_ISLNK(fst.st_mode) or not stat.S_ISREG(fst.st_mode):
                raise ValueError("output tree contains symlink or special file")
            if not _safe_name(f):
                raise ValueError("invalid UTF-8 or unsafe file name")
            if len(files) >= MAX_OUTPUT_FILES:
                raise ValueError("output file count limit exceeded")
            if fst.st_size > MAX_OUTPUT_TOTAL_BYTES - total_bytes:
                raise ValueError("output byte limit exceeded")
            with open(fp, "rb") as handle:
                content = handle.read()
            if len(content) > MAX_OUTPUT_TOTAL_BYTES - total_bytes:
                raise ValueError("output byte limit exceeded")
            rel_to_target = os.path.relpath(fp, target_abs)
            if not _safe_relpath(rel_to_target):
                raise ValueError("unsafe output relative path")
            files.append((rel_to_target, content))
            total_bytes += len(content)
    archive = _build_archive(files)
    sys.stdout.buffer.write(archive)


def _safe_name(name: str) -> bool:
    if not isinstance(name, str):
        return False
    try:
        name.encode("utf-8")
    except UnicodeError:
        return False
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        return False
    return True


def _safe_relpath(path: str) -> bool:
    if not isinstance(path, str):
        return False
    try:
        path.encode("utf-8")
    except UnicodeError:
        return False
    if not path or path.startswith(("/", "\\")) or (len(path) > 1 and path[1] == ":"):
        return False
    if "\x00" in path or "\\" in path:
        return False
    components = path.split("/")
    return not any(not c or c in {".", ".."} for c in components)


def _empty_archive() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as _:
        pass
    return output.getvalue()


def _build_archive(files: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for rel_path, content in files:
            info = tarfile.TarInfo(name=rel_path)
            info.size = len(content)
            info.mode = 0o444
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def parse_collected_output(archive_bytes: bytes) -> Sequence[SandboxEntry]:
    from gamr_engine.ports import SandboxEntry, SandboxValidationError

    if not archive_bytes:
        return ()
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
            entries: list[SandboxEntry] = []
            total_bytes = 0
            for member in archive.getmembers():
                if not member.isreg():
                    raise SandboxValidationError("archive contains symlink or special file")
                if not _safe_relpath(member.name):
                    raise SandboxValidationError("archive contains unsafe path")
                if len(entries) >= MAX_OUTPUT_FILES:
                    raise SandboxValidationError("output file count limit exceeded")
                if member.size > MAX_OUTPUT_TOTAL_BYTES - total_bytes:
                    raise SandboxValidationError("output byte limit exceeded")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise SandboxValidationError("archive entry cannot be read")
                content = extracted.read()
                if len(content) > MAX_OUTPUT_TOTAL_BYTES - total_bytes:
                    raise SandboxValidationError("output byte limit exceeded")
                entries.append(SandboxEntry(member.name, content))
                total_bytes += len(content)
            return tuple(sorted(entries, key=lambda e: e.path))
    except SandboxValidationError:
        raise
    except Exception as error:
        raise SandboxValidationError("failed to parse output archive") from error


if __name__ == "__main__":
    main()
