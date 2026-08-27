from __future__ import annotations

import os
import stat
import sys
import tarfile


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
    if not isinstance(name, str):
        return False
    try:
        name.encode("utf-8")
    except UnicodeError:
        return False
    if not name or name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
        return False
    if "\x00" in name or "\\" in name:
        return False
    components = name.split("/")
    return not any(not c or c in {".", ".."} for c in components)


if __name__ == "__main__":
    main()
