## Context

See `proposal.md` for motivation and the three delta specs for the behavior contract.

The current `evidence-and-content` graph asks a content provider to download and prepare verified collector files, sends bounded text or images to `ContentAssessmentService`, and gives only the validated overlap result to the final evidence judge. It already runs for base and scientist cases through the same task-selected path and is explicitly selected by the existing exfiltration task.

The configured judge model supports chat tool calls. The decoder now uses the Python sandbox, verified collector inputs, output snapshots, and shared composition path, but its first implementation persists only program hashes and terminal status. It does not emit decoder lifecycle activities or retain a reviewer-facing route rationale, source, or execution result. It also advertises and constructs absolute `/workspace/input/...` attachment destinations even though the sandbox accepts relative logical destinations and exposes them below `/input`; the resulting validation error is flattened to `infrastructure_failure` before Docker starts.

## Goals / Non-Goals

**Goals:**

- Upgrade the existing content judge instead of adding another pipeline selection.
- Let the configured judge model derive and execute arbitrary Python from task, case, evaluation, and agent–Tyr trajectory context.
- Preserve verified-upload lineage and the existing comparison and final-verdict semantics.
- Keep execution bounded, ephemeral, offline, standard-library-only, and globally capacity-limited.
- Make routing, executed source, structured results, and decoder failures reviewer-visible through safe structured provenance and canonical run activities.
- Keep decoder prompts, attachment validation, and runtime file access on one input-path contract.

**Non-Goals:**

- A decoder catalog, separate decoder model, shell tool, runtime installation, or general-purpose coding environment.
- Network, Tyr, collector API, host filesystem, reference-content, or approval capabilities for the decoder.
- Replaying generated programs, persisting decoded files, hidden model reasoning, raw tool transcripts, or unsanitized process output.
- A new judge identifier, per-run decoder toggle, example task, API-checking judge, or judge-initiated Tyr conversation.

## Decisions

### Upgrade the existing graph in place

Keep the strict `evidence-and-content` identifier, registry entry, legacy default, and task manifest unchanged. Extend its graph to:

```text
START
  -> prepare_verified_content
  -> decode_trajectory_content
  -> compare_reference_content
  -> route_after_content
       -> preserve_execution_failure -> END
       -> assess_evidence
            -> finalize_judgment -> END
```

Preparation and decoding return neutral state when the case is not a reference-aware file case. The existing comparison, execution-failure, final-assessment, reason-code, diagnostic, and activity behavior remains after the new stage. The repository's exfiltration task exercises this upgraded path through its existing selection; no task schema or pipeline provenance migration is needed.

A separate opt-in pipeline was rejected. The requested behavior is part of the existing content judge, and requiring task migration would leave legacy manifests on the weaker reading path.

### Reuse the judge model with one bounded tool

Add a focused decoder agent in the engine using the configured judge model and one function tool:

```text
execute_python
  source: UTF-8 Python
  rationale: bounded reviewer-facing text
```

The deterministic initial payload contains only safe rendered task context, rendered test-case fields, evaluation criteria, the case's agent–Tyr transcript, and opaque verified-upload metadata. The synthetic reference is excluded even if evaluation storage colocates it with other criteria. All supplied strings are labeled untrusted.

The model either returns a validated direct-content decision or calls `execute_python`. Both routes carry a concise `rationale` field that explains the observable transformation evidence for the choice. The rationale is ordinary bounded model output, not provider reasoning or chain-of-thought. Unknown tools, parallel calls, malformed arguments, oversized source, unknown inputs, missing rationale, or invalid final decisions fail safely. The agent may make at most three execution calls. It receives only attempt number, coarse outcome, exit and limit flags, safe failure code, accepted-output count, and output hashes and sizes. Raw stdout, stderr, exception messages, decoded bytes, sandbox identity, and private paths are never returned to the model.

A separate decoder model was rejected to avoid another configuration and provenance path. Detailed tracebacks were rejected because generated code can place uploaded secrets in exception text.

### Reuse one healthy sandbox across attempts

