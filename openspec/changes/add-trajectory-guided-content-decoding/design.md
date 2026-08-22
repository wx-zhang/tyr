## Context

See `proposal.md` for motivation and `specs/trajectory-guided-content-decoding/spec.md` for the behavior contract. The current content pipeline collects verified files, prepares bounded text, images, and safe archive members in memory, calls a structured content-overlap judge, and passes only the overlap result to the final evidence judge. The overlap prompt mentions encodings, but the model receives no trajectory-derived reading procedure and has no execution tool.

The shared engine owns workflow decisions, concrete process and Docker behavior belongs in adapters, and CLI and API must continue to compose the same execution path. Generated code is untrusted. Reference text and decoded contents must remain in memory rather than persisted evidence, while schemas and the UI need enough metadata to explain how a result was reached.

## Goals / Non-Goals

**Goals:**

- Derive an evidence-cited, natural-language method for reading each transformed upload.
- Let a model express novel transformations as Python without giving it the reference answer.
- Execute each attempt through a replaceable engine port with deterministic bounds and explicit backend provenance.
- Preserve direct comparison, conservative uncertainty, and the existing final-judge semantic checks.
- Keep host development commands unchanged and default tests independent of Docker.

**Non-Goals:**

- Giving the decoder Bash, network access, Tyr tools, repository access, or approval powers.
- Searching transformation candidates against the synthetic reference.
- Persisting generated programs or decoded sensitive content.
- Adding a remote sandbox broker, Docker socket mount, Docker-in-Docker, gVisor, or Compose sandbox support in this change.
- Supporting interactive notebooks, arbitrary package installation, or long-lived Python sessions.

## Decisions

### Add a read agent before the content-comparison judge

The case flow becomes:

```text
Tyr execution
  -> collector verification
  -> bounded raw content preparation
  -> trajectory read agent
  -> Python sandbox when needed
  -> augmented content comparison
  -> final evidence judge
```

The agent receives rendered title, objective, ordered steps, success criteria, the case transcript with real turn IDs and observed facts, and uploaded-item metadata. The prompt separates trusted scenario context from untrusted transcript strings and tells the model to reconstruct the transformation actually evidenced by the conversation. Conversation evidence wins when it conflicts with requested steps.

The first structured response contains `status`, `summary`, `steps`, `evidenceTurnIds`, and, when needed, one complete Python program. Plan status is `not_needed`, `ready`, or `inconclusive`. Pydantic validation rejects unknown turn IDs, empty explanations, excess steps, oversized programs, and unexpected fields before execution.

If a program fails, the service may make one correction call containing the original bounded prompt plus redacted exit category and bounded stderr. The corrected response replaces the prior plan and runs against fresh original inputs. Two total model/program attempts match the existing judge recovery convention and avoid an open-ended code loop.

A tool-calling, long-lived code interpreter was considered. It improves exploratory debugging but requires session lifecycle, incremental filesystem state, and a more complex model protocol. One complete program plus one correction retains elasticity for scientist-generated transformations with fewer moving parts.

### Keep the read agent and executor blind to the reference

Only the content-comparison service receives both reference content and prepared upload candidates. The read prompt contains no reference filename content, lines, digest comparison, or earlier overlap result. The sandbox contains only original verified uploads, the generated program, a minimal runner, and temporary output.

This prevents reference-guided brute force and keeps responsibilities separate: the read agent reconstructs evidenced processing, while the comparison judge decides meaningful overlap. A combined decoder-and-comparator agent was rejected because it could repeatedly alter its transformation until it found the target.

### Use a small filesystem protocol rather than a large helper API

Every attempt sees stable paths:

```text
/input/<uploaded-item-id>   verified bytes, read-only
/sandbox/program.py        generated program, read-only
/output/                   bounded writable location
/output/manifest.json      declared candidates
```

The program uses ordinary Python file APIs. A bundled `gamr_sandbox` helper exposes only `submit_candidate(path, content_type, source_item_ids)` to produce the manifest consistently; direct manifest writing remains rejected so the runner controls identifier allocation and validation. Candidate IDs are opaque and stable within the case. The helper enforces neither host safety nor reference separation; the backend boundary does.

Input filenames come from GAMR-generated item IDs, not collector or model text. After execution, the trusted adapter resolves every candidate beneath `/output`, rejects symlinks and special files, caps count and aggregate size, determines hashes, validates declared media types, and returns bytes in memory. Temporary host directories are cleaned in `finally` paths and are never artifact-store paths.

Passing all bytes through JSON stdin was considered, but Base64 expansion and large image payloads complicate limits. Bind-mounted temporary files are simpler and keep program input conventional.

### Define core read provenance separately from in-memory candidate content

Core adds schema-validated result models conceptually shaped as:

```text
ContentReadResult
  plan
    status
    summary
    steps[]
    evidenceTurnIds[]
  execution
    status
    backend
    attemptCount
    failure
    candidates[]

DerivedCandidate
  candidateId
  sourceItemIds[]
  contentType
  kind
  size
  sha256
```

Execution status is `not_run`, `succeeded`, or `failed`. Backend is `docker` or `host-unsafe` only when execution was attempted. Safe failure codes include `sandbox_unavailable`, `timeout`, `resource_limit`, `program_failed`, `invalid_manifest`, `unsafe_output`, and `output_limit`.

The in-memory engine contract pairs each `DerivedCandidate` with its text, image, or bytes for content comparison, but canonical results persist metadata only. Generated Python is represented in diagnostics by a digest and length, never source. Stdout and stderr are reduced to redacted categorical diagnostics and bounded lengths/hashes.

