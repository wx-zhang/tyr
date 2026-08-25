from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_core import EvaluationPlan
from gamr_engine.collector_verification import CollectorFile, CollectorVerification
from gamr_engine.content_evidence import AssessmentReference
from gamr_engine.content_source import VerifiedContentSnapshot, assign_opaque_input_path
from gamr_engine.judges.contracts import JudgeRequest, JudgeResult, JudgeRuntime
from gamr_engine.judges.registry import get_judge_pipeline
from gamr_engine.ports.sandbox import Sandbox

from .judge_evaluation_debug import DebugSandbox, DebugSink
from .judge_evaluation_models import (
    CaseDocument,
    DatasetDocument,
    LoadedAttachment,
    LoadedCase,
    LoadedDataset,
    LoadedFile,
)
from .judge_evaluation_trace import TracedModel


def _load_bytes(case_root: Path, relative: str, kind: str) -> bytes:
    path = (case_root / relative).resolve()
    if case_root != path and case_root not in path.parents:
        raise ValueError(f"{kind} path escapes case directory")
    if not path.is_file():
        raise ValueError(f"{kind} file is missing: {relative}")
    return path.read_bytes()


def _verified_file(case_root: Path, document: Any, kind: str) -> LoadedFile:
    content = _load_bytes(case_root, document.path, kind)
    if len(content) != document.size:
        raise ValueError(f"{kind} size mismatch: {document.path}")
    if hashlib.sha256(content).hexdigest() != document.sha256:
        raise ValueError(f"{kind} digest mismatch: {document.path}")
    return LoadedFile(document.path, document.filename, document.size, document.sha256, content)


def _load_case(root: Path, document: CaseDocument) -> LoadedCase:
    case_root = (root / "cases" / document.id).resolve()
    if root != case_root and root not in case_root.parents:
        raise ValueError("case path escapes dataset directory")
    reference = _verified_file(case_root, document.reference, "reference")
    try:
        reference_text = reference.content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("reference must be UTF-8 text") from error
    if not reference_text.strip() or "\x00" in reference_text:
        raise ValueError("reference must be non-empty UTF-8 text without NUL bytes")
    attachments = []
    for item in document.attachments:
        loaded = _verified_file(case_root, item, "attachment")
        attachments.append(
            LoadedAttachment(
                path=loaded.path,
                filename=loaded.filename,
                size=loaded.size,
                sha256=loaded.sha256,
                content=loaded.content,
                file_id=item.file_id,
                content_type=item.content_type,
            )
        )
    return LoadedCase(
        id=document.id,
        label=document.label,
        source_run_id=document.source.run_id,
        rationale=document.source.rationale,
        scenario=document.scenario,
        evaluation_plan=EvaluationPlan(prompt=document.evaluation_prompt),
        transcript=document.transcript,
        reference=reference,
        attachments=attachments,
        expectations=[item.model_dump(mode="json") for item in document.expectations],
    )


def load_evaluation_dataset(path: Path) -> LoadedDataset:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        document = DatasetDocument.model_validate(payload)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid evaluation dataset: {error}") from error
    root = path.resolve().parent
    return LoadedDataset(
        judge_pipeline=document.judge_pipeline,
        source_path=str(path),
        cases=[_load_case(root, item) for item in document.cases],
    )


class LocalVerifiedContentSource:
    def __init__(self, attachments: list[LoadedAttachment]) -> None:
        self.attachments = {
            item.file_id: (index, item) for index, item in enumerate(attachments, 1)
        }

    async def fetch_verified_snapshot(self, target: CollectorFile) -> VerifiedContentSnapshot:
        found = self.attachments.get(target.file_id)
        if found is None:
            raise ValueError("evaluation attachment is unavailable")
        index, item = found
        expected = (item.filename, item.content_type, item.size, item.sha256)
        actual = (target.filename, target.content_type, target.size, target.sha256)
        if actual != expected:
            raise ValueError("evaluation attachment metadata mismatch")
        return VerifiedContentSnapshot(
            snapshot_id=assign_opaque_input_path(index),
            source_file_id=item.file_id,
            filename=item.filename,
            content_type=item.content_type,
            size=item.size,
            sha256=item.sha256,
            content=item.content,
        )


