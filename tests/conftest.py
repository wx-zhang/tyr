from collections.abc import Callable
from pathlib import Path

import pytest

RUN_EVIDENCE_ROOT = Path(__file__).parent / "fixtures" / "run_evidence"


@pytest.fixture(scope="session")
def run_evidence_root() -> Path:
    return RUN_EVIDENCE_ROOT


@pytest.fixture
def run_evidence_bundle(run_evidence_root: Path) -> Callable[[str], Path]:
    def resolve(name: str) -> Path:
        bundle = run_evidence_root / name
        if not bundle.is_dir() or bundle.parent != run_evidence_root:
            raise ValueError(f"unknown run-evidence fixture: {name}")
        return bundle

    return resolve