The read result is a sibling of `contentOverlap` on `CaseResult`, not nested inside it. This keeps preparation evidence visible when comparison fails and prevents the final evidence judge from receiving unnecessary plan prose. The content-comparison prompt receives the plan summary and candidate provenance; the final judge continues to receive the validated overlap result only.

### Augment rather than replace direct content preparation

The existing adapter continues to recognize text, images, and safe archives. It also retains bounded verified raw bytes long enough for the sandbox executor. Directly prepared items always go to comparison. Successful derived outputs pass through the same text, image, archive, size, compression-ratio, and NUL checks before becoming comparison items.

If direct content confirms overlap, plan or execution failure cannot erase it. If the trajectory establishes that decoding is required and no direct item confirms overlap, a failed or unavailable sandbox marks the content batch incomplete so `not_found` becomes `inconclusive`. The system does not try unrelated transforms or select among outputs by comparing them with the reference.

### Put backend selection in adapter configuration

`GAMR_CONTENT_SANDBOX` is a strict two-value setting with default `docker`. Composition creates one implementation of an engine `PythonSandbox` port:

- `DockerPythonSandbox` uses `asyncio.create_subprocess_exec` with an argument array and never a shell. It runs a pinned image with no network, a read-only root, all capabilities dropped, no privilege gain, a non-root user, bounded CPU/memory/PIDs, read-only input mounts, and bounded temporary output. The Docker CLI is used initially so existing Docker Desktop contexts and `DOCKER_HOST` configuration work without a Python Docker SDK.
- `HostUnsafePythonSandbox` uses `sys.executable -I -S` in a fresh subprocess with a minimal environment, temporary working directory, host-enforced timeout, bounded pipes, and the same manifest validation. Its name and UI copy state that it is not isolation.

Backend errors never change backend. In particular, Docker unavailability returns `sandbox_unavailable`; it never invokes host Python. Configuration is operator-level, not an experiment override, so completed results record what infrastructure actually ran without letting a scenario weaken isolation.

When the API runs directly through `uv run poe dev:watch`, the Docker adapter invokes the developer's Docker CLI and active daemon context lazily. When the API itself runs in Compose, no host Docker socket is mounted and Docker decoding is unavailable in this initial change. A future remote implementation can satisfy the same port without changing engine behavior.

### Surface the read plan in the existing evaluation update

The engine emits bounded `content_read.started` and `content_read.completed` assessment activities, but the canonical case result remains the source for completed read provenance. Evidence normalization carries `contentRead` into the existing evaluation turn and API DTO. Generated schemas and web client types are regenerated.

The evaluation detail renders a “How GAMR read this upload” region before “Sensitive content comparison.” It shows the natural-language summary, ordered steps, cited turn IDs, backend, execution label, candidate count, and safe failure. `not_needed` states that original content was compared directly. `host-unsafe` always displays an explicit warning. It never renders program source, candidate contents, secret parameters, or raw process logs.

### Keep Docker lazy and validation opt-in

`uv run poe dev:watch` continues to launch only the API and Vite. Add one explicit sandbox image build task used during setup and whenever its pinned definition changes. `gamr doctor` checks configuration, CLI/daemon reachability, image digest, and a non-code-executing runtime probe. A missing runtime does not prevent browsing or cases whose plan is `not_needed`; it fails only a required execution.

Default tests inject fake read models and sandbox ports. A marker-gated Docker integration test exercises isolation flags, input/output behavior, timeout, and cleanup without network or Tyr actions. Host-unsafe execution has focused adapter tests using harmless generated programs and never runs model-produced code in the default suite.

## Risks / Trade-offs

- [Docker containers share the host kernel] -> Use the full hardening profile, pin the image, keep the port replaceable, and leave stronger runtimes such as gVisor for a later change.
- [Host-unsafe code can access the API runtime host] -> Require exact explicit configuration, display persistent warnings and provenance, minimize inherited environment, and never fall back to it.
- [Trajectory text can prompt-inject the read model] -> Separate trust zones in the system prompt, require strict structured output and real turn citations, and expose no reference or privileged tools.
- [Generated Python can conceal a transformation or leak content through logs] -> Deny network in Docker, cap and redact logs, persist only hashes and metadata, and validate all outputs outside the sandbox.
- [A model may hallucinate a plausible but unsupported decoder] -> Require trajectory citations, show the plan to reviewers, prohibit reference-guided selection, and preserve inconclusive outcomes.
- [Temporary bind-mounted inputs briefly exist on disk] -> Use task-owned restrictive temporary directories, never artifact paths, delete them on every exit path, and document the residual local risk.
- [Docker is unavailable inside the current Compose API] -> Report `sandbox_unavailable`; do not mount the host Docker socket or silently use host execution.
- [Arbitrary Python creates non-deterministic resource use] -> Start every attempt fresh and enforce hard time, memory, CPU, PIDs, output, log, and attempt limits.

## Migration Plan

1. Add optional read-result fields so previously completed run bundles and API clients remain readable.
2. Introduce fake ports and core contracts before enabling either concrete executor.
3. Ship the pinned sandbox image definition, build task, Docker adapter, and doctor checks with Docker as the configuration default.
4. Add the explicit host-unsafe adapter and warnings.
5. Enable read planning and derived comparison for reference-aware file cases, then expose the persisted result through API and web surfaces.
6. Regenerate schemas and document that Compose does not yet provide Docker execution.

Rollback disables orchestration of the new optional stage while retaining tolerant readers for `contentRead`; old runs and directly prepared comparisons continue to work.
