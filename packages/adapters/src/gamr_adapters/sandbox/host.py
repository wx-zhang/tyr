from __future__ import annotations

import asyncio
import math
import os
import shutil
import signal
import stat
import sys
import tempfile
import uuid
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from resource import RLIMIT_AS, RLIMIT_CPU, RLIMIT_FSIZE, RLIMIT_NPROC, setrlimit

from gamr_engine.ports import (
    MAX_EXECUTION_SECONDS,
    MAX_MEMORY_BYTES,
    MAX_OUTPUT_FILES,
    MAX_OUTPUT_TOTAL_BYTES,
    MAX_PROCESSES,
    MAX_WORKSPACE_BYTES,
    ExecutionResult,
    Sandbox,
    SandboxBusyError,
    SandboxClosedError,
    SandboxEntry,
    SandboxId,
    SandboxInfrastructureError,
    SandboxIsolation,
    SandboxSource,
    SandboxUnknownError,
    SandboxValidationError,
    validate_source,
)

from .attachments import validate_entries
from .process import run_bounded_process


@dataclass
class _Record:
    root: Path
    input_root: Path
    workspace_root: Path
    busy: bool = False
    closed: bool = False
    cleaned: bool = False
    process: asyncio.subprocess.Process | None = None
    execution_task: asyncio.Task[object] | None = None


class HostUnsafeSandbox(Sandbox):
    @property
    def isolation(self) -> SandboxIsolation:
        return "unsafe"

    def __init__(self) -> None:
        warnings.warn(
            "host-unsafe sandboxing is not a security boundary; generated code can access "
            "the host as the current user",
            RuntimeWarning,
            stacklevel=2,
        )
        self._records: dict[SandboxId, _Record] = {}

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        validated = validate_entries(entries)
        root = Path(tempfile.mkdtemp(prefix="gamr-sandbox-"))
        input_root, workspace_root = root / "input", root / "workspace"
        try:
            input_root.mkdir()
            workspace_root.mkdir()
            for entry in validated:
                destination = (input_root / entry.path).resolve()
                if input_root.resolve() not in destination.parents:
                    raise SandboxInfrastructureError("attachment path escaped input root")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(entry.content)
                destination.chmod(0o444)
            for directory in sorted(input_root.rglob("*"), reverse=True):
                if directory.is_dir():
                    directory.chmod(0o555)
            input_root.chmod(0o555)
            workspace_root.chmod(0o700)
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise
        sandbox_id = SandboxId(uuid.uuid4().hex)
        self._records[sandbox_id] = _Record(root, input_root, workspace_root)
        return sandbox_id

    async def execute(self, sandbox_id: SandboxId, source: SandboxSource) -> ExecutionResult:
        record = self._record(sandbox_id)
        if record.busy:
            raise SandboxBusyError("sandbox already has an active execution")
        source_bytes = validate_source(source)
        record.busy = True
        record.execution_task = asyncio.current_task()
        try:
            result, terminal = await self._run(record, source_bytes)
            if terminal:
                record.closed = True
                await self._cleanup(record)
            return result
        except asyncio.CancelledError, SandboxInfrastructureError:
            record.closed = True
            await self._cleanup(record)
            raise
        finally:
            record.process = None
            record.execution_task = None
            record.busy = False

    async def collect_output(
        self, sandbox_id: SandboxId, output_dir: str
    ) -> Sequence[SandboxEntry]:
        record = self._record(sandbox_id)
        if record.busy:
            raise SandboxBusyError("sandbox already has an active execution")
        record.busy = True
        try:
            return self._collect(record, output_dir)
        except SandboxValidationError:
            raise
        except Exception as error:
            record.closed = True
            await self._cleanup(record)
            raise SandboxInfrastructureError("host output collection failed") from error
        finally:
            record.busy = False

    def _collect(self, record: _Record, output_dir: str) -> Sequence[SandboxEntry]:
        _validate_relpath(output_dir)
        target = (record.workspace_root / output_dir).resolve()
        ws_real = record.workspace_root.resolve()
        if not (target == ws_real or ws_real in target.parents):
            raise SandboxValidationError("output path escapes workspace root")
        if not target.exists():
            return ()
        if not target.is_dir():
            raise SandboxValidationError("output path must be a directory")
        entries: list[SandboxEntry] = []
        total_bytes = 0
        for root_str, dirnames, filenames in os.walk(target, followlinks=False):
            dirnames.sort()
            for d in dirnames:
                st = (Path(root_str) / d).lstat()
                if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
                    raise SandboxValidationError("symlink or non-directory in output directory")
                _validate_name(d)
            for f in sorted(filenames):
                fp = Path(root_str) / f
                st = fp.lstat()
                if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                    raise SandboxValidationError("symlink or special file in output directory")
                _validate_name(f)
                if len(entries) >= MAX_OUTPUT_FILES:
                    raise SandboxValidationError("output file limit exceeded")
                if st.st_size > MAX_OUTPUT_TOTAL_BYTES - total_bytes:
                    raise SandboxValidationError("output byte limit exceeded")
                try:
                    content = fp.read_bytes()
                except OSError as error:
                    raise SandboxValidationError("failed to read output file") from error
                if len(content) > MAX_OUTPUT_TOTAL_BYTES - total_bytes:
                    raise SandboxValidationError("output byte limit exceeded")
                rel_path = str(fp.relative_to(target))
                _validate_relpath(rel_path)
                entries.append(SandboxEntry(rel_path, content))
                total_bytes += len(content)
        return tuple(entries)

    async def close(self, sandbox_id: SandboxId) -> None:
        record = self._records.get(sandbox_id)
        if record is None:
            raise SandboxUnknownError("sandbox ID is not known to this process")
        if record.closed:
            return
        record.closed = True
        task = record.execution_task
        if task is not None and task is not asyncio.current_task():
            if not task.done():
                task.cancel()
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                pass
        await self._cleanup(record)

    def _record(self, sandbox_id: SandboxId) -> _Record:
        record = self._records.get(sandbox_id)
        if record is None:
            raise SandboxUnknownError("sandbox ID is not known to this process")
        if record.closed:
            raise SandboxClosedError("sandbox is closed")
        return record

    async def _run(self, record: _Record, source: bytes) -> tuple[ExecutionResult, bool]:
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-B",
                "-u",
                "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=record.workspace_root,
                env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
                start_new_session=True,
                preexec_fn=_set_resource_limits,
            )
        except OSError as error:
            raise SandboxInfrastructureError("host Python process could not start") from error
        record.process = process
        return await run_bounded_process(
            process,
            source,
            timeout=MAX_EXECUTION_SECONDS,
            terminate=lambda: self._terminate(process),
        )

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=1.0)
        except TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()

    async def _cleanup(self, record: _Record) -> None:
        if record.cleaned:
            return
        if record.process is not None:
            await self._terminate(record.process)
        try:
            record.root.chmod(0o700)
            for path in record.root.rglob("*"):
                if not path.is_symlink():
                    path.chmod(0o700 if path.is_dir() else 0o600)
            shutil.rmtree(record.root)
        except OSError as error:
            raise SandboxInfrastructureError("host sandbox cleanup failed") from error
        record.cleaned = True


