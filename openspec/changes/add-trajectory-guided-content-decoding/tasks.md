## 1. Core Contracts and Configuration

- [ ] 1.1 Add failing core tests for read-plan, read-execution, and derived-candidate enums and models, including valid serialization, every invalid status/backend combination, unsafe or duplicate identifiers, missing evidence, size/count boundaries, extra fields, and loading legacy case results without `contentRead`; run them and confirm the expected failures.
- [ ] 1.2 Add the schema-validated `ContentReadResult` family and optional `contentRead` case-result field with no provider, filesystem, process, or UI concerns; make the focused core tests pass while keeping each source file below 300 lines.
- [ ] 1.3 Add failing adapter configuration tests for Docker defaulting, explicit `host-unsafe`, invalid values, sandbox image identity, and bounded execution settings.
- [ ] 1.4 Add strict `GAMR_CONTENT_SANDBOX` and sandbox limit settings, default to Docker, and compose one sandbox port without fallback; update `.env.example` in the CLI/API scope and make the focused configuration tests pass.

## 2. Read-Plan Agent

- [ ] 2.1 Add failing engine prompt tests proving the read agent receives rendered scenario context, only the owning case trajectory, real turn IDs, observed facts, and uploaded-item metadata while receiving no synthetic reference content, reference-derived values, comparison output, credentials, or unrelated case turns.
- [ ] 2.2 Add failing validation tests for `not_needed`, `ready`, and inconclusive plans; actual-conversation precedence; scientist-generated transformations; unknown evidence turn IDs; empty or oversized summaries, steps, and programs; extra fields; invalid source item IDs; prompt-injection strings; and malformed model responses.
- [ ] 2.3 Introduce a focused read-plan prompt/contract module and service behind structured model ports, treat transcript strings as untrusted evidence, and make the prompt and validation tests pass.
- [ ] 2.4 Add failing recovery tests proving a failed program may cause one redacted correction request, the second plan replaces the first, both executions start from original inputs, and no third model or sandbox attempt occurs.
- [ ] 2.5 Implement the two-attempt read-agent orchestration with bounded categorical execution feedback and hashed diagnostics that never persist program source, decoded content, unrestricted stdout/stderr, or secret parameters; make the recovery tests pass.

## 3. Sandbox Protocol and Output Validation

- [ ] 3.1 Add failing critical-path tests for the sandbox filesystem protocol and `submit_candidate` helper covering read-only stable input IDs, valid text/image/binary candidates, duplicate and unknown sources, missing manifests, malformed JSON, absolute and escaping paths, symlinks, devices/special files, changed files, unsupported media, candidate count, individual and aggregate output limits, stdout/stderr limits, and cleanup after every outcome.
- [ ] 3.2 Define the engine Python-sandbox port, in-memory execution request/result contracts, opaque candidate IDs, and safe failure taxonomy; implement the trusted runner/helper and shared adapter-side manifest validator with no shell parsing, then make every 3.1 rejection and success test pass.
- [ ] 3.3 Add failing redaction tests using secrets in program text, plan steps, paths, stdout, stderr, exception text, and candidate metadata; prove persisted diagnostics and returned safe failures contain no configured secret or decoded candidate content.
- [ ] 3.4 Apply existing redaction at every sandbox diagnostic boundary, persist only program length/hash and bounded execution metadata, and make the focused secrecy tests pass.

## 4. Docker and Host-Unsafe Backends

- [ ] 4.1 Add failing Docker adapter tests for exact argument-array construction, pinned image use, non-root identity, no network, read-only root, dropped capabilities, no privilege gain, private/bounded processes, CPU/memory limits, read-only input/program mounts, bounded temporary output, host timeout, non-zero exits, missing CLI/daemon/image, cancellation, cleanup, and proof that model-controlled text never becomes a Docker option or host path.
- [ ] 4.2 Add a minimal pinned Python sandbox image and implement `DockerPythonSandbox` with asynchronous subprocess execution and no shell, centralized output validation, explicit `sandbox_unavailable`, and no host fallback; make the focused Docker unit tests pass.
- [ ] 4.3 Add failing host-unsafe adapter tests using only static harmless programs to prove `sys.executable -I -S`, a fresh process and temporary directory per attempt, minimal environment, bounded pipes and timeout, cleanup, shared manifest validation, explicit backend provenance, and no shell interpolation.
- [ ] 4.4 Implement `HostUnsafePythonSandbox`, preserve its intentionally unsafe host access semantics, and make the focused tests pass without executing model-produced code in the default suite.
- [ ] 4.5 Add a marker-gated Docker integration test for successful candidate output, blocked network, read-only inputs/root, process and time limits, unsafe-output rejection, and cleanup; keep it excluded from default tests and document its prerequisites.

## 5. Content Pipeline Integration

