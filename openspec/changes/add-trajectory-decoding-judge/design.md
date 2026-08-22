## Context

See `proposal.md` for motivation and the three delta specs for the behavior contract.

The current `evidence-and-content` graph asks a content provider to download and prepare verified collector files, sends bounded text or images to `ContentAssessmentService`, and gives only the validated overlap result to the final evidence judge. It already runs for base and scientist cases through the same task-selected path and is explicitly selected by the existing exfiltration task.

The configured judge model supports chat tool calls. The existing Python sandbox accepts immutable input entries and executes bounded standard-library Python. Docker is the only enforceable backend; `host-unsafe` is intentionally not a security boundary. The sandbox returns stdout and stderr but cannot snapshot generated workspace files, and experiment composition does not inject it into judging today.

## Goals / Non-Goals

**Goals:**

- Upgrade the existing content judge instead of adding another pipeline selection.
- Let the configured judge model derive and execute arbitrary Python from task, case, evaluation, and agent–Tyr trajectory context.
- Preserve verified-upload lineage and the existing comparison and final-verdict semantics.
- Keep execution bounded, ephemeral, offline, standard-library-only, and globally capacity-limited.
- Make decoder failures conservative and reviewer-visible through safe structured provenance.

**Non-Goals:**

- A decoder catalog, separate decoder model, shell tool, runtime installation, or general-purpose coding environment.
- Network, Tyr, collector API, host filesystem, reference-content, or approval capabilities for the decoder.
- Persisting or replaying generated programs, decoded files, process output, or agent tool transcripts.
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
```

The deterministic initial payload contains only safe rendered task context, rendered test-case fields, evaluation criteria, the case's agent–Tyr transcript, and opaque verified-upload metadata. The synthetic reference is excluded even if evaluation storage colocates it with other criteria. All supplied strings are labeled untrusted.

The model either returns a validated direct-content decision or calls `execute_python`. Unknown tools, parallel calls, malformed arguments, oversized source, unknown inputs, or invalid final decisions fail safely. The agent may make at most three execution calls. It receives only attempt number, coarse outcome, exit and limit flags, safe failure code, accepted-output count, and output hashes and sizes. Raw stdout, stderr, exception messages, decoded bytes, source, sandbox identity, and private paths are discarded before the next model call.

A separate decoder model was rejected to avoid another configuration and provenance path. Detailed tracebacks were rejected because generated code can place uploaded secrets in exception text.

### Reuse one healthy sandbox across attempts

Acquire decoder capacity and start one Docker sandbox only when the agent makes its first tool call. Mount the verified inputs once and reuse the sandbox workspace for later corrections. Assign every attempt a distinct output root:

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

Add optional decoding provenance beneath the content-overlap result: status, attempt count, safe failure code, program SHA-256 values, limit flags, and derived-file records containing source file ID, opaque item ID, digest, size, and detected content type. Exclude source, content, stdout, stderr, prompts, tool messages, sandbox IDs, container data, and host paths.

Carry the same bounded structure through artifacts, normalized evidence, API, report, and web view. Old results load without it. Program hashes provide audit correlation even though they reveal that two runs used identical generated code; no executable payload is retained.

### Gate decoder sandboxes across runs

Create one process-wide asynchronous capacity gate in shared application composition. Add `GAMR_MAX_CONCURRENT_DECODERS` as a positive integer setting with a default of 2. A case acquires a slot before sandbox start and holds it for the healthy shared sandbox lifecycle. Waiting does not consume an attempt. Cancellation and every start, execution, collection, close, and cleanup outcome release or remove the waiter in a `finally` path.

The gate is distinct from run and case semaphores so concurrent runs cannot multiply Docker usage without a bound. CLI and API use the same configured capacity and gate implementation.

## Risks / Trade-offs

- [Generated Python attempts malicious behavior] -> Require contained Docker isolation, immutable opaque inputs, no network or credentials, fixed resources, and validated output snapshots.
- [Reference leakage manufactures a match] -> Keep reference content outside decoder context, tools, sandbox, diagnostics, and feedback.
- [Persistent workspace contaminates retries] -> Collect only the current engine-issued attempt root and validate its complete snapshot.
- [Trajectory prompt injection broadens authority] -> Treat every task, case, evaluation, and transcript string as untrusted and expose one fixed tool.
- [Coarse feedback lowers correction quality] -> Permit three attempts and stable workspace while never returning raw diagnostics.
- [One upgraded pipeline adds cost to plain files] -> Analyze every applicable case as specified, but allow a validated direct decision to skip sandbox execution.
- [Two runs exhaust Docker resources] -> Hold each active shared case sandbox behind the process-wide capacity gate.
- [Third-party formats remain unsupported] -> Return a safe unavailable-import failure and review image additions separately.

## Migration Plan

1. Extend sandbox and content-source contracts with fakes and rejection tests.
2. Add optional core decoding provenance and regenerate schemas without changing the judge identifier.
3. Build the decoder agent and extend the existing graph behind its current registry entry.
4. Compose the secure sandbox and global capacity through CLI, API, normal execution, and scientist resume.
5. Run the existing exfiltration task through deterministic fake-port coverage and retain its task manifest selection.
6. Update generated graph assets, task, sandbox, engine, API, web, environment, and test documentation.

Rollback removes the decoder stages from `evidence-and-content`; optional result fields keep completed bundles readable. No task manifest, sandbox ID, or decoded artifact needs migration.
