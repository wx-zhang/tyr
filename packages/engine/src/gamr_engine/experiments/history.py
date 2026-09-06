from __future__ import annotations

from datetime import UTC, datetime

from gamr_core import CaseResult

from ..ports.artifacts import ArtifactStore
from .artifacts import scientist_artifact_id
from .model_response import render_transcript
from .records import ScenarioExecutionRecord

MAX_HISTORY_TRANSCRIPT_CHARS = 4000
MAX_SCIENTIST_HISTORY_RECORD_BYTES = 10_000


def slice_utf8(text: str, max_bytes: int, *, from_end: bool = False) -> str:
    if max_bytes <= 0:
        return ""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    sliced = encoded[-max_bytes:] if from_end else encoded[:max_bytes]
    return sliced.decode("utf-8", errors="ignore")


def truncate_with_marker(text: str, max_bytes: int, marker: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    marker_bytes = len(marker.encode("utf-8"))
    if max_bytes <= marker_bytes:
        return slice_utf8(marker, max_bytes)
    available = max_bytes - marker_bytes
    head_bytes = available // 2
    tail_bytes = available - head_bytes
    return (
        slice_utf8(text, head_bytes)
        + marker
        + slice_utf8(text, tail_bytes, from_end=True)
    )


def truncate_scientist_history_transcript(transcript_text: str) -> str:
    return truncate_with_marker(
        transcript_text,
        MAX_HISTORY_TRANSCRIPT_CHARS,
        "\n    [... middle of transcript truncated ...]\n",
    )


def history_recency(record: ScenarioExecutionRecord) -> datetime:
    stamp = record.source_created_at
    if stamp is None:
        return datetime.max.replace(tzinfo=UTC)
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=UTC)
    return stamp


def latest_unique_records(
    records: list[ScenarioExecutionRecord], limit: int
) -> list[ScenarioExecutionRecord]:
    if limit <= 0:
        return []
    newest: dict[str, ScenarioExecutionRecord] = {}
    recency: dict[str, datetime] = {}
    for record in records:
        scenario_id = record.case.scenario_id
        stamp = history_recency(record)
        previous = recency.get(scenario_id)
        if previous is not None and previous > stamp:
            continue
        newest[scenario_id] = record
        recency[scenario_id] = stamp
    ranked = sorted(
        newest.values(),
        key=lambda item: (history_recency(item), item.case.scenario_id),
        reverse=True,
    )[:limit]
    ranked.reverse()
    return ranked


def cap_history_records(
    records: list[ScenarioExecutionRecord], *, test_limit: int, scientist_limit: int
) -> list[ScenarioExecutionRecord]:
    return latest_unique_records(
        [record for record in records if record.origin == "base"], test_limit
    ) + latest_unique_records(
        [record for record in records if record.origin != "base"], scientist_limit
    )


def effective_scientist_history(
    records: list[ScenarioExecutionRecord], artifacts: ArtifactStore | None
) -> list[ScenarioExecutionRecord]:
    if artifacts is None:
        return records
    checker = getattr(artifacts, "is_scientist_scenario_archived", None)
    if not callable(checker):
        return records
    return [
        record
        for record in records
        if not record.origin_run_id
        or not checker(
            record.origin_run_id,
            record.origin_artifact_id or scientist_artifact_id(record.case.scenario_id),
        )
    ]


def scientist_history_block(record: ScenarioExecutionRecord) -> str:
    case: CaseResult = record.case
    steps = "\n".join(
        f"    {index}. {step}" for index, step in enumerate(record.rendered_steps, 1)
    )
    transcript_text = truncate_scientist_history_transcript(render_transcript(record.transcript))
    details = [
        f"  Success criteria: {record.rendered_success or '(not provided)' }",
        f"  Expected control: {record.scenario.spec.expected_control}",
        f"  Evidence requirements: {'; '.join(record.scenario.spec.evidence_requirements)}",
    ]
    if case.assessment_failure:
        details.append(f"  Assessment failure: {case.assessment_failure}")
    if case.reason_codes:
        details.append(f"  Reason codes: {', '.join(str(code) for code in case.reason_codes)}")
    if case.missing_evidence:
        details.append(f"  Missing evidence: {'; '.join(case.missing_evidence)}")
    details_text = "\n".join(details)
    return (
        f"=== {case.scenario_id} "
        f"(outcome={case.outcome}, verdict={case.verdict}, "
        f"objective={case.objective_status}, assessment={case.assessment_status}) ===\n"
        f"  Title: {record.rendered_title}\n"
        f"  Objective: {record.rendered_objective}\n"
        f"  Steps:\n{steps}\n"
        f"{details_text}\n"
        f"  Execution transcript:\n{transcript_text or '    (no transcript)'}\n"
        f"  Assessment summary: {case.summary}"
    )


def scientist_history(
    records: list[ScenarioExecutionRecord], *, max_bytes: int | None = None
) -> str:
    if not records:
        return "none"
    blocks = [scientist_history_block(record) for record in records]
    if max_bytes is not None:
        separator_bytes = len(b"\n\n")
        available = max_bytes - separator_bytes * (len(blocks) - 1)
        per_record = max(1, available // len(blocks))
        per_record = min(per_record, MAX_SCIENTIST_HISTORY_RECORD_BYTES)
        if any(len(block.encode("utf-8")) > per_record for block in blocks):
            blocks = [
                truncate_with_marker(
                    block,
                    per_record,
                    "\n    [... history record truncated ...]\n",
                )
                for block in blocks
            ]
    return "\n\n".join(blocks)
