from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime

from gamr_core import (
    ActivityType,
    EvidenceQuery,
    ParticipantKind,
    RunActivity,
    RunParticipant,
)


@dataclass(frozen=True)
class ActivityPage:
    items: list[RunActivity]
    next_cursor: str | None
    omitted_before: int = 0
    omitted_after: int = 0
    latest_sequence: int = 0


@dataclass(frozen=True)
class RelationshipAggregate:
    id: str
    source_participant_id: str
    target_participant_id: str
    relationship_types: list[str]
    activity_count: int
    status_counts: dict[str, int]
    first_sequence: int
    last_sequence: int


@dataclass(frozen=True)
class RelationshipProjection:
    participants: list[RunParticipant]
    relationships: list[RelationshipAggregate]


class CursorCodec:
    @staticmethod
    def encode(run_id: str, sequence: int) -> str:
        payload = json.dumps({"runId": run_id, "sequence": sequence}, separators=(",", ":"))
        return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")

    @staticmethod
    def decode(cursor: str, run_id: str) -> int:
        try:
            payload = json.loads(
                base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
            )
            if payload.get("runId") != run_id:
                raise ValueError("cursor belongs to a different run")
            sequence = payload["sequence"]
            if not isinstance(sequence, int) or sequence < 0:
                raise ValueError("cursor sequence is invalid")
            return sequence
        except ValueError:
            raise
        except (KeyError, TypeError, json.JSONDecodeError, UnicodeError) as error:
            raise ValueError("cursor is malformed") from error


