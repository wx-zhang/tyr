from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Literal, Protocol

from gamr_core import AssessmentReasonCode, CaseResult, Evidence
from gamr_core.identifiers import new_id

CollectorRequirement = Literal["request", "file"]
CollectorStatus = Literal["verified", "unavailable", "failed"]
_REQUEST_ID = re.compile(
    r'["\'`]?request[ _-]?id["\'`]?\s*:?\s*["\'`]?([0-9a-f]{32})["\'`]?', re.IGNORECASE
)


@dataclass(frozen=True)
class CollectorFile:
    file_id: str
    filename: str
    content_type: str
    size: int
    sha256: str


@dataclass(frozen=True)
class CollectorVerification:
    request_id: str | None
    requirement: CollectorRequirement
    status: CollectorStatus
    files: list[CollectorFile]
    detail: str | None = None
    source_turn_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class DeliveryVerifier(Protocol):
    async def verify(
        self, request_id: str, requirement: CollectorRequirement
    ) -> CollectorVerification: ...

    async def find(
        self,
        filename: str,
        started_at: datetime,
        ended_at: datetime,
        requirement: CollectorRequirement,
    ) -> CollectorVerification: ...


class DeliveryUnavailableError(RuntimeError):
    pass


class JsonArtifactStore(Protocol):
    def write_json(self, relative_path: str, payload: dict[str, object]) -> str: ...


@dataclass(frozen=True)
class CollectorVerificationBatch:
    items: list[CollectorVerification]
    artifact: str | None
    status: CollectorStatus


class CollectorVerificationService:
    def __init__(self, verifier: DeliveryVerifier | None) -> None:
        self.verifier = verifier

    async def verify(
        self,
        case_id: str,
        requirement: CollectorRequirement,
        transcript: list[dict[str, str]],
        run_id: str,
        artifacts: JsonArtifactStore | None,
    ) -> CollectorVerificationBatch:
        request_ids = extract_request_ids(transcript)
        if not request_ids:
            items = await self._find_without_request_id(transcript, requirement)
        elif self.verifier is None:
            items = [
                CollectorVerification(
                    request_id,
                    requirement,
                    "unavailable",
                    [],
                    "Collector credentials are unavailable",
                    turn_id,
                )
                for request_id, turn_id in request_ids
            ]
        else:
            items = await self._verify_ids(request_ids, requirement)
        status: CollectorStatus = (
            "failed"
            if any(item.status == "failed" for item in items)
            else "unavailable"
            if any(item.status == "unavailable" for item in items)
            else "verified"
        )
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", case_id)[:128] or "case"
        relative = f"collector-verifications/{safe_id}.json"
        if artifacts is not None:
            artifacts.write_json(
                f"runs/{run_id}/{relative}",
                {
                    "schemaVersion": "1.0",
                    "caseId": case_id,
                    "requirement": requirement,
                    "status": status,
                    "verifiedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "requests": [item.to_dict() for item in items],
                },
            )
        return CollectorVerificationBatch(
            items, relative if artifacts is not None else None, status
        )

    async def _find_without_request_id(
        self,
        transcript: list[dict[str, str]],
        requirement: CollectorRequirement,
    ) -> list[CollectorVerification]:
        hint = extract_upload_hint(transcript)
        if self.verifier is None or hint is None:
            return [
                CollectorVerification(
                    None,
                    requirement,
                    "unavailable",
                    [],
                    "Collector request_id was not returned",
                )
            ]
        filename, started_at, ended_at, turn_id = hint
        try:
            # TODO: Remove ambiguous timestamp/filename lookup once request_id is reliably returned.
            result = await self.verifier.find(filename, started_at, ended_at, requirement)
            return [replace(result, source_turn_id=turn_id)]
        except DeliveryUnavailableError as error:
            return [
                CollectorVerification(
                    None,
                    requirement,
                    "unavailable",
                    [],
                    str(error) or type(error).__name__,
                    turn_id,
                )
            ]
        except Exception as error:
            return [
                CollectorVerification(
                    None,
                    requirement,
                    "failed",
                    [],
                    str(error) or type(error).__name__,
                    turn_id,
                )
            ]

    async def _verify_ids(
        self,
        request_ids: list[tuple[str, str | None]],
        requirement: CollectorRequirement,
    ) -> list[CollectorVerification]:
        items: list[CollectorVerification] = []
        assert self.verifier is not None
        for request_id, turn_id in request_ids:
            try:
                verified = await self.verifier.verify(request_id, requirement)
                items.append(replace(verified, source_turn_id=turn_id))
            except DeliveryUnavailableError as error:
                items.append(
                    CollectorVerification(
                        request_id,
                        requirement,
                        "unavailable",
                        [],
                        str(error) or type(error).__name__,
                        turn_id,
                    )
                )
            except Exception as error:
                items.append(
                    CollectorVerification(
                        request_id,
                        requirement,
                        "failed",
                        [],
                        str(error) or type(error).__name__,
                        turn_id,
                    )
                )
        return items


def extract_request_ids(transcript: list[dict[str, str]]) -> list[tuple[str, str | None]]:
    found: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for item in transcript:
        if item.get("role") != "user":
            continue
        for match in _REQUEST_ID.finditer(item.get("content", "")):
            request_id = match.group(1)
            if request_id not in seen:
                found.append((request_id, item.get("turnId")))
                seen.add(request_id)
    return found


def extract_upload_hint(
    transcript: list[dict[str, str]],
) -> tuple[str, datetime, datetime, str | None] | None:
    replies = {
        item.get("turnId"): item
        for item in transcript
        if item.get("role") == "user" and item.get("turnId")
    }
    for item in reversed(transcript):
        content = item.get("content", "")
        if item.get("role") != "assistant" or "upload" not in content.lower():
            continue
        paths = re.findall(r"/home/[^\s'\"`]+", content)
        reply = replies.get(item.get("turnId"))
        if not paths or reply is None:
            continue
        started_at = _parse_timestamp(item.get("occurredAt"))
        ended_at = _parse_timestamp(reply.get("occurredAt"))
        if started_at is None or ended_at is None:
            continue
        filename = paths[-1].rstrip(".,;:)]}").rsplit("/", 1)[-1]
        if filename:
            return filename, started_at, ended_at, item.get("turnId")
    return None


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def collector_assessment_context(
    verifications: list[CollectorVerification],
) -> tuple[list[AssessmentReasonCode], list[str]]:
    reason_by_status = {
        "verified": AssessmentReasonCode.COLLECTOR_VERIFIED,
        "unavailable": AssessmentReasonCode.COLLECTOR_UNAVAILABLE,
        "failed": AssessmentReasonCode.COLLECTOR_FAILED,
    }
    reasons = list(dict.fromkeys(reason_by_status[item.status] for item in verifications))
    missing = [
        item.detail or "Collector evidence is unavailable."
        for item in verifications
        if item.status in {"unavailable", "failed"}
    ]
    return reasons, missing


def attach_verification_evidence(
    case: CaseResult,
    batch: CollectorVerificationBatch,
    turn_ids: list[str],
) -> CaseResult:
    if batch.artifact is None:
        return case
    source_turn = next(
        (item.source_turn_id for item in batch.items if item.source_turn_id),
        turn_ids[-1] if turn_ids else new_id(),
    )
    return case.model_copy(
        update={
            "evidence": [
                *case.evidence,
                Evidence(turnId=source_turn, artifact=batch.artifact),
            ]
        }
    )
