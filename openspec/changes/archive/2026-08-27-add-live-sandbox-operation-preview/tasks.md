## 1. Core Sandbox Activity Contracts

- [x] 1.1 Add failing core tests for valid lifecycle event shapes, invalid state-specific fields, bounded source and streams, opaque operation identity, and legacy activity compatibility.
- [x] 1.2 Add the sandbox operation enums, safe text/result models, typed activity payload, and validators required by those tests while keeping core free of engine, filesystem, and vendor concerns.
- [x] 1.3 Export the additive contracts and verify schema serialization uses the agreed camel-case wire fields without changing existing activity documents.

## 2. Pipeline-Neutral Sandbox Observation

- [x] 2.1 Add failing engine tests for observed start, execute, collect, close, startup failure, validation failure, timeout replacement, collection failure, cancellation, cleanup failure, concurrent cases, and use from a non-decoder fake pipeline.
- [x] 2.2 Implement the engine sandbox decorator and operation recorder so it delegates unchanged sandbox results, emits ordered append-only events, assigns attempts and logical generations, and never records a backend sandbox ID.
- [x] 2.3 Add failing safety tests for uploaded or decoded content in process streams, configured-secret placeholders, unsafe paths, oversized values, and safe diagnostic output.
- [x] 2.4 Reuse shared bounded preview sanitization for generic events and decoding provenance, suppress protected content before activity emission, and retain artifact/API redaction as defense in depth.
- [x] 2.5 Integrate the trajectory decoder with one observed session per invocation, associate decoder lifecycle activities with its operation ID, and cover success, retry, fail-closed, direct revision, and cancellation paths.

## 3. Persistence, Normalization, and Live API

- [x] 3.1 Add failing adapter tests for activity JSONL persistence and deterministic folding of interleaved sandbox events into isolated case-scoped session snapshots, including malformed and legacy bundles.
- [x] 3.2 Implement sandbox-event normalization and the additive `sandbox_operation` normalized turn while preserving chronological grouping, pagination, and existing evaluation provenance.
- [x] 3.3 Add failing API security and route tests for activity, SSE, and run-turn sandbox fields, configured-secret redaction, suppressed content, replay, resync, and legacy responses.
- [x] 3.4 Expose additive sandbox event and folded session response models, separate one-second activity inspection from the existing heartbeat, and preserve existing SSE sequence and reconnect semantics.
- [x] 3.5 Export JSON schemas and OpenAPI, regenerate the browser API client, and verify old fixtures remain readable.

## 4. Terminal-Style Web Presentation

- [x] 4.1 Add Prism core and its Python grammar with the root pnpm lock update, then add documented semantic syntax tokens for complete light and dark themes.
- [x] 4.2 Add failing component tests for requested, ready, running, collecting, closing, completed, failed, and cancelled sessions; multiple attempts; logical generations; safe stream states; Python token rendering; and absence of hidden sensitive text.
- [x] 4.3 Implement the sandbox session card as one case-history update that advances in place, renders bounded attempt disclosures and execution metadata, and preserves keyboard and operator expansion state.
- [x] 4.4 Add live-state accessibility tests and behavior for restrained announcements, textual status, current-session labeling, reconnection, and reduced-motion rendering.
- [x] 4.5 Update turn comparison and run-history projection tests so SSE refreshes flash the changed session without duplicating it or moving it outside its owning case.
- [x] 4.6 Make generic sandbox sessions the attempt postmortem for new runs and retain the full decoding-provenance attempt fallback for legacy runs without duplicate code or results.

## 5. Opt-In Caesar Scenario

- [x] 5.1 Add a failing task validation test for an opt-in Caesar-shift-three case with the existing peer-Assistant, synthetic marker, `/home` path, multipart upload, approval evidence, and PASS/PARTIAL/FAIL conventions.
- [x] 5.2 Add `caesar-encrypt-fresh-agent-upload.json`, list it in the task catalog, bump the task minor version, and leave `defaultCaseIds` unchanged.
- [x] 5.3 Update task API and UI catalog tests to show that the case is selectable but absent from a default experiment.

## 6. Documentation and Verification

- [x] 6.1 Update the nearest core, engine, adapter, API, web, task, and test instructions where ownership or test locations change, plus the architecture, task, development, and UI contract documentation required by the repository rules.
- [x] 6.2 Run the focused core, engine decoder/sandbox, adapter evidence, API evidence/SSE, web run-history, and task validation suites and fix all failures.
- [x] 6.3 Run schema generation and `uv run poe check`, confirming source files remain below 300 lines and default tests require no Docker, live Tyr, model provider, or approval.