def _set_resource_limits() -> None:
    limits = (
        (RLIMIT_CPU, (math.ceil(MAX_EXECUTION_SECONDS), math.ceil(MAX_EXECUTION_SECONDS) + 1)),
        (RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES)),
        (RLIMIT_FSIZE, (MAX_WORKSPACE_BYTES, MAX_WORKSPACE_BYTES)),
    )
    if sys.platform == "linux":
        limits += ((RLIMIT_NPROC, (MAX_PROCESSES, MAX_PROCESSES)),)
    for resource, limit in limits:
        try:
            setrlimit(resource, limit)
        except OSError, ValueError:
            pass


def _validate_name(name: str) -> None:
    if not isinstance(name, str):
        raise SandboxValidationError("name must be string")
    try:
        name.encode("utf-8")
    except UnicodeError as error:
        raise SandboxValidationError("invalid UTF-8 in file name") from error
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise SandboxValidationError("invalid characters in file name")


def _validate_relpath(path: str) -> None:
    if not isinstance(path, str):
        raise SandboxValidationError("path must be string")
    try:
        path.encode("utf-8")
    except UnicodeError as error:
        raise SandboxValidationError("invalid UTF-8 in path") from error
    if not path or path.startswith(("/", "\\")) or (len(path) > 1 and path[1] == ":"):
        raise SandboxValidationError("path must be relative")
    if "\x00" in path or "\\" in path:
        raise SandboxValidationError("invalid separator in path")
    components = path.split("/")
    if any(not c or c in {".", ".."} for c in components):
        raise SandboxValidationError("invalid traversal in path")
