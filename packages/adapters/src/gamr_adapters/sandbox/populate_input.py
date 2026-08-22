from __future__ import annotations

import os
import stat
import sys
import tarfile
from pathlib import PurePosixPath


def main() -> None:
    root = "/input"
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as archive:
        for member in archive:
            if not member.isreg() or not _safe_name(member.name):
                raise ValueError("input archive contains an unsafe entry")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("input archive entry cannot be read")
            destination = os.path.join(root, member.name)
            os.makedirs(os.path.dirname(destination), mode=0o755, exist_ok=True)
            with open(destination, "wb") as output:
                output.write(source.read())
            os.chmod(destination, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    for directory, _, _ in os.walk(root):
        os.chmod(directory, 0o555)


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and not name.startswith("/")
        and "\\" not in name
        and "\x00" not in name
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


if __name__ == "__main__":
    main()