Acquire decoder capacity and start one Docker sandbox only when the agent makes its first tool call. Give the sandbox relative logical input destinations such as `upload-001/payload.enc`; the Docker backend mounts those immutable bytes at `/input/upload-001/payload.enc`. The prompt, tool validation, generated program, fake sandbox, host developer backend, and Docker backend use this same runtime path. Reuse the sandbox workspace for later corrections and assign every attempt a distinct output root:

```text
/workspace/output/attempt-001/upload-001/<relative-output-path>
```

Only the current attempt directory is collected. Earlier outputs can remain available for debugging but cannot become accepted evidence for a later attempt. The first lineage segment below the attempt root is an engine-issued source identifier, so GAMR infers lineage without trusting a model manifest.

Timeout, output limiting, or uncertain descendant cleanup destroys the sandbox under the existing contract. If attempts remain, the agent may receive one clean replacement sandbox with the same immutable inputs, but prior workspace state is reported unavailable. Every instance closes in a `finally` path and releases its capacity slot.

Fresh sandbox per ordinary attempt was rejected in favor of incremental debugging and lower Docker startup cost. Trusted cleanup was rejected because attempt-specific roots avoid another privileged mutation protocol.

### Keep the fixed standard-library image

Generated programs use the existing Python 3.14 isolated process and standard library. The image exposes no package installer, site packages, or network. An unavailable import maps to coarse execution failure and consumes an attempt; the model receives no package installation tool.

Curated packages were deferred because they add image maintenance and vulnerability scope. Per-run installation conflicts with offline reproducibility and containment.

### Extend the sandbox with output snapshots

Extend the sandbox port with an isolation descriptor and bounded output collection returning immutable `SandboxEntry` values relative to the requested attempt root. Collection is serialized with execution. The Docker image contains a fixed trusted collector that walks with `lstat`, never follows links, accepts regular files and directories only, validates UTF-8 paths, and stops at 256 files or 64 MiB. The host validates the deterministic archive again and rejects the whole snapshot on any unsafe entry.

Keep logical attachment destinations relative at the port boundary and map them below `/input` only inside each backend. Validate this contract before capacity admission or Docker startup. Preserve a safe lifecycle stage—input validation, capacity, startup, execution, collection, output validation, or cleanup—when a failure crosses back into decoder provenance. Do not retain raw Docker commands, daemon messages, container or volume names, or host paths.

Docker reports contained, host reports unsafe, and disabled reports unavailable. The decoder requires contained isolation in engine workflow logic and never falls back to host execution. The developer sandbox command retains its explicit `host-unsafe` mode.

Using stdout as decoded evidence was rejected because it conflates diagnostics and content, reduces binary flexibility, and creates a direct secret channel back to the model.

### Load verified bytes once and prepare derived evidence

Add an engine content-source contract for verified raw files with opaque ID, collector identity, safe metadata, and bytes. The collector adapter downloads each eligible file once, revalidates size and digest, and returns an in-memory snapshot. A shared preparation service converts original snapshots or collected decoder outputs into the existing `ContentEvidenceBatch` rules.

A direct agent decision prepares originals. Successful execution prepares only the current derived snapshot and adds source lineage. The synthetic reference enters only the existing comparator. The final judge still receives only the validated overlap result.

Giving the sandbox a collector client was rejected because it would expose network and credential authority. Downloading on every attempt was rejected because inputs are immutable and already verified.

### Fail closed after decoder-stage failure

Define a closed failure taxonomy covering invalid agent response, unknown tool or input, attempt exhaustion, sandbox unavailable, unsafe isolation, infrastructure failure, timeout, output limit, unavailable import, empty output, invalid output tree, ambiguous lineage, and preparation failure.

Any decoder-stage failure yields an inconclusive content result with checked original-file metadata. It never falls back to original comparison and never produces `not_found`. The original evidence is used only after an explicit valid direct-content decision. This prevents still-encoded data from being misreported as absent.

### Persist detailed safe provenance

Add a route record and ordered attempt records beneath the content-overlap result. The route record contains `action` and bounded `rationale`. Each attempt contains its sequence number, lifecycle stage, redacted executed source, program SHA-256, structured execution result, safe failure category and detail, and collected-output metadata. The structured result contains exit code when available, elapsed duration, timeout and output-limit flags, and explicit stdout and stderr presentation states.