- [ ] 5.1 Add failing adapter tests proving collector-verified raw bytes remain bounded and available in memory alongside existing prepared text/images/archive members, while mismatched hashes, oversized files, unsafe archives, unsupported content, and preparation errors retain conservative behavior.
- [ ] 5.2 Extend the in-memory content-evidence contract and collector preparation seam for raw verified inputs without persisting copies; reuse existing safe preparation for validated derived candidates and make the focused adapter tests pass.
- [ ] 5.3 Add failing engine integration tests for the full ordering `collector verification -> read plan -> sandbox -> content comparison -> final judge`, `not_needed` skipping Python, scientist-generated encodings, successful text/image/archive-derived candidates, source provenance, and content-judge receipt of the plan summary without program source.
- [ ] 5.4 Add failing uncertainty tests proving direct confirmed overlap survives planning/execution failure, required but unavailable decoding changes absent overlap to inconclusive, failed partial candidates are ignored, unrelated transformations are never tried, and Docker failure never invokes host execution.
- [ ] 5.5 Integrate the read agent and sandbox into the shared content pipeline ahead of comparison, augment direct candidates, pass only validated overlap to the final judge, emit bounded content-read activities, and make the integration and uncertainty tests pass on both normal and scientist cases.
- [ ] 5.6 Split any touched engine or adapter module that would exceed 300 lines and update the nearest `AGENTS.md` source maps for every new seam.

## 6. Evidence, API, and Schemas

- [ ] 6.1 Add failing artifact normalization and recovery tests for successful, unnecessary, inconclusive, recovered, malformed, legacy, and secret-bearing `contentRead` records, including deterministic ordering with content-comparison and final-evaluation updates.
- [ ] 6.2 Persist canonical read provenance and safe diagnostics, normalize it into evaluation turns, preserve legacy bundle reading, and make the focused adapter evidence tests pass without writing generated code or decoded contents.
- [ ] 6.3 Add failing API tests for `contentRead` on run results and paginated turns, including all statuses, derived metadata, legacy omission, backend warnings, redaction, and exclusion of programs, candidate contents, raw logs, credentials, and protected runtime paths.
- [ ] 6.4 Extend API DTOs and mappings with optional read provenance, keep authorization and bundle-confinement behavior unchanged, and make the focused API tests pass.
- [ ] 6.5 Regenerate run-result, operational, OpenAPI, and web client schemas; validate representative legacy, Docker, host-unsafe, unnecessary, successful, and failed result documents.

## 7. CLI, Development, and Operations

- [ ] 7.1 Add failing CLI doctor tests for selected-backend display, Docker CLI/daemon/image availability, explicit host-unsafe warning, invalid configuration, bounded non-executing probes, and no sandbox container creation during ordinary startup.
- [ ] 7.2 Add the doctor checks and one explicit Poe sandbox-image build task, keeping `uv run poe dev:watch` behavior unchanged and avoiding Docker access until a plan requires Python; make the focused CLI tests pass.
- [ ] 7.3 Verify host CLI and host API composition select the same sandbox implementation, and add regression coverage that the current Compose API receives `sandbox_unavailable` for Docker instead of mounting a host socket or using host Python.

## 8. Web Read-Plan Presentation

- [ ] 8.1 Add failing web behavior tests for a “How GAMR read this upload” region before sensitive-content comparison, natural summary, ordered steps, evidence turns, backend, execution outcome, candidate count, safe failure, direct-comparison wording, and a persistent host-unsafe warning that does not rely on color.
- [ ] 8.2 Add failing disclosure and security tests proving generated Python, decoded contents, secret parameters, unrestricted logs, and internal temporary paths never render, while long safe summaries and steps remain bounded and accessible on desktop and mobile.
- [ ] 8.3 Implement the read-plan presentation using generated API types and existing run-history disclosure patterns, split touched files to remain below 300 lines, update `apps/web/AGENTS.md`, and make the focused web tests pass.

## 9. Documentation and Verification

- [ ] 9.1 Update README configuration and command tables, `.env.example`, task-format and development documentation, architecture flow, Docker/Compose limitations, sandbox threat model, operator warnings, setup and opt-in test commands, and relevant root/module `AGENTS.md` files in the same change.
- [ ] 9.2 Add representative Base64, Caesar, chained, custom scientist transformation, conflicting-trajectory, prompt-injection, timeout, unsafe-output, and sandbox-unavailable fixtures without real secrets or live actions.
- [ ] 9.3 Run focused core, engine, adapter, API, CLI, and web tests while iterating; then run schema generation, `uv run poe check`, the complete deterministic web suite, and the marker-gated Docker sandbox integration test when Docker is available.
- [ ] 9.4 Verify the web flow at desktop and 375px-wide mobile viewports for `not_needed`, successful Docker, failed Docker, and host-unsafe results; confirm instructions precede comparison, evidence-turn references are usable, warnings are textual, and no sensitive content appears.
