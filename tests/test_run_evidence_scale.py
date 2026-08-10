from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from gamr_adapters.artifacts.query import ActivityMemoryRepository, ActivityPage
from gamr_core import ActivityType, EvidenceQuery, EvidenceType, RunActivity


def test_run_evidence_repository_handles_10000_items_with_bounded_pages() -> None:
    started = datetime(2026, 8, 8, tzinfo=UTC)
    rows = [
        RunActivity(
            id=f"scale-{sequence}",
            runId="scale-run",
            sequence=sequence,
            occurredAt=started + timedelta(seconds=sequence),
            activityType=ActivityType.CASE,
            status="completed" if sequence % 2 == 0 else "observed",
            caseId=f"case-{sequence % 10}",
            evidenceType=EvidenceType.EVENT,
            summary=f"item {sequence}",
        )
        for sequence in range(1, 10_001)
    ]
    repository = ActivityMemoryRepository(rows)

    began = time.perf_counter()
    page = repository.query(
        EvidenceQuery(runId="scale-run", q="item 99", status="completed", limit=200)
    )

    assert isinstance(page, ActivityPage)
    assert len(page.items) <= 200
    assert all(item.status == "completed" for item in page.items)
    assert time.perf_counter() - began < 2
