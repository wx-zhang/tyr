from __future__ import annotations

import asyncio

import pytest
from gamr_adapters.sandbox import host as host_module
from gamr_adapters.sandbox.host import HostUnsafeSandbox
from gamr_engine.ports import (
    SandboxBusyError,
    SandboxClosedError,
    SandboxEntry,
    SandboxId,
    SandboxUnknownError,
    SandboxValidationError,
)


@pytest.mark.asyncio
async def test_host_backend_uses_fresh_processes_and_persistent_workspace() -> None:
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start([SandboxEntry("data/input.txt", b"hello")])

    first = await sandbox.execute(
        sandbox_id,
        "from pathlib import Path\n"
        "assert Path('../input/data/input.txt').read_text() == 'hello'\n"
        "Path('state.txt').write_text('persisted')\n"
        "value = 'not persistent'\n"
        "print('first')\n",
    )
    second = await sandbox.execute(
        sandbox_id,
        "from pathlib import Path\n"
        "assert not globals().get('value')\n"
        "print(Path('state.txt').read_text())\n",
    )

    assert first.exit_code == 0
    assert second.stdout.strip() == "persisted"
    await sandbox.close(sandbox_id)


@pytest.mark.asyncio
async def test_host_backend_timeout_when_child_closes_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_module, "MAX_EXECUTION_SECONDS", 0.2)
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()

    result = await sandbox.execute(
        sandbox_id,
        "import os, time\nos.close(1)\nos.close(2)\ntime.sleep(10)",
    )

    assert result.timed_out
    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('closed')")


@pytest.mark.asyncio
async def test_host_backend_timeout_when_grandchild_lives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host_module, "MAX_EXECUTION_SECONDS", 0.2)
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()

    result = await sandbox.execute(
        sandbox_id,
        (
            "import subprocess, sys\n"
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])\n"
            "sys.exit(0)"
        ),
    )

    assert result.timed_out
    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('closed')")


@pytest.mark.asyncio
async def test_host_backend_timeout_invalidates_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host_module, "MAX_EXECUTION_SECONDS", 0.2)
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()

    result = await sandbox.execute(sandbox_id, "while True: pass")

    assert result.timed_out
    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('closed')")


@pytest.mark.asyncio
async def test_host_backend_output_limit_invalidates_sandbox() -> None:
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()

    result = await sandbox.execute(sandbox_id, "print('x' * (1024 * 1024 + 100))")

    assert result.output_limited
    assert len(result.stdout.encode()) <= 1024 * 1024
    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('closed')")


@pytest.mark.asyncio
async def test_host_backend_removes_temp_tree_and_rejects_closed_and_unknown_ids() -> None:
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()

    await sandbox.execute(
        sandbox_id,
        "from pathlib import Path; Path('marker.txt').write_text('hi')",
    )
    await sandbox.close(sandbox_id)
    await sandbox.close(sandbox_id)

    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('no')")
    with pytest.raises(SandboxUnknownError):
        await sandbox.execute("missing", "print('no')")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_host_backend_has_no_configured_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYR_MCP_TOKEN", "secret-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()

    result = await sandbox.execute(
        sandbox_id,
        "import os\n"
        "assert 'TYR_MCP_TOKEN' not in os.environ\n"
        "assert 'OPENROUTER_API_KEY' not in os.environ\n",
    )

    assert result.exit_code == 0
    await sandbox.close(sandbox_id)


@pytest.mark.asyncio
async def test_host_backend_reports_python_failure_but_remains_usable() -> None:
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()

    failed = await sandbox.execute(sandbox_id, "raise RuntimeError('expected')")
    succeeded = await sandbox.execute(sandbox_id, "print('usable')")

    assert failed.exit_code != 0
    assert "RuntimeError" in failed.stderr
    assert succeeded.exit_code == 0
    await sandbox.close(sandbox_id)


