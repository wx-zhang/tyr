# Test scope

## Purpose

Own cross-package fixtures, integration tests, and smoke tests.

## Standards

Use fake ports by default. Live Tyr/OpenRouter tests are opt-in markers and never run in default CI. Keep fixtures small and deterministic.

## Run-evidence fixtures

`fixtures/run_evidence/<name>/` contains self-contained, redacted bundles for live, completed,
interrupted, malformed, approval, delegation, and bridge scenarios. A bundle may contain
`run.json`, `task.snapshot.json`, `checkpoint.json`, `events.jsonl`, `transcript.jsonl`,
`result.json`, and redacted files under `raw/`. The live, interrupted, approval, delegation, and
bridge bundles intentionally omit a terminal `result.json`. The `malformed` bundle deliberately
marks retained detail as malformed; its raw file is not a valid JSON document so normalizers can
exercise that availability state.

Use the `run_evidence_bundle` fixture from `tests/conftest.py` to resolve a bundle by name. Do not
add credentials, bearer values, authorization headers, configured secret values, server paths, or
idempotency keys to fixtures. Use fixed UTC timestamps and stable IDs. Fixture reads must not write
or rewrite the source bundle.

`test_run_evidence_scale.py` owns the deterministic 10,000-item projection and
bundle-immutability budget. Run `uv run pytest tests -k run_evidence_scale` for
that focused check; the full cross-package suite is `uv run pytest tests`.
Judge graph offline rendering tests live in `tests/test_render_judge_graph.py`.
Decoding runner, loop, prompt, and capacity regressions live in
`packages/engine/tests/test_runner_decoder.py`, `packages/engine/tests/test_decoder_*.py`,
`packages/engine/tests/test_reporting.py`,
`packages/adapters/tests/test_collector_content.py`, and `apps/web/src/features/runs/DecodingProvenance.test.tsx`.
Sandbox contract, backend, and developer-runner regressions live in
`packages/engine/tests/test_sandbox.py`, `packages/adapters/tests/test_sandbox_*.py`,
`packages/engine/tests/test_sandbox_preview.py`, and `tests/test_sandbox_runner.py`. Docker runtime tests use the deselected-by-default
`sandbox_docker` marker and controlled snippets only.
Judge evaluation loader, scoring, trace, and CLI regressions live in
`apps/cli/tests/test_judge_evaluation.py`. The real model-and-Docker evaluation is an explicit
developer job and is never part of default pytest.
Skill helper regressions live in `tests/skills/`.
