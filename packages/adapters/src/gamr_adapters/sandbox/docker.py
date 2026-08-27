from __future__ import annotations

import asyncio
import io
import tarfile
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from gamr_engine.ports import (
    MAX_EXECUTION_SECONDS,
    MAX_MEMORY_BYTES,
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
    SandboxUnavailableError,
    SandboxUnknownError,
    SandboxValidationError,
    validate_source,
)

from .attachments import validate_entries
from .collect_output import parse_collected_output
from .process import run_bounded_process

IMAGE_TAG = "gamr-sandbox:python3.14-stdlib"
LABEL_KEY = "com.tyr.gamr.sandbox"
LABEL_ID_KEY = f"{LABEL_KEY}.id"


def build_volume_create_args(volume: str, public_id: str) -> tuple[str, ...]:
    return (
        "volume",
        "create",
        "--label",
        f"{LABEL_KEY}=true",
        "--label",
        f"{LABEL_ID_KEY}={public_id}",
        volume,
    )


def build_populate_args(volume: str, public_id: str) -> tuple[str, ...]:
    return (
        "run",
        "--interactive",
        "--rm",
        "--network",
        "none",
        "--label",
        f"{LABEL_KEY}=true",
        "--label",
        f"{LABEL_ID_KEY}={public_id}",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "65532:65532",
        "--volume",
        f"{volume}:/input:rw",
        IMAGE_TAG,
        "/usr/local/bin/python",
        "/opt/gamr/populate_input.py",
    )


def build_container_create_args(container: str, volume: str, public_id: str) -> tuple[str, ...]:
    mem = f"{MAX_MEMORY_BYTES // (1024 * 1024)}m"
    mount = (
        f"/workspace:rw,noexec,nosuid,nodev,size={MAX_WORKSPACE_BYTES},uid=65532,gid=65532,mode=700"
    )
    return (
        "create",
        "--name",
        container,
        "--label",
        f"{LABEL_KEY}=true",
        "--label",
        f"{LABEL_ID_KEY}={public_id}",
        "--network",
        "none",
        "--restart",
        "no",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--cpus",
        "1",
        "--memory",
        mem,
        "--memory-swap",
        mem,
        "--pids-limit",
        str(MAX_PROCESSES),
        "--volume",
        f"{volume}:/input:ro",
        "--tmpfs",
        mount,
        "--env",
        "PYTHONNOUSERSITE=1",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--user",
        "65532:65532",
        "--workdir",
        "/workspace",
        IMAGE_TAG,
        "/usr/local/bin/python",
        "-c",
        "import time; time.sleep(315360000)",
    )


def build_execute_args(container: str) -> tuple[str, ...]:
    return (
        "exec",
        "--interactive",
        "--user",
        "65532:65532",
        "--workdir",
        "/workspace",
        container,
        "/usr/local/bin/python",
        "-I",
        "-B",
        "-u",
        "-",
    )


def build_collect_output_args(container: str, output_dir: str) -> tuple[str, ...]:
    return (
        "exec",
        "--user",
        "65532:65532",
        "--workdir",
        "/workspace",
        container,
        "/usr/local/bin/python",
        "-I",
        "-B",
        "-u",
        "/opt/gamr/collect_output.py",
        output_dir,
    )


def build_input_archive(entries: Sequence[SandboxEntry]) -> bytes:
    validated = validate_entries(entries)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for entry in validated:
            info = tarfile.TarInfo(entry.path)
            info.size = len(entry.content)
            info.mode = 0o444
            info.mtime = 0
            archive.addfile(info, io.BytesIO(entry.content))
    return output.getvalue()


@dataclass
class _Record:
    public_id: SandboxId
    volume: str
    container: str
    busy: bool = False
    closed: bool = False
    cleaned: bool = False
    resources_removed: bool = False
    process: asyncio.subprocess.Process | None = None
    execution_task: asyncio.Task[object] | None = None


