from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

from gamr_adapters.sandbox.docker import IMAGE_TAG

_ROOT: Final = Path(__file__).resolve().parents[1]
_CONTEXT: Final = (_ROOT / "packages/adapters/src/gamr_adapters/sandbox").resolve()
_DOCKERFILE: Final = _CONTEXT / "Dockerfile"


def main() -> int:
    if not _CONTEXT.is_dir() or not _DOCKERFILE.is_file():
        raise SystemExit("sandbox Docker build context is missing")
    result = subprocess.run(
        ["docker", "build", "--tag", IMAGE_TAG, "--file", str(_DOCKERFILE), str(_CONTEXT)],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
