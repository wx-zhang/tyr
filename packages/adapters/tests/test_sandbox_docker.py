from __future__ import annotations

import asyncio
import io
import sys
import tarfile

import pytest
from gamr_adapters.sandbox import docker as docker_module
from gamr_adapters.sandbox.collect_output import parse_collected_output
from gamr_adapters.sandbox.docker import (
    IMAGE_TAG,
    build_collect_output_args,
    build_container_create_args,
    build_execute_args,
    build_input_archive,
    build_populate_args,
    build_volume_create_args,
)
from gamr_engine.ports import (
    SandboxBusyError,
    SandboxClosedError,
    SandboxEntry,
    SandboxId,
    SandboxUnknownError,
    SandboxValidationError,
)


def test_input_archive_contains_only_validated_logical_files() -> None:
    archive = build_input_archive(
        [
            SandboxEntry("dir/name with spaces.txt", b"hello"),
            SandboxEntry("punctuation-;-$().txt", b"world"),
        ]
    )

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as handle:
        members = handle.getmembers()
        assert [member.name for member in members] == [
            "dir/name with spaces.txt",
            "punctuation-;-$().txt",
        ]
        assert handle.extractfile(members[0]).read() == b"hello"  # type: ignore[union-attr]


def test_docker_vectors_use_fixed_containment_flags() -> None:
    volume = "gamr-volume-private"
    container = "gamr-container-private"
    public_id = "public-id-with-metacharacters-$()"
    volume_args = build_volume_create_args(volume, public_id)
    populate_args = build_populate_args(volume, public_id)
    container_args = build_container_create_args(container, volume, public_id)
    execute_args = build_execute_args(container)

    assert IMAGE_TAG in populate_args
    assert "--interactive" in populate_args
    assert IMAGE_TAG in container_args
    assert "--network" in populate_args and "none" in populate_args
    assert "--network" in container_args and "none" in container_args
    assert "--read-only" in populate_args
    assert "--cap-drop" in populate_args and "ALL" in populate_args
    assert "--security-opt" in populate_args and "no-new-privileges" in populate_args
    assert "--user" in populate_args and "65532:65532" in populate_args
    assert any(public_id in value for value in populate_args)
    assert "--read-only" in container_args
    assert "--cap-drop" in container_args and "ALL" in container_args
    assert "--security-opt" in container_args and "no-new-privileges" in container_args
    assert "--cpus" in container_args and "1" in container_args
    assert "--memory" in container_args and "256m" in container_args
    assert "--memory-swap" in container_args and "256m" in container_args
    assert "--pids-limit" in container_args and "64" in container_args
    assert "--restart" in container_args and "no" in container_args
    assert any(value.endswith(":/input:ro") for value in container_args)
    workspace_mount = next(value for value in container_args if value.startswith("/workspace:rw"))
    assert "uid=65532" in workspace_mount
    assert "gid=65532" in workspace_mount
    assert "mode=700" in workspace_mount
    assert execute_args[-1] == "-"
    assert any(public_id in value for value in volume_args)
    assert any(public_id in value for value in container_args)
    assert container not in volume_args


@pytest.mark.asyncio
async def test_docker_backend_failure_raises_and_invalidates_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gamr_adapters.sandbox.docker import DockerSandbox, _DockerResult
    from gamr_engine.ports import SandboxInfrastructureError

    sandbox = DockerSandbox()

    async def command(args: tuple[str, ...], stdin: bytes | None = None) -> _DockerResult:
        del args, stdin
        return _DockerResult(0, b"", b"")

    async def failing_process(args: tuple[str, ...]) -> asyncio.subprocess.Process:
        del args
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            (
                "import sys; "
                "sys.stderr.write('Error response from daemon: No such container\\n'); "
                "sys.exit(1)"
            ),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(sandbox, "_command", command)
    monkeypatch.setattr(sandbox, "_docker_process", failing_process)
    sandbox_id = await sandbox.start()

    with pytest.raises(SandboxInfrastructureError):
        await sandbox.execute(sandbox_id, "print('hello')")
    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('closed')")


@pytest.mark.asyncio
async def test_docker_backend_is_constructed_without_runtime_probe() -> None:
    from gamr_adapters.sandbox.docker import DockerSandbox

    sandbox = DockerSandbox()

    assert sandbox is not None


@pytest.mark.asyncio
async def test_docker_lifecycle_uses_fake_cli_and_fresh_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gamr_adapters.sandbox.docker import DockerSandbox, _DockerResult

    sandbox = DockerSandbox()
    commands: list[tuple[str, ...]] = []

    async def command(args: tuple[str, ...], stdin: bytes | None = None) -> _DockerResult:
        del stdin
        commands.append(args)
        return _DockerResult(0, b"", b"")

    async def process(args: tuple[str, ...]) -> asyncio.subprocess.Process:
        del args
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(sandbox, "_command", command)
    monkeypatch.setattr(sandbox, "_docker_process", process)
    sandbox_id = await sandbox.start([SandboxEntry("input.txt", b"content")])

    result = await sandbox.execute(sandbox_id, "print('ok')")
    await sandbox.close(sandbox_id)
    await sandbox.close(sandbox_id)

    assert result.exit_code == 0
    assert any(args[0:2] == ("volume", "create") for args in commands)
    assert any(args[0:2] == ("volume", "rm") for args in commands)
    assert any(args[0:2] == ("rm", "--force") for args in commands)
    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('closed')")



