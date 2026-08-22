from __future__ import annotations

import shutil
import subprocess

import pytest
from gamr_adapters.sandbox.docker import IMAGE_TAG, DockerSandbox
from gamr_engine.ports import SandboxClosedError, SandboxEntry


@pytest.fixture
def docker_image() -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is unavailable")
    result = subprocess.run(
        ["docker", "image", "inspect", IMAGE_TAG],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"Docker image {IMAGE_TAG} is not built")


@pytest.mark.sandbox_docker
@pytest.mark.asyncio
async def test_docker_runtime_isolated_input_workspace_and_environment(docker_image: None) -> None:
    sandbox = DockerSandbox()
    sandbox_id = await sandbox.start([SandboxEntry("immutable.txt", b"original")])

    first = await sandbox.execute(
        sandbox_id,
        "from pathlib import Path\n"
        "import os\n"
        "assert Path('/input/immutable.txt').read_text() == 'original'\n"
        "try:\n"
        "    Path('/input/immutable.txt').write_text('changed')\n"
        "except OSError:\n"
        "    pass\n"
        "assert 'TYR_MCP_TOKEN' not in os.environ\n"
        "Path('/workspace/state.txt').write_text('persisted')\n",
    )
    second = await sandbox.execute(
        sandbox_id,
        "from pathlib import Path\n"
        "assert Path('/input/immutable.txt').read_text() == 'original'\n"
        "assert Path('/workspace/state.txt').read_text() == 'persisted'\n",
    )

    assert first.exit_code == 0
    assert second.exit_code == 0
    await sandbox.close(sandbox_id)


@pytest.mark.sandbox_docker
@pytest.mark.asyncio
async def test_docker_runtime_denies_network(docker_image: None) -> None:
    sandbox = DockerSandbox()
    sandbox_id = await sandbox.start()
    result = await sandbox.execute(
        sandbox_id,
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('http://example.com', timeout=.5)\n"
        "except Exception:\n"
        "    print('denied')\n"
        "else:\n"
        "    raise AssertionError('network unexpectedly available')\n",
    )
    await sandbox.close(sandbox_id)

    assert result.exit_code == 0
    assert result.stdout.strip() == "denied"


@pytest.mark.sandbox_docker
@pytest.mark.asyncio
async def test_docker_runtime_pip_unavailable(docker_image: None) -> None:
    sandbox = DockerSandbox()
    sandbox_id = await sandbox.start()
    result = await sandbox.execute(
        sandbox_id,
        "import sys\n"
        "try:\n"
        "    import pip\n"
        "    print('pip_found')\n"
        "except ImportError:\n"
        "    print('pip_absent')\n",
    )
    await sandbox.close(sandbox_id)

    assert result.exit_code == 0
    assert result.stdout.strip() == "pip_absent"


@pytest.mark.sandbox_docker
@pytest.mark.asyncio
async def test_docker_runtime_limits_and_labeled_cleanup(docker_image: None) -> None:
    sandbox = DockerSandbox()
    sandbox_id = await sandbox.start()

    timeout_result = await sandbox.execute(
        sandbox_id,
        "while True: pass",
    )
    assert timeout_result.timed_out
    with pytest.raises(SandboxClosedError):
        await sandbox.execute(sandbox_id, "print('closed')")
    await sandbox.close(sandbox_id)

    ps_output = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"label=com.tyr.gamr.sandbox.id={sandbox_id}", "-q"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert not ps_output.stdout.strip()