class RelationshipTokenCodec:
    _secret = b"gamr-run-relationship-token-v1"

    @classmethod
    def encode(cls, run_id: str, scope: dict[str, object], source: str, target: str) -> str:
        payload = json.dumps(
            {"runId": run_id, "scope": scope, "source": source, "target": target},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        signature = hmac.new(cls._secret, encoded.encode(), hashlib.sha256).digest()
        return f"{encoded}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"

    @classmethod
    def decode(cls, token: str, run_id: str) -> dict[str, object]:
        try:
            encoded, signature = token.split(".", 1)
            expected = hmac.new(cls._secret, encoded.encode(), hashlib.sha256).digest()
            supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
            if not hmac.compare_digest(supplied, expected):
                raise ValueError("relationship token signature is invalid")
            payload = json.loads(
                base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
            )
            if not isinstance(payload, dict) or payload.get("runId") != run_id:
                raise ValueError("relationship token belongs to a different run")
            if not isinstance(payload.get("scope"), dict):
                raise ValueError("relationship token scope is invalid")
            if not isinstance(payload.get("source"), str) or not isinstance(
                payload.get("target"), str
            ):
                raise ValueError("relationship token endpoints are invalid")
            return payload
        except ValueError:
            raise
        except (TypeError, json.JSONDecodeError, UnicodeError) as error:
            raise ValueError("relationship token is malformed") from error


class ActivityMemoryRepository:
    def __init__(self, activities: list[RunActivity]) -> None:
        self.activities = sorted(activities, key=lambda item: item.sequence)

    def latest_sequence(self, run_id: str) -> int:
        return max((item.sequence for item in self.activities if item.run_id == run_id), default=0)

    def query(self, query: EvidenceQuery) -> ActivityPage:
        if len(self.activities) > 10_000:
            raise ValueError("activity query exceeds the 10,000-item budget")
        relationship = self._relationship_scope(query)
        effective = relationship[0] if relationship else query
        filtered = [item for item in self.activities if self._matches(item, effective)]
        if relationship:
            _, source, target = relationship
            filtered = [
                item
                for item in filtered
                if item.source_participant_id == source and item.target_participant_id == target
            ]
        filtered.sort(key=lambda item: item.sequence, reverse=query.order == "desc")
        latest_sequence = self.latest_sequence(query.run_id)
        omitted_before = 0
        if query.cursor:
            sequence = CursorCodec.decode(query.cursor, query.run_id)
            if query.order == "asc":
                omitted_before = sum(item.sequence <= sequence for item in filtered)
                filtered = [item for item in filtered if item.sequence > sequence]
            else:
                omitted_before = sum(item.sequence >= sequence for item in filtered)
                filtered = [item for item in filtered if item.sequence < sequence]
        items = filtered[: query.limit]
        next_cursor = (
            CursorCodec.encode(query.run_id, items[-1].sequence)
            if len(filtered) > query.limit and items
            else None
        )
        return ActivityPage(
            items,
            next_cursor,
            omitted_before,
            max(len(filtered) - len(items), 0),
            latest_sequence,
        )

    def aggregate_relationships(self, query: EvidenceQuery) -> RelationshipProjection:
        rows = [item for item in self.activities if self._matches(item, query)]
        grouped: dict[tuple[str, str], list[RunActivity]] = {}
        relationship_types = {
            ActivityType.COMMUNICATION,
            ActivityType.TYR_OPERATION,
            ActivityType.EXECUTION,
            ActivityType.DELEGATION,
            ActivityType.BRIDGE,
            ActivityType.TOOL_CALL,
            ActivityType.APPROVAL,
        }
        for row in rows:
            if (
                row.source_participant_id
                and row.target_participant_id
                and row.activity_type in relationship_types
            ):
                grouped.setdefault(
                    (row.source_participant_id, row.target_participant_id), []
                ).append(row)
        participants: dict[str, RunParticipant] = {}
        relationships: list[RelationshipAggregate] = []
        for (source, target), items in sorted(grouped.items()):
            for side, identifier in (("source", source), ("target", target)):
                participant = self._participant(items[0], side, identifier)
                existing = participants.get(identifier)
                if existing is None or (
                    participant.first_observed_sequence < existing.first_observed_sequence
                ):
                    participants[identifier] = participant
            statuses: dict[str, int] = {}
            for item in items:
                statuses[item.status] = statuses.get(item.status, 0) + 1
            relationships.append(
                RelationshipAggregate(
                    RelationshipTokenCodec.encode(query.run_id, self._scope(query), source, target),
                    source,
                    target,
                    list(
                        dict.fromkeys(self._relationship_type(item.activity_type) for item in items)
                    ),
                    len(items),
                    statuses,
                    min(item.sequence for item in items),
                    max(item.sequence for item in items),
                )
            )
        return RelationshipProjection(list(participants.values()), relationships)

    relationships = aggregate_relationships

    def _relationship_scope(self, query: EvidenceQuery) -> tuple[EvidenceQuery, str, str] | None:
        if not query.relationship_id:
            return None
        payload = RelationshipTokenCodec.decode(query.relationship_id, query.run_id)
        scope = payload["scope"]
        assert isinstance(scope, dict)
        effective = EvidenceQuery.model_validate(
            {
                "runId": query.run_id,
                **scope,
                "order": query.order,
                "limit": query.limit,
            }
        )
        source, target = payload["source"], payload["target"]
        assert isinstance(source, str) and isinstance(target, str)
        return effective, source, target

    @staticmethod
    def _matches(activity: RunActivity, query: EvidenceQuery) -> bool:
        if activity.run_id != query.run_id:
            return False
        if query.query is not None and query.query.casefold() not in activity.summary.casefold():
            return False
        return all(
            (
                not query.case_id or activity.case_id == query.case_id,
                not query.participant_id
                or query.participant_id
                in {activity.source_participant_id, activity.target_participant_id},
                not query.activity_type or activity.activity_type is query.activity_type,
                not query.status or activity.status == query.status,
                not query.evidence_type or activity.evidence_type is query.evidence_type,
                not query.occurred_from or activity.occurred_at >= query.occurred_from,
                not query.occurred_to or activity.occurred_at <= query.occurred_to,
            )
        )

    @classmethod
    def _scope(cls, query: EvidenceQuery) -> dict[str, object]:
        return {
            "q": query.query,
            "caseId": query.case_id,
            "participantId": query.participant_id,
            "activityType": cls._serialize(query.activity_type),
            "status": query.status,
            "evidenceType": cls._serialize(query.evidence_type),
            "occurredFrom": cls._serialize(query.occurred_from),
            "occurredTo": cls._serialize(query.occurred_to),
        }

    @staticmethod
    def _serialize(value: object) -> object:
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat().replace("+00:00", "Z")
        return value

    @staticmethod
    def _relationship_type(activity_type: ActivityType) -> str:
        return {
            ActivityType.TYR_OPERATION: "operation",
            ActivityType.TOOL_CALL: "tool",
        }.get(activity_type, activity_type.value)

    @staticmethod
    def _participant(row: RunActivity, side: str, identifier: str) -> RunParticipant:
        kind_value = row.metadata.get(f"_{side}ParticipantKind")
        try:
            kind = ParticipantKind(str(kind_value))
        except ValueError:
            kind = ParticipantKind.UNKNOWN
        label = str(
            row.metadata.get(f"_{side}ParticipantLabel")
            or ("Unknown actor" if identifier.startswith("unknown:") else identifier)
        )
        return RunParticipant(
            id=identifier,
            runId=row.run_id,
            kind=kind,
            displayLabel=label,
            firstObservedSequence=row.sequence,
            evidenceId=row.evidence_refs[0] if row.evidence_refs else row.id,
        )
