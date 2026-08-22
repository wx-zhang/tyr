from __future__ import annotations

import asyncio
import io
import sys
import tarfile

import pytest
from gamr_adapters.sandbox import docker as docker_module
from gamr_adapters.sandbox.docker import (
    IMAGE_TAG,
    build_container_create_args,
    build_execute_args,
    build_input_archive,
    build_populate_args,
    build_volume_create_args,
)
from gamr_engine.ports import SandboxBusyError, SandboxClosedError, SandboxEntry


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
    populate_args = build_populate_args(volume)
    container_args = build_container_create_args(container, volume, public_id)
    execute_args = build_execute_args(container)

    assert IMAGE_TAG in populate_args
    assert "--interactive" in populate_args
    assert IMAGE_TAG in container_args
    assert "--network" in populate_args and "none" in populate_args
    assert "--network" in container_args and "none" in container_args
    assert "--read-only" in container_args
    assert "--cap-drop" in container_args and "ALL" in container_args
    assert "--security-opt" in container_args and "no-new-privileges" in container_args
    assert "--cpus" in container_args and "1" in container_args
    assert "--memory" in container_args and "256m" in container_args
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
    record = sandbox._records[sandbox_id]
    assert str(sandbox_id) not in record.container
    assert any(args[0:2] == ("volume", "create") for args in commands)
    assert any(args[0:2] == ("volume", "rm") for args in commands)
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
