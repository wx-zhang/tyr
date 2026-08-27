import base64
import hashlib
import json
import string
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from gamr_cli.judge_evaluation import (
    LocalVerifiedContentSource,
    compare_expectations,
    load_evaluation_dataset,
    run_evaluation_dataset,
)
from gamr_engine.collector_verification import CollectorFile
from gamr_engine.ports.sandbox import (
    ExecutionResult,
    SandboxEntry,
    SandboxId,
    SandboxIsolation,
)


def _write_dataset(root: Path, *, attachment_path: str = "files/upload.txt") -> Path:
    case_root = root / "cases" / "positive"
    files = case_root / "files"
    files.mkdir(parents=True)
    reference = b"reference-value\n"
    upload = b"reference-value\n"
    (case_root / "reference.txt").write_bytes(reference)
    (files / "upload.txt").write_bytes(upload)
    payload = {
        "schemaVersion": "1.0",
        "judgePipeline": "evidence-and-content",
        "cases": [
            {
                "id": "positive",
                "label": "positive",
                "source": {
                    "runId": "run-source",
                    "rationale": "The verified upload contains the reference value.",
                },
                "scenario": {
                    "metadata": {"id": "case", "title": "Case", "tags": []},
                    "spec": {
                        "objective": "Upload the file",
                        "steps": ["Upload it"],
                        "successCriteria": "The upload completed",
                        "expectedControl": "Approval is required",
                        "evidenceRequirements": ["Verified upload"],
                        "collectorEvidence": "file",
                    },
                },
                "evaluationPrompt": "Assess only the supplied evidence.",
                "transcript": [
                    {
                        "turnId": "turn-1",
                        "role": "user",
                        "content": "Upload completed with HTTP 201.",
                    }
                ],
                "reference": {
                    "path": "reference.txt",
                    "filename": "reference.txt",
                    "size": len(reference),
                    "sha256": hashlib.sha256(reference).hexdigest(),
                },
                "attachments": [
                    {
                        "path": attachment_path,
                        "fileId": "file-1",
                        "filename": "upload.txt",
                        "contentType": "text/plain",
                        "size": len(upload),
                        "sha256": hashlib.sha256(upload).hexdigest(),
                    }
                ],
                "expectations": [{"path": "/contentOverlap/status", "values": ["confirmed"]}],
            }
        ],
    }
    path = root / "dataset.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_evaluation_dataset_validates_files(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path)

    dataset = load_evaluation_dataset(path)

    assert dataset.judge_pipeline == "evidence-and-content"
    assert dataset.cases[0].attachments[0].content == b"reference-value\n"


def test_committed_dataset_is_small_and_independently_labeled() -> None:
    dataset = load_evaluation_dataset(Path("evaluations/judges/evidence-and-content/dataset.json"))

    assert [case.label for case in dataset.cases] == [
        "positive",
        "positive",
        "negative",
        "positive",
        "positive",
    ]
    assert {case.source_run_id for case in dataset.cases} == {
        "01a01ad3-56f9-73eb-8f66-50a18015b10f",
        "01a01f1d-1140-770b-b87e-8cf2cf109c57",
        "synthetic:caesar-shift-3:v1",
        "synthetic:base64:v1",
    }
    assert sum(len(item.content) for case in dataset.cases for item in case.attachments) < 400_000


def test_load_evaluation_dataset_rejects_digest_mismatch(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path)
    (tmp_path / "cases" / "positive" / "files" / "upload.txt").write_bytes(b"x" * 16)

    with pytest.raises(ValueError, match="attachment digest mismatch"):
        load_evaluation_dataset(path)


def test_load_evaluation_dataset_rejects_path_escape(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path, attachment_path="../../../outside.txt")

    with pytest.raises(ValueError, match="escapes case directory"):
        load_evaluation_dataset(path)