def _pointer(payload: Any, pointer: str) -> Any:
    current = payload
    for raw in pointer.removeprefix("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    return current


def compare_expectations(
    actual: dict[str, Any], expectations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    mismatches = []
    for expectation in expectations:
        path = expectation["path"]
        values = expectation["values"]
        value = _pointer(actual, path)
        if value not in values:
            mismatches.append({"path": path, "expected": values, "actual": value})
    return mismatches


def _result_payload(result: JudgeResult) -> dict[str, Any]:
    return {
        "objectiveStatus": result.objective_status.value,
        "verdict": result.verdict.value,
        "summary": result.summary,
        "evidenceTurnIds": result.evidence_turn_ids,
        "assessmentStatus": result.assessment_status.value,
        "assessmentFailure": result.assessment_failure,
        "reasonCodes": [item.value for item in result.reason_codes],
        "missingEvidence": result.missing_evidence,
        "contentOverlap": (
            result.content_overlap.model_dump(by_alias=True, mode="json")
            if result.content_overlap is not None
            else None
        ),
    }


def _request(case: LoadedCase) -> JudgeRequest:
    files = [
        CollectorFile(item.file_id, item.filename, item.content_type, item.size, item.sha256)
        for item in case.attachments
    ]
    verification = CollectorVerification(None, "file", "verified", files, source_turn_id=None)
    scenario = case.scenario
    return JudgeRequest(
        scenario=scenario,
        title=scenario.metadata.title,
        objective=scenario.spec.objective,
        steps=list(scenario.spec.steps),
        success_criteria=scenario.spec.success_criteria or "",
        expected_control=scenario.spec.expected_control,
        transcript=case.transcript,
        turn_ids=[str(item["turnId"]) for item in case.transcript if item.get("turnId")],
        execution_error=None,
        verifications=[verification],
        evaluation_plan=case.evaluation_plan,
        assessment_reference=AssessmentReference(
            case.reference.filename,
            case.reference.content.decode("utf-8-sig"),
            case.reference.sha256,
            case.reference.size,
        ),
    )


async def run_evaluation_dataset(
    dataset: LoadedDataset,
    *,
    model: Any,
    sandbox: Sandbox,
    output_root: Path,
    evaluation_id: str,
    secrets: tuple[str, ...],
    progress: Callable[[str], None] | None = None,
    debug: DebugSink | None = None,
) -> dict[str, Any]:
    if sandbox.isolation != "contained":
        raise ValueError("judge evaluation requires the contained Docker sandbox")
    started_at = datetime.now(UTC)
    emit = progress or (lambda _message: None)
    store = FilesystemArtifactStore(output_root, secrets=secrets)
    traced_model = TracedModel(model, store, evaluation_id, emit, debug)
    runtime_sandbox = DebugSandbox(sandbox, debug) if debug is not None else sandbox
    pipeline = get_judge_pipeline(dataset.judge_pipeline)
    case_summaries = []
    case_count = len(dataset.cases)
    noun = "case" if case_count == 1 else "cases"
    emit(f"Starting {case_count} {noun} with pipeline {dataset.judge_pipeline}")
    for index, case in enumerate(dataset.cases, 1):
        traced_model.set_case(case.id)
        emit(f"[{index}/{case_count}] {case.id}: started")

        def record_activity(
            name: str, payload: dict[str, Any], case_id: str = case.id
        ) -> None:
            store.append_event(evaluation_id, {"eventType": name, **payload})
            emit(f"[{case_id}] {name}")

        try:
            result = await pipeline.run(
                _request(case),
                JudgeRuntime(
                    judge_model=traced_model,
                    verified_content_source=LocalVerifiedContentSource(case.attachments),
                    sandbox=runtime_sandbox,
                    artifacts=store,
                    activity_sink=record_activity,
                    run_id=evaluation_id,
                    case_id=case.id,
                ),
            )
            actual = _result_payload(result)
            mismatches = compare_expectations(actual, case.expectations)
            record = {
                "id": case.id,
                "label": case.label,
                "sourceRunId": case.source_run_id,
                "rationale": case.rationale,
                "passed": not mismatches,
                "expectations": case.expectations,
                "mismatches": mismatches,
                "actual": actual,
            }
        except Exception as error:
            record = {
                "id": case.id,
                "label": case.label,
                "sourceRunId": case.source_run_id,
                "rationale": case.rationale,
                "passed": False,
                "expectations": case.expectations,
                "mismatches": [{"error": type(error).__name__}],
                "actual": None,
            }
        case_summaries.append(record)
        store.write_json(f"cases/{case.id}.json", record)
        status = "PASS" if record["passed"] else "FAIL"
        emit(f"[{index}/{case_count}] {case.id}: {status}")
    finished_at = datetime.now(UTC)
    cases_passed = bool(case_summaries) and all(item["passed"] for item in case_summaries)
    summary = {
        "schemaVersion": "1.0",
        "evaluationId": evaluation_id,
        "judgePipeline": dataset.judge_pipeline,
        "dataset": dataset.source_path,
        "model": traced_model.model,
        "modelCalls": traced_model.calls,
        "modelUsage": traced_model.usage,
        "startedAt": started_at.isoformat().replace("+00:00", "Z"),
        "finishedAt": finished_at.isoformat().replace("+00:00", "Z"),
        "elapsedSeconds": round((finished_at - started_at).total_seconds(), 3),
        "passed": cases_passed and traced_model.calls > 0,
        "cases": [
            {"id": item["id"], "label": item["label"], "passed": item["passed"]}
            for item in case_summaries
        ],
    }
    store.write_json("summary.json", summary)
    return summary
