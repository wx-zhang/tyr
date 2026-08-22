## 1. Sandbox Output Contract

- [x] 1.1 Add failing engine contract tests for isolation descriptors and attempt-root output collection, covering valid snapshots, unknown and closed IDs, collection during execution, paths outside the requested root, duplicate conflicts, symlinks, special files, invalid UTF-8 names, count and byte limits, and whole-snapshot rejection; run them and confirm the expected failures.
- [x] 1.2 Add failing adapter tests for deterministic Docker collection arguments and archives, no shell interpolation, no-follow traversal, bounded reads, container and host-path exclusion, persistent workspace behavior, and cleanup after collection failure; run them and confirm the expected failures.
- [x] 1.3 Extend the sandbox port with contained, unsafe, and unavailable isolation plus bounded output collection; implement the Docker trusted collector, controlled host collection, and disabled rejection; make focused tests pass.
- [x] 1.4 Add marker-gated Docker runtime tests proving valid binary and nested outputs are collected, earlier attempt roots are excluded, symlinks and special files are rejected, limits are enforced, workspace persists across healthy executions, and no resource survives close or terminal failure.

## 2. Verified Content and Derived Evidence

- [x] 2.1 Add failing engine and adapter tests for one-time verified raw downloads, opaque input assignment, size and digest mismatch rejection, stable checked-file metadata, and absence of collector URLs, credentials, references, and host paths; run them and confirm the expected failures.
- [x] 2.2 Add failing preparation tests for original and derived snapshots covering attempt isolation, source lineage, new opaque item IDs, text, images, archives, empty output, unknown source directories, per-file and total limits, nested archives, decompression ratios, and unsafe-tree rejection; run them and confirm the expected failures.
- [x] 2.3 Implement the verified content-source contract and shared byte-to-evidence preparation so the decoder path downloads once while direct preparation and the existing comparator retain their current behavior; make focused tests pass.
- [x] 2.4 Add regression tests comparing current content preparation before and after refactoring for readable text, images, archives, unsupported content, incomplete batches, conflicting collector metadata, and changed downloads.

## 3. Core Decoding Provenance

- [x] 3.1 Add failing core tests for optional bounded decoding provenance, closed statuses and failure codes, attempt bounds, digest and lineage validation, rejection of secret-bearing or extra fields, serialization aliases, and legacy content results with no decoding data; run them and confirm the expected failures.
- [x] 3.2 Implement decoding provenance models without changing the `evidence-and-content` identifier, omitted-task default, or legacy judge-pipeline provenance; make focused core tests pass.
- [x] 3.3 Add schema tests proving existing task manifests remain unchanged and new and legacy run results validate with and without decoding provenance.

## 4. Judge-Model Decoder Agent

- [x] 4.1 Add failing prompt tests proving the configured judge model receives safe rendered task context, test-case fields, evaluation criteria, the case's agent–Tyr transcript, and opaque upload metadata while excluding the synthetic reference, raw bytes, credentials, unrelated history, collector locations, and host paths; run them and confirm the expected failures.
- [x] 4.2 Add failing critical validation tests for direct decisions, valid `execute_python` calls, malformed arguments, oversized or non-UTF-8 source, unknown or parallel tools, repeated IDs, unknown inputs, invalid final responses, provider errors, and refusal; confirm no rejected response starts a sandbox.
- [x] 4.3 Add failing execution-loop tests for a successful first program, correction in the same healthy workspace, distinct accepted attempt roots, exactly three calls, replacement only after terminal sandbox destruction, immutable inputs, unconditional close, cancellation, timeout, output limiting, infrastructure failure, unsafe isolation, and no host fallback; run them and confirm the expected failures.
- [x] 4.4 Add failing standard-library and secrecy tests proving unavailable imports do not trigger installation and stdout, stderr, exception messages, decoded bytes, generated source, raw tool messages, sandbox IDs, container names, and host paths never enter later model messages or persisted surfaces; run them and confirm the expected failures.
- [x] 4.5 Implement the focused decoder agent, tool parser, coarse feedback mapping, shared-case sandbox lifecycle, attempt-root validation, three-call budget, terminal replacement rule, failure taxonomy, and hash-only provenance in source files below the 300-line gate; make decoder tests pass.

## 5. Existing Evidence-and-Content Graph

