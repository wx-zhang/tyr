from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from gamr_core import ActivityType, EvidenceType, RunActivity

_SAFE_STATUS = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,99}$")
_UNSAFE_IDENTIFIER = re.compile(
    r"bearer\s+\S+|(?:api[_-]?key|token|secret)\s*[=:]\s*\S+|(?:^|[\s=:])(?:/|[A-Za-z]:[\\/]|~[/\\])",
    re.IGNORECASE,
)

TERMINAL_STATES = frozenset({"completed", "partial", "failed", "cancelled", "rejected"})
_DIAGNOSTIC_KEYS = (
    "agentName",
    "agent",
    "computerName",
    "state",
    "status",
    "error",
    "errorMessage",
    "failureReason",
    "reason",
    "refusal",
    "blockReason",
    "detail",
    "details",
    "summary",
    "message",
)


@dataclass(frozen=True)
class OperationWaitResult:
    payload: dict[str, object]
    local_state: str
    notes: tuple[str, ...] = ()


def normalize_operation_result(
    result: dict[str, object],
    *,
    run_id: str,
    starting_sequence: int = 1,
) -> list[RunActivity]:
    operation_id = str(result.get("operationId") or result.get("id") or "operation")
    if _UNSAFE_IDENTIFIER.search(operation_id):
        operation_id = "operation"
    occurred_at = _operation_time(result.get("updatedAt"))
    activities: list[RunActivity] = []
    groups = (
        ("executions", ActivityType.EXECUTION, "execution"),
        ("delegations", ActivityType.DELEGATION, "delegation"),
        ("bridges", ActivityType.BRIDGE, "bridge"),
        ("toolCalls", ActivityType.TOOL_CALL, "tool call"),
        ("pendingApprovals", ActivityType.APPROVAL, "approval"),
    )
    for key, activity_type, label in groups:
        entries = result.get(key)
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            status = str(entry.get("state") or entry.get("status") or "observed").lower()
            if not _SAFE_STATUS.fullmatch(status):
                status = "observed"
            source = _observed_participant(entry, "source")
            target = _observed_participant(entry, "target")
            item_key = str(entry.get("id") or entry.get(f"{key[:-1]}Id") or index)
            item_id = sha256(f"{run_id}:{operation_id}:{key}:{item_key}".encode()).hexdigest()[:32]
            activities.append(
                RunActivity(
                    id=f"operation-{item_id}",
                    runId=run_id,
                    sequence=starting_sequence + len(activities),
                    occurredAt=occurred_at,
                    activityType=activity_type,
                    status=status,
                    operationId=operation_id,
                    sourceParticipantId=source,
                    targetParticipantId=target,
                    evidenceType=EvidenceType.EVENT,
                    summary=f"Observed Tyr {label}",
                    metadata={"_operationSource": key},
                )
            )
    return activities


normalize_tyr_operation = normalize_operation_result


def _operation_time(value: object) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed.utcoffset() == UTC.utcoffset(parsed):
                return parsed
        except ValueError:
            pass
    return datetime(1970, 1, 1, tzinfo=UTC)


def _observed_participant(entry: dict[str, object], side: str) -> str | None:
    for key in (f"{side}ParticipantId", f"{side}Id"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip() and not _UNSAFE_IDENTIFIER.search(value):
            return value.strip()
    return None


def work_pending(result: dict[str, object]) -> bool:
    for group in ("executions", "bridges"):
        entries = result.get(group)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            state = entry.get("state") or entry.get("status")
            if isinstance(state, str) and state.lower() not in TERMINAL_STATES:
                return True
    return False


def failure_notes(result: dict[str, object]) -> tuple[str, ...]:
    notes: list[str] = []
    for group in ("executions", "bridges"):
        entries = result.get(group)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                notes.append(f"{group}: {entry!r}"[:400])
                continue
            state = str(entry.get("state") or entry.get("status") or "").lower()
            fields = {
                key: str(entry[key]).strip()
                for key in _DIAGNOSTIC_KEYS
                if isinstance(entry.get(key), (str, int, float, bool))
                and str(entry[key]).strip()
            }
            cause_keys = set(fields) - {"agentName", "agent", "computerName", "state", "status"}
            if state == "completed" and not cause_keys:
                continue
            if not fields:
                notes.append(f"{group}: {entry!r}"[:400])
            else:
                notes.append(f"{group}: " + ", ".join(f"{k}={v}" for k, v in fields.items())[:400])
    return tuple(notes)


def _peer_approval_pending(result: dict[str, object]) -> bool:
    entries = result.get("bridges")
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        state = str(entry.get("state") or entry.get("status") or "").lower()
        if state in {"waiting_for_approval", "pending_approval", "approval_required"}:
            return True
        if entry.get("pendingApproval") or entry.get("pendingApprovals"):
            return True
    return False


async def settle_operation(
    read_status: Callable[[int], Awaitable[dict[str, object]]],
    *,
    initial: dict[str, object] | None = None,
    attempts: int | None = None,
    poll_wait_seconds: int = 30,
    settle_wait_seconds: int = 5,
    poll_budget_seconds: float = 300,
    poll_min_gap_seconds: float = 1,
) -> OperationWaitResult:
    """Poll until the outer operation and delegated work are genuinely quiet.

    The normal budget is wall-clock based so an immediately-returning long poll
    cannot consume a fixed number of attempts before a slow delegated action
    finishes. ``attempts`` remains a bounded test seam for deterministic tests.
    """

    result = initial or await read_status(0)
    quiet_stamp: object = None
    deadline = time.monotonic() + poll_budget_seconds
    count = 0
    while (attempts is not None and count < attempts) or (
        attempts is None and time.monotonic() < deadline
    ):
        count += 1
        state = str(result.get("state") or result.get("status") or "unknown").lower()
        if state == "input_required":
            return OperationWaitResult(result, "input_required", failure_notes(result))
        if result.get("pendingApprovals"):
            return OperationWaitResult(result, "waiting_for_approval", failure_notes(result))
        if _peer_approval_pending(result):
            return OperationWaitResult(result, "peer_approval_blocked", failure_notes(result))
        done = state in TERMINAL_STATES and not work_pending(result)
        if done and result.get("updatedAt") == quiet_stamp:
            return OperationWaitResult(result, "settled", failure_notes(result))
        quiet_stamp = result.get("updatedAt") if done else None
        requested_wait = settle_wait_seconds if done else poll_wait_seconds
        started = time.monotonic()
        result = await read_status(requested_wait)
        gap = poll_min_gap_seconds - (time.monotonic() - started)
        if gap > 0:
            await asyncio.sleep(gap)

    state = str(result.get("state") or result.get("status") or "unknown").lower()
    if state in TERMINAL_STATES and not work_pending(result):
        return OperationWaitResult(result, "settled", failure_notes(result))
    return OperationWaitResult(result, "timeout", failure_notes(result))