@pytest.mark.asyncio
async def test_host_backend_rejects_overlapping_execution_and_allows_other_ids() -> None:
    sandbox = HostUnsafeSandbox()
    first_id = await sandbox.start()
    second_id = await sandbox.start()

    first_task = asyncio.create_task(sandbox.execute(first_id, "import time; time.sleep(.2)"))
    await asyncio.sleep(0.03)
    with pytest.raises(SandboxBusyError):
        await sandbox.execute(first_id, "print('busy')")
    other_task = asyncio.create_task(sandbox.execute(second_id, "print('other')"))
    await asyncio.gather(first_task, other_task)
    await sandbox.close(first_id)
    await sandbox.close(second_id)


@pytest.mark.asyncio
async def test_host_backend_closing_active_execution_cleans_descendants() -> None:
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()
    task = asyncio.create_task(
        sandbox.execute(
            sandbox_id,
            "import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "time.sleep(30)\n",
        )
    )
    await asyncio.sleep(0.1)
    await sandbox.close(sandbox_id)

    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('closed')")


@pytest.mark.asyncio
async def test_host_backend_rejects_invalid_source_without_starting_python() -> None:
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()

    with pytest.raises(SandboxValidationError):
        await sandbox.execute(sandbox_id, b"\xff")
    with pytest.raises(SandboxValidationError):
        await sandbox.execute(sandbox_id, "x" * (64 * 1024 + 1))
    await sandbox.close(sandbox_id)


@pytest.mark.asyncio
async def test_host_backend_reports_unsafe_isolation() -> None:
    sandbox = HostUnsafeSandbox()
    assert sandbox.isolation == "unsafe"


@pytest.mark.asyncio
async def test_host_backend_collect_output_success() -> None:
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()
    await sandbox.execute(
        sandbox_id,
        (
            "import os\n"
            "os.makedirs('output/attempt-001/upload-001', exist_ok=True)\n"
            "with open('output/attempt-001/upload-001/data.txt', 'wb') as f:\n"
            "    f.write(b'decoded text')\n"
            "with open('output/attempt-001/upload-001/nested.bin', 'wb') as f:\n"
            "    f.write(b'\\x00\\x01\\x02')\n"
        ),
    )
    entries = await sandbox.collect_output(sandbox_id, "output/attempt-001")
    assert len(entries) == 2
    assert entries[0].path == "upload-001/data.txt"
    assert entries[0].content == b"decoded text"
    assert entries[1].path == "upload-001/nested.bin"
    assert entries[1].content == b"\x00\x01\x02"

    missing = await sandbox.collect_output(sandbox_id, "output/attempt-002")
    assert missing == ()

    await sandbox.close(sandbox_id)


@pytest.mark.asyncio
async def test_host_backend_collect_output_rejects_symlinks_and_traversal() -> None:
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()
    await sandbox.execute(
        sandbox_id,
        (
            "import os\n"
            "os.makedirs('output/attempt-001', exist_ok=True)\n"
            "with open('secret.txt', 'w') as f:\n"
            "    f.write('secret')\n"
            "os.symlink('../../secret.txt', 'output/attempt-001/link.txt')\n"
        ),
    )
    with pytest.raises(SandboxValidationError):
        await sandbox.collect_output(sandbox_id, "output/attempt-001")

    with pytest.raises(SandboxValidationError):
        await sandbox.collect_output(sandbox_id, "../outside")

    await sandbox.close(sandbox_id)


@pytest.mark.asyncio
async def test_host_backend_collect_output_rejects_busy_unknown_and_closed() -> None:
    sandbox = HostUnsafeSandbox()
    sandbox_id = await sandbox.start()
    task = asyncio.create_task(sandbox.execute(sandbox_id, "import time; time.sleep(0.3)"))
    await asyncio.sleep(0.05)
    with pytest.raises(SandboxBusyError):
        await sandbox.collect_output(sandbox_id, "output/attempt-001")
    await task

    with pytest.raises(SandboxUnknownError):
        await sandbox.collect_output(SandboxId("unknown-id"), "output/attempt-001")

    await sandbox.close(sandbox_id)
    with pytest.raises(SandboxClosedError):
        await sandbox.collect_output(sandbox_id, "output/attempt-001")
