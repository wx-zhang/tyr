# Quickstart: Validate Run Evidence Visualization

## Prerequisites

- Python 3.14, uv, Node.js 24 LTS, and pnpm through Corepack.
- No live Tyr, model provider, credentials, or action approval is required. Use deterministic
  redacted fixtures for all validation below.

## Install

```bash
uv sync --all-packages --dev
corepack enable
uv run poe web-install
```

## Contract and model validation

Start with failing tests for the normalized activity contract, stable identity and ordering,
bundle normalization, redaction, confinement, cursor validation, and typed API responses.

```bash
uv run pytest packages/core/tests
uv run pytest packages/adapters/tests
uv run pytest apps/api/tests/test_runs.py
uv run poe schemas
git diff --exit-code -- schemas apps/web/src/api/generated.ts
```

Expected outcomes:

- Duplicate or non-positive run sequences, non-UTC times, unsafe metadata, malformed or cross-run
  cursors, cross-run evidence IDs, path escapes, unpermitted detail, and page limits above 200 are
  rejected.
- Configured secrets, bearer values, authorization fields, idempotency keys, and server paths are
  absent from activity, search, graph, SSE, summary, and content DTOs.
- Finalizing a result does not alter previously retained raw evidence.
- Repeated bundle normalization produces the same view without changing the source bundle.
- Generated OpenAPI contains the contracts summarized in `contracts/run-evidence-api.yaml`.

## API and reconnect scenarios

Use fixtures for a running multi-case run, a completed run, an interrupted run without
`result.json`, a waiting approval, delegated/bridge settling, malformed evidence, and an entirely
redacted detail.

```bash
uv run pytest apps/api/tests
uv run pytest tests
```

Verify:

1. The overview reports exact phase/case counts, pending approvals, and unsettled Tyr work.
2. Literal search and every structured filter remain scoped to one authorized run.
3. Relationship counts use the complete filtered result, and relationship selection pages through
   every contributing permitted activity.
4. `Last-Event-ID` resumes after disconnect with ordered IDs, no duplicates, a bounded backlog, and
   heartbeat behavior.
5. A late delegated or bridge response prevents a false settled state.
6. Missing, malformed, omitted, redacted, and oversized detail states are distinct.
7. Reading a historical run does not modify its bundle.

## Web behavior

```bash
pnpm --dir apps/web test -- --run
pnpm --dir apps/web build
```

Verify with mocked typed API and SSE fixtures:

1. Progress, timeline, relationship graph/list, and inspector synchronize through stable IDs.
2. Exact search and filters preserve overall state and pending approval attention.
3. New activity follows only at the end; inspecting older evidence shows a newer-items count without
   moving focus or scroll position.
4. Reconnect merges snapshot and delta data by ID and sequence without duplicates.
5. The graph and semantic list support keyboard selection, visible focus, and identical evidence
   access; reduced motion removes non-essential animation.
6. Evidence content is absent before explicit reveal and redacted everywhere after reveal, including
   copied and assistive output.
7. Loading, empty, stale, disconnected, terminal, unavailable, and narrow-screen states retain
   meaningful text and navigation.
8. Runs with selected cases are labeled Test cases; runs with an explicit empty case selection and
   enabled scientist iterations are labeled Scientist only. Scientist entries identify the case IDs
   used from history, including the empty-history state. Configure the scientist history window with
   `historyTestRuns` (default 10) and `historyScientistRuns` (default 5); only matching persisted
   terminal runs with result bundles are used.
9. Collector evidence appears chronologically in Updates without a manual page refresh. Verified
   text, Markdown, JSON, XML, CSV, and raster images open in a bounded keyboard-accessible preview;
   retained UTF-8 request bodies appear as request-body artifacts only when their reconstructed byte
   length matches collector metadata and their digest is verified; decoded multipart summaries do
   not invalidate quarantined files, and exact IDs recover files from historical failed manifests;
   unsupported and oversized files remain available only through the run-scoped download. A
   collector redirect, transient transport, 408, 425, 429, or 5xx failure is retried twice;
   redirected reads authenticate again, and exhaustion states the safe operation, attempt count,
   and status or error type without exposing upstream details.

## Scale budget

Run the deterministic 10,000-item fixture. No external service is used.

```bash
uv run pytest tests -k run_evidence_scale
pnpm --dir apps/web test -- --run -t "bounded window"
```

The overview, literal search, filter, selection, and return-to-context interactions each complete
within 2 seconds under the test environment. The repository scale fixture exercises 10,000 bundle
items; the web busy-run test verifies the 200-row DOM bound. The API returns at most 200 activity
rows, and the web page does not place the complete evidence set in the DOM.

## Final checks

```bash
uv run poe check
pnpm --dir apps/web test -- --run
uv run poe schemas
git diff --exit-code -- schemas apps/web/src/api/generated.ts
```

`uv run poe check` does not currently run the web test suite or verify regenerated schema drift, so
the additional commands are required. Do not enable live Tyr/OpenRouter tests or real actions.