- [x] 5.1 Add failing topology tests for the upgraded existing graph's preparation, trajectory-decoding, comparison, execution-failure, evidence-assessment, and finalization paths, including side-effect-free inspection and fresh case state; run them and confirm the expected failures.
- [x] 5.2 Add failing behavior tests for non-applicable cases, direct decisions, decoded text, multiple outputs, base64 and Caesar examples, successful no-overlap, malformed analysis, exhausted attempts, sandbox failures, unsafe outputs, ambiguous lineage, and execution errors with and without verified content; run them and confirm the expected failures.
- [x] 5.3 Add failing boundary tests proving only validated evidence reaches the comparator, only safe overlap reaches the final judge, the reference never reaches the decoder, exact-digest and incomplete-evidence constraints remain intact, and decoder failure never falls back or becomes `not_found`; run them and confirm the expected failures.
- [x] 5.4 Extend `evidence-and-content` in place, reusing focused comparison and final-assessment helpers while preserving its identifier, task selection, existing comparator and final prompts, retries, diagnostics, activities, and canonical assessment fields; make judge tests pass.
- [x] 5.5 Add characterization tests proving non-reference and non-file cases make no decoder call and all existing post-decoder comparison and final-assessment fixtures retain equivalent behavior.

## 6. Global Capacity and Shared Composition

- [x] 6.1 Add failing settings and capacity tests for `GAMR_MAX_CONCURRENT_DECODERS` defaulting to 2, accepting positive integers, rejecting zero, negative, and non-integer values, FIFO admission, waiting without attempt consumption, cross-run bounding, cancellation, terminal failures, cleanup failures, and guaranteed slot release.
- [x] 6.2 Implement one process-wide decoder-capacity gate in shared application composition and hold one slot for each healthy case sandbox lifecycle; make focused concurrency tests pass.
- [x] 6.3 Add failing runner tests proving the upgraded graph receives each base and scientist case's safe task, case, evaluation, and transcript context, preserves case isolation under concurrency, and runs no decoder when evaluation or reference-file conditions do not apply; run them and confirm the expected failures.
- [x] 6.4 Thread the verified content source, secure sandbox, and shared capacity through execution service, runner, `JudgeRuntime`, CLI, API, normal execution, and scientist resume without a second model setting, pipeline identifier, delivery override, or duplicated workflow; make focused tests pass.
- [x] 6.5 Add end-to-end fake-port parity tests for CLI and API, including the existing exfiltration task, a scientist-defined custom transform, persistent correction, terminal replacement, safe failure, cancellation cleanup, and equal calls, provenance, overlap, verdict, reason codes, and missing evidence.

## 7. Evidence, API, Report, and Web

- [x] 7.1 Add failing artifact and normalization tests for decoding provenance, legacy omission, source-to-output lineage, safe failures, configured-secret redaction, malformed history, and proof that generated code, content, process output, exception messages, tool messages, and sandbox identity are never persisted; run them and confirm the expected failures.
- [x] 7.2 Carry safe decoding provenance through canonical results, artifact normalization, query projections, Markdown reports, API DTOs, and generated types while retaining `evidence-and-content` pipeline provenance and excluding transient sensitive values; make backend tests pass.
- [x] 7.3 Add failing web behavior tests for accessible decoding status and bounded lineage beside content comparison, successful, skipped, failed, and legacy states, and absence of code or decoded content at desktop and mobile widths; run them and confirm the expected failures.
- [x] 7.4 Implement decoding presentation using generated types and existing evaluation details without adding a new pipeline label, graph control, or per-run decoder toggle; make web tests pass.

## 8. Schemas, Documentation, and Verification

- [x] 8.1 Regenerate run-result and OpenAPI schemas without adding a judge identifier; add validation fixtures for decoding success and failure provenance and legacy documents; verify a second generation is clean.
- [x] 8.2 Update task, development, sandbox, engine, API, web, `.env.example`, and README documentation with automatic applicable-case analysis, judge-model reuse, three calls in one healthy sandbox, standard-library limits, fail-closed semantics, `GAMR_MAX_CONCURRENT_DECODERS` defaulting to 2, and sensitive-data exclusions.
- [x] 8.3 Update affected `AGENTS.md` source maps, commands, environment tables, and test ownership; keep instruction files within their line limits and preserve every `CLAUDE.md` symlink.
- [x] 8.4 Regenerate `docs/assets/judges/evidence-and-content.png`, prove atomic replacement, and verify it shows the new nodes without executing a case or contacting a model, Tyr, collector, browser, or network.
- [ ] 8.5 Run narrow core, engine judge, sandbox adapter, artifact, API, and web checks while iterating; then run `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`, `uv run poe schemas`, and `uv run poe check`, leaving live services, approvals, and Docker runtime tests opt-in.
