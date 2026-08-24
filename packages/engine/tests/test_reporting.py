from datetime import UTC, datetime

from gamr_core import (
    AssessmentStatus,
    CaseResult,
    ContentOverlapResult,
    ContentOverlapStatus,
    DecodingAttempt,
    DecodingExecutionResult,
    DecodingProvenance,
    DecodingStatus,
    DecodingStream,
    Evidence,
    ExecutionOutcome,
    ExperimentConfig,
    ResultSummary,
    RunResult,
    SecurityVerdict,
    TaskReference,
)
from gamr_engine.reporting import render_markdown


def test_report_includes_safe_decoder_route_code_result_and_lineage() -> None:
    digest = "a" * 64
    decoding = DecodingProvenance(
        status=DecodingStatus.SUCCEEDED,
        action="execute",
        rationale="Bearer report-secret at /home/alice/input needs decoding.",
        attemptCount=1,
        programSha256=[digest],
        attempts=[
            DecodingAttempt(
                attempt=1,
                stage="output_validation",
                source="print('report-secret from /home/alice/input')",
                programSha256=digest,
                execution=DecodingExecutionResult(
                    exitCode=0,
                    elapsedSeconds=0.125,
                    stdout=DecodingStream(state="captured", value="Bearer report-secret"),
                    stderr=DecodingStream(state="empty"),
                ),
            )
        ],
    )
    result = RunResult(
        runId="run-report",
        task=TaskReference(id="task", version="1.0", digest="sha256:" + "b" * 64),
        startedAt=datetime.now(UTC),
        outcome=ExecutionOutcome.COMPLETED,
        configuration=ExperimentConfig(),
        summary=ResultSummary(vulnerable=0, protected=1, inconclusive=0),
        cases=[
            CaseResult(
                scenarioId="case-1",
                outcome=ExecutionOutcome.COMPLETED,
                verdict=SecurityVerdict.PROTECTED,
                summary="Protected",
                evidence=[Evidence(turnId="turn-1", artifact="raw/turn-1.json")],
                contentOverlap=ContentOverlapResult(
                    status=ContentOverlapStatus.NOT_FOUND,
                    assessmentStatus=AssessmentStatus.VALID,
                    matches=[],
                    decoding=decoding,
                ),
            )
        ],
        findings=[],
        errors=[],
    )

    report = render_markdown(result)

    assert "route `execute`" in report
    assert "Bearer report-secret at /home/alice/input needs decoding." in report
    assert "Executed source" in report
    assert "print('report-secret from /home/alice/input')" in report
    assert f"program `{digest}`" in report
    assert "Result: exit `0`" in report
    assert "stdout `captured`" in report
