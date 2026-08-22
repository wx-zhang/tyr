from __future__ import annotations

import warnings

from gamr_engine.ports import Sandbox

from gamr_adapters.config import Settings

from .disabled import DisabledSandbox
from .docker import DockerSandbox
from .host import HostUnsafeSandbox


def create_sandbox(settings: Settings | None = None) -> Sandbox:
    selected = settings or Settings()
    if selected.sandbox_backend == "disabled":
        return DisabledSandbox()
    if selected.sandbox_backend == "host-unsafe":
        warnings.warn(
            "GAMR_SANDBOX_BACKEND=host-unsafe is not a security boundary; "
            "generated code can access the host as the current user",
            RuntimeWarning,
            stacklevel=2,
        )
        return HostUnsafeSandbox()
    return DockerSandbox()