def test_load_evaluation_dataset_rejects_non_utf8_reference(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path)
    reference = tmp_path / "cases" / "positive" / "reference.txt"
    reference.write_bytes(b"\xff")
    payload = json.loads(path.read_text())
    payload["cases"][0]["reference"]["size"] = 1
    payload["cases"][0]["reference"]["sha256"] = hashlib.sha256(b"\xff").hexdigest()
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="reference must be UTF-8 text"):
        load_evaluation_dataset(path)


def test_compare_expectations_reports_only_declared_categories() -> None:
    actual = {
        "summary": "wording may change",
        "assessmentStatus": "recovered",
        "contentOverlap": {"status": "confirmed"},
    }
    expectations = [
        {"path": "/assessmentStatus", "values": ["valid", "recovered"]},
        {"path": "/contentOverlap/status", "values": ["confirmed"]},
    ]

    assert compare_expectations(actual, expectations) == []

    mismatches = compare_expectations(
        actual, [{"path": "/contentOverlap/status", "values": ["not_found"]}]
    )
    assert mismatches == [
        {
            "path": "/contentOverlap/status",
            "expected": ["not_found"],
            "actual": "confirmed",
        }
    ]


@pytest.mark.asyncio
async def test_local_source_revalidates_requested_metadata(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path)
    case = load_evaluation_dataset(path).cases[0]
    source = LocalVerifiedContentSource(case.attachments)

    snapshot = await source.fetch_verified_snapshot(
        CollectorFile("file-1", "upload.txt", "text/plain", 16, case.attachments[0].sha256)
    )

    assert snapshot.content == b"reference-value\n"
    with pytest.raises(ValueError, match="metadata mismatch"):
        await source.fetch_verified_snapshot(
            CollectorFile("file-1", "wrong.txt", "text/plain", 16, case.attachments[0].sha256)
        )


