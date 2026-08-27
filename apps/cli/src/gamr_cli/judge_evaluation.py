from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gamr_adapters.artifacts.filesystem import FilesystemArtifactStore
from gamr_engine.collector_verification import CollectorFile, CollectorVerification
from gamr_engine.content_evidence import AssessmentReference
from gamr_engine.content_source import VerifiedContentSnapshot, assign_opaque_input_path
from gamr_engine.judges.contracts import JudgeRequest, JudgeResult, JudgeRuntime
from gamr_engine.judges.registry import get_judge_pipeline
from gamr_engine.ports.sandbox import Sandbox
from gamr_engine.ports.tracing import TracePort, trace_run, trace_score, trace_span

from .judge_evaluation_debug import DebugSandbox, DebugSink
from .judge_evaluation_models import (
    LoadedAttachment,
    LoadedCase,
    LoadedDataset,
)
from .judge_evaluation_models import (
    load_evaluation_dataset as load_evaluation_dataset,
)
from .judge_evaluation_trace import TracedModel


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
    trace_port: TracePort | None = None,
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
    with trace_run(
        trace_port,
        f"evaluation:{evaluation_id}",
        session_id=evaluation_id,
        trace_id=evaluation_id,
        metadata={"dataset": dataset.source_path, "pipeline": dataset.judge_pipeline},
    ) as run_obs:
        for index, case in enumerate(dataset.cases, 1):
            traced_model.set_case(case.id)
            emit(f"[{index}/{case_count}] {case.id}: started")

            def record_activity(name: str, payload: dict[str, Any], case_id: str = case.id) -> None:
                store.append_event(evaluation_id, {"eventType": name, **payload})
                emit(f"[{case_id}] {name}")

            with trace_span(
                trace_port,
                f"case:{case.id}",
                metadata={"caseId": case.id, "evaluationId": evaluation_id},
            ) as case_obs:
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
                    if case_obs is not None:
                        trace_score(
                            trace_port,
                            "security_verdict",
                            result.verdict.value,
                            observation=case_obs,
                        )
                        trace_score(
                            trace_port,
                            "objective_status",
                            result.objective_status.value,
                            observation=case_obs,
                        )
                        trace_score(
                            trace_port,
                            "assessment_status",
                            result.assessment_status.value,
                            observation=case_obs,
                        )
                        trace_score(
                            trace_port,
                            "evaluation_passed",
                            1.0 if record["passed"] else 0.0,
                            observation=case_obs,
                        )
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
                    if case_obs is not None:
                        trace_score(trace_port, "evaluation_passed", 0.0, observation=case_obs)
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
        if run_obs is not None:
            trace_score(
                trace_port,
                "evaluation_passed",
                1.0 if summary["passed"] else 0.0,
                observation=run_obs,
            )
        store.write_json("summary.json", summary)
        return summary