@dataclass(frozen=True)
class _DockerResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class DockerSandbox(Sandbox):
    @property
    def isolation(self) -> SandboxIsolation:
        return "contained"

    def __init__(self) -> None:
        self._records: dict[SandboxId, _Record] = {}

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        validated = validate_entries(entries)
        archive = build_input_archive(validated)
        public_id = SandboxId(uuid.uuid4().hex)
        priv = uuid.uuid4().hex
        volume, container = f"gamr-sandbox-volume-{priv}", f"gamr-sandbox-container-{priv}"
        volume_created, container_created = False, False
        try:
            await self._success(build_volume_create_args(volume, public_id))
            volume_created = True
            await self._success(build_populate_args(volume, str(public_id)), archive)
            await self._success(build_container_create_args(container, volume, public_id))
            container_created = True
            await self._success(("start", container))
        except SandboxUnavailableError, Exception:
            await self._remove_resources(container, volume, container_created, volume_created)
            raise
        record = _Record(public_id, volume, container)
        self._records[public_id] = record
        return public_id

    async def execute(self, sandbox_id: SandboxId, source: SandboxSource) -> ExecutionResult:
        record = self._record(sandbox_id)
        if record.busy:
            raise SandboxBusyError("sandbox already has an active execution")
        source_bytes = validate_source(source)
        record.busy = True
        record.execution_task = asyncio.current_task()
        try:
            process = await self._docker_process(build_execute_args(record.container))
            record.process = process
            result, terminal = await run_bounded_process(
                process,
                source_bytes,
                timeout=MAX_EXECUTION_SECONDS,
                terminate=lambda: self._terminate(record),
            )
            if terminal:
                record.closed = True
                await self._cleanup(record)
            elif result.exit_code != 0 and b"Error response from daemon" in result.stderr.encode():
                record.closed = True
                await self._cleanup(record)
                raise SandboxInfrastructureError("Docker execution failed")
            return result
        except asyncio.CancelledError, SandboxInfrastructureError, SandboxUnavailableError:
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
            cmd = build_collect_output_args(record.container, output_dir)
            result = await self._command(cmd)
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace").strip()
                if any(w in err for w in ("output", "unsafe", "invalid", "limit", "escapes")):
                    raise SandboxValidationError(err)
                raise SandboxInfrastructureError(f"Docker collection failed: {err}")
            return parse_collected_output(result.stdout)
        except SandboxValidationError, SandboxBusyError, SandboxClosedError, SandboxUnknownError:
            raise
        except Exception as error:
            record.closed = True
            await self._cleanup(record)
            raise SandboxInfrastructureError("Docker output collection failed") from error
        finally:
            record.busy = False

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

    async def _docker_process(self, args: Sequence[str]) -> asyncio.subprocess.Process:
        try:
            return await asyncio.create_subprocess_exec(
                "docker",
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as error:
            raise SandboxUnavailableError("Docker CLI is not installed") from error
        except OSError as error:
            raise SandboxInfrastructureError("Docker process could not start") from error

    async def _success(self, args: Sequence[str], stdin: bytes | None = None) -> bytes:
        result = await self._command(args, stdin)
        if result.returncode != 0:
            raise SandboxInfrastructureError("Docker sandbox command failed")
        return result.stdout

    async def _command(self, args: Sequence[str], stdin: bytes | None = None) -> _DockerResult:
        process = await self._docker_process(args)
        stdout, stderr = await process.communicate(stdin)
        return _DockerResult(process.returncode or 0, stdout, stderr)

    async def _terminate(self, record: _Record) -> None:
        await self._remove_resources(record.container, record.volume, True, True)
        record.resources_removed = True
        process = record.process
        if process is not None and process.returncode is None:
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=1.0)
            except TimeoutError:
                pass

    async def _cleanup(self, record: _Record) -> None:
        if record.cleaned:
            return
        if not record.resources_removed:
            await self._remove_resources(record.container, record.volume, True, True)
            record.resources_removed = True
        record.cleaned = True

    async def _remove_resources(
        self, container: str, volume: str, container_created: bool, volume_created: bool
    ) -> None:
        if container_created:
            await self._remove_one(("rm", "--force", container))
        if volume_created:
            await self._remove_one(("volume", "rm", volume))

    async def _remove_one(self, args: Sequence[str]) -> None:
        result = await self._command(args)
        if result.returncode != 0 and b"No such" not in result.stderr:
            raise SandboxInfrastructureError("Docker sandbox cleanup failed")