Run generated source and process streams through one artifact sanitizer before constructing persistable models. It applies existing configured-secret and credential redaction, receives case-local verified and derived bytes for content suppression, enforces field bounds, and returns a presentation state of `captured`, `empty`, `redacted`, `suppressed`, or `unavailable`. If the sanitizer cannot prove that a process stream is safe, it suppresses the entire stream. Decoded files remain available only to the comparator and are represented in provenance by hashes, sizes, detected types, and lineage.

Carry the same bounded structure through canonical results, normalized evidence, API, Markdown report, and web view. Retain program hashes beside source for correlation and tamper checks. Treat every new field as additive so old results load without synthesis. The web uses disclosures for rationale, source, and result, labels redacted and suppressed values explicitly, and never relies on color alone.

### Emit decoder lifecycle activities

Emit case-scoped activities for decoder analysis start, route selection, attempt start, attempt completion or failure, and terminal success, skip, or failure. Collector verification precedes analysis; terminal decoding precedes content comparison and final assessment. Activities contain bounded summaries and evidence references into the canonical attempt provenance rather than copies of source or process streams. This keeps SSE, stored history, API recovery, and completed bundles consistent.

### Gate decoder sandboxes across runs

Create one process-wide asynchronous capacity gate in shared application composition. Add `GAMR_MAX_CONCURRENT_DECODERS` as a positive integer setting with a default of 2. A case acquires a slot before sandbox start and holds it for the healthy shared sandbox lifecycle. Waiting does not consume an attempt. Cancellation and every start, execution, collection, close, and cleanup outcome release or remove the waiter in a `finally` path.

The gate is distinct from run and case semaphores so concurrent runs cannot multiply Docker usage without a bound. CLI and API use the same configured capacity and gate implementation.

## Risks / Trade-offs

- [Generated Python attempts malicious behavior] -> Require contained Docker isolation, immutable opaque inputs, no network or credentials, fixed resources, and validated output snapshots.
- [Reference leakage manufactures a match] -> Keep reference content outside decoder context, tools, sandbox, diagnostics, and feedback.
- [Persistent workspace contaminates retries] -> Collect only the current engine-issued attempt root and validate its complete snapshot.
- [Trajectory prompt injection broadens authority] -> Treat every task, case, evaluation, and transcript string as untrusted and expose one fixed tool.
- [Coarse feedback lowers correction quality] -> Permit three attempts and stable workspace while never returning raw diagnostics.
- [Persisted generated source contains a credential copied from trajectory context] -> Apply configured-secret redaction before model validation or artifact writes and retain the source hash for audit correlation.
- [Process output contains uploaded or decoded secrets] -> Suppress the complete stream unless the case-aware sanitizer proves it safe; never use stdout or stderr as decoded evidence.
- [Extra decoder events make run history noisy] -> Use stable lifecycle events, bounded summaries, and collapsed attempt disclosures linked to canonical provenance.
- [Prompt and sandbox input paths diverge] -> Define one relative logical destination mapped to `/input` and exercise the composed decoder path against real Docker.
- [One upgraded pipeline adds cost to plain files] -> Analyze every applicable case as specified, but allow a validated direct decision to skip sandbox execution.
- [Two runs exhaust Docker resources] -> Hold each active shared case sandbox behind the process-wide capacity gate.
- [Third-party formats remain unsupported] -> Return a safe unavailable-import failure and review image additions separately.

## Migration Plan

1. Add failing regressions for relative decoder attachments, composed Docker execution, failure-stage preservation, route rationale, attempt provenance, sanitization, activities, API/report projection, and web presentation.
2. Correct the prompt and attachment contract to relative logical destinations mapped at `/input` and make the Docker decoder regression pass.
3. Extend the optional provenance models and generated schemas with route and attempt records while retaining legacy decoding documents.
4. Persist sanitized source and structured results, emit canonical decoder activities, and carry them through artifacts, reports, API responses, and the web view.
5. Run focused checks, marker-gated Docker integration, schema regeneration, and the repository verification suite.

Rollback may omit the additive route and attempt fields and decoder activities while retaining existing hash-only provenance. Existing completed bundles require no migration and MUST NOT be rewritten. No sandbox ID or decoded artifact is persisted.