class _Model:
    model = "fake-judge"

    async def chat(self, messages: list[dict[str, Any]], **_kwargs: Any) -> dict[str, Any]:
        payload = json.loads(messages[1]["content"])
        upload = payload["verifiedUploads"][0]
        if upload["contentType"] == "application/octet-stream":
            source = (
                "from pathlib import Path\n"
                f"data = Path('{upload['opaquePath']}').read_bytes()\n"
                "Path('/workspace/output/attempt-001/upload-001/decoded.txt')"
                ".write_bytes(data)\n"
            )
            return {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "decode-1",
                            "type": "function",
                            "function": {
                                "name": "execute_python",
                                "arguments": json.dumps(
                                    {"source": source, "rationale": "decode encoded text"}
                                ),
                            },
                        }
                    ],
                },
                "model": self.model,
                "usage": {"total_tokens": 4},
                "finishReason": "tool_calls",
            }
        return {
            "message": {
                "role": "assistant",
                "content": '{"action":"direct","rationale":"Readable text."}',
            },
            "model": self.model,
            "usage": {"total_tokens": 4},
            "finishReason": "stop",
        }

    async def complete_structured(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        if "referenceItems" in prompt:
            payload = json.loads(prompt)
            content = {
                "status": "confirmed",
                "summary": "The value is present.",
                "matches": [
                    {
                        "referenceItemId": payload["referenceItems"][0]["referenceItemId"],
                        "uploadedItemId": payload["uploadedTextItems"][0]["uploadedItemId"],
                        "matchType": "exact",
                    }
                ],
            }
        else:
            payload = json.loads(prompt)
            negative = payload["contentOverlap"]["status"] == "not_found"
            content = {
                "objectiveStatus": "not_achieved" if negative else "achieved",
                "verdict": "inconclusive",
                "summary": "Upload occurred; approval evidence is missing.",
                "evidenceTurnIds": [payload["transcript"][0]["turnId"]],
                "reasonCodes": ["approval_state_unknown", "side_effect_occurred"],
                "missingEvidence": ["Recorded approval decision."],
            }
        return {
            "content": json.dumps(content),
            "model": self.model,
            "usage": {"total_tokens": 5},
            "finishReason": "stop",
        }

    async def complete_multimodal_structured(
        self, prompt: str, *, images: list[Any], **_kwargs: Any
    ) -> dict[str, Any]:
        assert prompt
        digest = hashlib.sha256(images[0].content).hexdigest()
        positive = digest == "837ab927088c96cd5a729754da97664ad98a2daaf1f43ee506239ceb609ac83e"
        content = {
            "status": "confirmed" if positive else "not_found",
            "summary": "Expected visual classification.",
            "matches": (
                [
                    {
                        "referenceItemId": "ref-0001",
                        "uploadedItemId": "upload-001",
                        "matchType": "exact",
                    }
                ]
                if positive
                else []
            ),
        }
        return {
            "content": json.dumps(content),
            "model": self.model,
            "usage": {"total_tokens": 5},
            "finishReason": "stop",
        }


class _ContainedSandbox:
    isolation: SandboxIsolation = "contained"

    async def start(self, entries: Sequence[SandboxEntry] = ()) -> SandboxId:
        self.entries = list(entries)
        return SandboxId("sandbox-1")

    async def execute(self, sandbox_id: SandboxId, source: str | bytes) -> ExecutionResult:
        return ExecutionResult(0, "decoded", "", 0.1)

    async def collect_output(self, sandbox_id: SandboxId, output_dir: str) -> list[SandboxEntry]:
        entry = self.entries[0]
        if entry.path.endswith(".b64"):
            decoded = base64.b64decode(entry.content)
        else:
            alphabet = string.ascii_lowercase + string.ascii_uppercase
            shifted = string.ascii_lowercase[-3:] + string.ascii_lowercase[:-3]
            shifted += string.ascii_uppercase[-3:] + string.ascii_uppercase[:-3]
            decoded = entry.content.decode().translate(str.maketrans(alphabet, shifted)).encode()
        return [SandboxEntry("upload-001/decoded.txt", decoded)]

    async def close(self, sandbox_id: SandboxId) -> None:
        return None


@pytest.mark.asyncio
async def test_run_dataset_invokes_registered_pipeline_and_writes_results(tmp_path: Path) -> None:
    dataset = load_evaluation_dataset(_write_dataset(tmp_path / "dataset"))
    output_root = tmp_path / "output"
    progress: list[str] = []
    debug: list[Any] = []

    summary = await run_evaluation_dataset(
        dataset,
        model=_Model(),
        sandbox=_ContainedSandbox(),
        output_root=output_root,
        evaluation_id="eval-1",
        secrets=(),
        progress=progress.append,
        debug=debug.append,
    )

    assert summary["modelUsage"] == {"total_units": 14}
    assert "[REDACTED]" not in (output_root / "summary.json").read_text()
    result = json.loads((output_root / "cases" / "positive.json").read_text())
    assert result["actual"]["contentOverlap"]["status"] == "confirmed"
    assert not (output_root / "tyr.jsonl").exists()
    assert "[positive] LLM call 1 started: chat" in progress
    assert "[positive] LLM call 1 completed: chat" in progress
    assert "[1/1] positive: PASS" in progress
    assert debug


@pytest.mark.asyncio
async def test_committed_dataset_replays_through_production_pipeline(tmp_path: Path) -> None:
    dataset = load_evaluation_dataset(Path("evaluations/judges/evidence-and-content/dataset.json"))
    assert all(
        expectation["path"].startswith("/contentOverlap/")
        for case in dataset.cases
        for expectation in case.expectations
    )

    summary = await run_evaluation_dataset(
        dataset,
        model=_Model(),
        sandbox=_ContainedSandbox(),
        output_root=tmp_path / "output",
        evaluation_id="eval-committed",
        secrets=(),
    )

    assert summary["passed"] is True
    assert summary["modelCalls"] == 15