@pytest.mark.asyncio
async def test_docker_partial_start_failure_removes_created_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gamr_adapters.sandbox.docker import DockerSandbox, _DockerResult
    from gamr_engine.ports import SandboxInfrastructureError

    sandbox = DockerSandbox()
    commands: list[tuple[str, ...]] = []

    async def command(args: tuple[str, ...], stdin: bytes | None = None) -> _DockerResult:
        del stdin
        commands.append(args)
        if args[0] == "create":
            return _DockerResult(1, b"", b"create failed")
        return _DockerResult(0, b"", b"")

    monkeypatch.setattr(sandbox, "_command", command)
    with pytest.raises(SandboxInfrastructureError):
        await sandbox.start()

    assert any(args[0:2] == ("volume", "rm") for args in commands)


@pytest.mark.asyncio
async def test_docker_same_id_busy_and_terminal_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gamr_adapters.sandbox.docker import DockerSandbox, _DockerResult

    monkeypatch.setattr(docker_module, "MAX_EXECUTION_SECONDS", 0.2)
    sandbox = DockerSandbox()

    async def command(args: tuple[str, ...], stdin: bytes | None = None) -> _DockerResult:
        del args, stdin
        return _DockerResult(0, b"", b"")

    async def process(args: tuple[str, ...]) -> asyncio.subprocess.Process:
        del args
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(sandbox, "_command", command)
    monkeypatch.setattr(sandbox, "_docker_process", process)
    sandbox_id = await sandbox.start()
    active = asyncio.create_task(sandbox.execute(sandbox_id, "while True: pass"))
    await asyncio.sleep(0.03)
    with pytest.raises(SandboxBusyError):
        await sandbox.execute(sandbox_id, "print('busy')")
    result = await active

    assert result.timed_out
    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('closed')")


def test_docker_collect_output_args_no_shell_interpolation() -> None:
    args = build_collect_output_args("container-123", "output/attempt-001; rm -rf /")
    assert "exec" in args
    assert "container-123" in args
    assert "/opt/gamr/collect_output.py" in args
    assert "output/attempt-001; rm -rf /" in args
    assert not any("sh" in arg or "bash" in arg for arg in args)


def test_parse_collected_output_validates_and_extracts_archive() -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as archive:
        info1 = tarfile.TarInfo(name="upload-001/data.txt")
        info1.size = 5
        info1.mode = 0o444
        archive.addfile(info1, io.BytesIO(b"hello"))
        info2 = tarfile.TarInfo(name="upload-001/nested/file.bin")
        info2.size = 3
        info2.mode = 0o444
        archive.addfile(info2, io.BytesIO(b"\x00\x01\x02"))
    valid_tar = buf.getvalue()

    entries = parse_collected_output(valid_tar)
    assert len(entries) == 2
    assert entries[0].path == "upload-001/data.txt"
    assert entries[0].content == b"hello"
    assert entries[1].path == "upload-001/nested/file.bin"
    assert entries[1].content == b"\x00\x01\x02"


def test_parse_collected_output_rejects_symlinks_special_files_and_traversal() -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as archive:
        info = tarfile.TarInfo(name="link.txt")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        archive.addfile(info)
    with pytest.raises(SandboxValidationError):
        parse_collected_output(buf.getvalue())

    buf2 = io.BytesIO()
    with tarfile.open(fileobj=buf2, mode="w") as archive:
        info = tarfile.TarInfo(name="../escape.txt")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"no"))
    with pytest.raises(SandboxValidationError):
        parse_collected_output(buf2.getvalue())


@pytest.mark.asyncio
async def test_docker_collect_output_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    from gamr_adapters.sandbox.docker import DockerSandbox, _DockerResult

    sandbox = DockerSandbox()
    assert sandbox.isolation == "contained"

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as archive:
        info = tarfile.TarInfo(name="upload-001/out.txt")
        info.size = 2
        archive.addfile(info, io.BytesIO(b"ok"))
    valid_tar = buf.getvalue()

    async def command(args: tuple[str, ...], stdin: bytes | None = None) -> _DockerResult:
        del stdin
        if args[0] == "exec" and "/opt/gamr/collect_output.py" in args:
            return _DockerResult(0, valid_tar, b"")
        return _DockerResult(0, b"", b"")

    monkeypatch.setattr(sandbox, "_command", command)
    sandbox_id = await sandbox.start()

    entries = await sandbox.collect_output(sandbox_id, "output/attempt-001")
    assert len(entries) == 1
    assert entries[0].path == "upload-001/out.txt"
    assert entries[0].content == b"ok"

    await sandbox.close(sandbox_id)
    with pytest.raises(SandboxClosedError):
        await sandbox.collect_output(sandbox_id, "output/attempt-001")
    with pytest.raises(SandboxUnknownError):
        await sandbox.collect_output(SandboxId("unknown"), "output/attempt-001")


@pytest.mark.asyncio
async def test_docker_collect_output_failure_cleans_up(monkeypatch: pytest.MonkeyPatch) -> None:
    from gamr_adapters.sandbox.docker import DockerSandbox, _DockerResult

    sandbox = DockerSandbox()
    commands: list[tuple[str, ...]] = []

    async def command(args: tuple[str, ...], stdin: bytes | None = None) -> _DockerResult:
        del stdin
        commands.append(args)
        if args[0] == "exec" and "/opt/gamr/collect_output.py" in args:
            return _DockerResult(1, b"", b"collector error: output byte limit exceeded\n")
        return _DockerResult(0, b"", b"")

    monkeypatch.setattr(sandbox, "_command", command)
    sandbox_id = await sandbox.start()

    with pytest.raises(SandboxValidationError):
        await sandbox.collect_output(sandbox_id, "output/attempt-001")

