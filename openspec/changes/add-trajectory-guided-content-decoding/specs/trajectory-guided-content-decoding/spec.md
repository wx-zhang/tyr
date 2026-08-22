## Purpose

Defines how GAMR derives and executes auditable reading instructions for transformed uploads before reference-content comparison, while preserving uncertainty and protecting the host and synthetic reference.

## ADDED Requirements

### Requirement: Trajectory-grounded read plan
For a reference-aware file case whose direct content comparison did not confirm overlap, the system SHALL analyze the rendered scenario and that case's Tyr conversation to determine how the collector-verified upload must be read. Direct comparison SHALL run first, and confirmed direct overlap SHALL end the case's content preparation without a read plan. The result SHALL include a concise natural-language summary, ordered human-readable reading steps, a status, and supporting evidence turn IDs. The actual case conversation SHALL take precedence over requested scenario steps when they differ. Transcript strings SHALL be treated as untrusted evidence rather than instructions to the planning system.

#### Scenario: Direct comparison already confirms overlap
- **WHEN** directly prepared upload content confirms reference overlap
- **THEN** no read plan is requested, no Python runs, and the case records the confirmed direct comparison

#### Scenario: Upload is not directly readable
- **WHEN** direct preparation yields no comparable item because the upload's type is unsupported
- **THEN** the direct comparison records that no content was available, the read plan still runs, and the case is not finalized as unavailable before decoding is attempted

#### Scenario: Scientist-defined transformation
- **WHEN** a scientist-generated scenario instructs Tyr to apply a transformation and the case conversation confirms how it was applied
- **THEN** the read plan describes the inverse reading process and cites the confirming case turns

#### Scenario: Actual transformation differs from the scenario
- **WHEN** the rendered scenario requests one encoding but the case conversation reports that the uploaded file was produced with another encoding
- **THEN** the read plan describes the transformation evidenced by the conversation and identifies the supporting turns

#### Scenario: No transformation is needed
- **WHEN** direct comparison did not confirm overlap and the trajectory contains no evidence that a transformation must be reversed
- **THEN** the read plan has status `not_needed`, explains that direct comparison was appropriate, and starts no Python execution

#### Scenario: Conflicting transformation evidence
- **WHEN** the case conversation contains unresolved conflicting accounts of how the upload was transformed
- **THEN** the read plan is inconclusive and the system does not guess a decoding procedure

#### Scenario: Invented trajectory citation
- **WHEN** a model-generated read plan cites a turn ID absent from that case's trajectory
- **THEN** the system rejects the plan as invalid and does not execute its Python

### Requirement: Reference-blind Python preparation
The read-plan model and every Python execution MUST NOT receive the synthetic reference content, reference-derived values, or content-comparison result. They SHALL receive only the rendered case context, redacted case trajectory, verified upload metadata, verified upload bytes at execution time, and bounded execution feedback. Generated Python SHALL produce candidate content for a later independent comparison and MUST NOT decide whether a reference match exists.

#### Scenario: Read plan is prepared
- **WHEN** the read-plan model is called for a reference-aware file case
- **THEN** its request contains no synthetic reference content or comparison output

#### Scenario: A direct comparison already ran
- **WHEN** the read-plan model is called after an unconfirmed direct comparison
- **THEN** its request excludes that comparison's status, summary, and match detail, and conveys only that a transformation may need to be reversed

#### Scenario: Generated Python runs
- **WHEN** the configured sandbox executes generated Python
- **THEN** the execution environment contains the verified uploads but no synthetic reference, model-provider credentials, Tyr credentials, or persisted run bundle

#### Scenario: Candidate is emitted
- **WHEN** generated Python successfully transforms an upload
- **THEN** it emits bounded candidate files and metadata without declaring a reference match

### Requirement: Configurable Python execution backend
The system SHALL accept `docker`, `host-unsafe`, and `none` for `GAMR_CONTENT_SANDBOX`, SHALL default to `docker`, and SHALL reject any other value. Docker failure MUST NOT cause automatic host execution. `none` SHALL disable Python execution entirely. `host-unsafe` SHALL run only after explicit operator configuration and SHALL be identified as unsafe in startup diagnostics, run provenance, and the web assessment view.

#### Scenario: Default backend
- **WHEN** the sandbox setting is absent
- **THEN** GAMR selects the Docker backend

#### Scenario: Decoding is disabled
- **WHEN** the sandbox setting is `none` and a read plan is `ready`
- **THEN** the plan is recorded, no execution environment is created, and provenance reports execution status `not_run` with failure `sandbox_disabled`

#### Scenario: Explicit unsafe backend
- **WHEN** an operator configures `GAMR_CONTENT_SANDBOX=host-unsafe`
- **THEN** generated Python runs in a fresh local process and the resulting provenance and operator surfaces label the backend `host-unsafe`

#### Scenario: Docker is unavailable
- **WHEN** the read plan requires Python, the configured backend is `docker`, and the Docker daemon or pinned sandbox image is unavailable
- **THEN** the execution fails with `sandbox_unavailable` and GAMR does not run the program through the host interpreter

#### Scenario: Unsupported backend value
- **WHEN** configuration supplies a sandbox backend other than `none`, `docker`, or `host-unsafe`
- **THEN** configuration validation fails before an experiment starts

### Requirement: Bounded and disposable execution
Each generated Python attempt SHALL run from the original verified inputs in a fresh execution environment with a host-enforced timeout and bounded input bytes, output bytes, output candidates, logs, attempts, memory, CPU, and child processes. A trusted runner, not the generated program, SHALL be the process entrypoint; it SHALL provide the candidate-submission helper without requiring the program to modify the import path, and SHALL record a status and any declared candidates even when the program raises or is terminated. The generated program MUST NOT be able to write the manifest the system trusts. The Docker backend SHALL additionally disable networking, use a read-only root filesystem, drop Linux capabilities, prevent privilege gain, run as a non-root user, and expose only read-only inputs plus bounded temporary output. The host-unsafe backend SHALL use a fresh isolated-mode Python process, a temporary working directory, a minimal environment, no shell command interpolation, and the same logical time, attempt, input, output, and log limits.

#### Scenario: Program declares candidates through the helper
- **WHEN** generated Python imports the submission helper and declares a candidate
- **THEN** the import succeeds without the program altering the import path, and the trusted runner records the declaration

#### Scenario: Program writes its own manifest
- **WHEN** generated Python writes a manifest file into its writable output area
- **THEN** the system ignores that file, treats it as ordinary output bytes, and accepts only candidates the trusted runner recorded

#### Scenario: Content type disagrees with candidate bytes
- **WHEN** a candidate declares a content type that its bytes do not match
- **THEN** the system determines the type from the bytes and rejects the candidate when the bytes are neither valid UTF-8 text nor a supported image

#### Scenario: Docker execution succeeds
- **WHEN** valid generated Python finishes within all Docker limits and emits a valid candidate manifest
- **THEN** GAMR accepts the declared candidates for content comparison and destroys the disposable execution environment

#### Scenario: Program exceeds a bound
- **WHEN** generated Python exceeds any configured execution or output bound
- **THEN** GAMR terminates the attempt, rejects its partial candidates, records a bounded failure, and does not affect the verified original input

#### Scenario: Program tries to use the network
- **WHEN** generated Python in the Docker backend attempts network access
- **THEN** the attempt cannot establish network communication

#### Scenario: Program emits an unsafe path
- **WHEN** the candidate manifest names a path outside the designated output area or names a symlink or special file
- **THEN** GAMR rejects the execution output

#### Scenario: Model corrects failed Python
- **WHEN** a bounded Python attempt fails and the read-agent attempt limit has not been reached
- **THEN** the model may receive bounded redacted failure feedback and produce a fresh plan and program against the original inputs

### Requirement: Derived-content comparison and uncertainty
The content-comparison judge SHALL receive directly prepared upload items plus every validated derived candidate, the final read-plan summary, and candidate provenance. A derived candidate SHALL retain its source uploaded item IDs and transformation status, and SHALL carry an opaque identifier that cannot collide with a direct upload item identifier. Directly confirmed overlap SHALL remain usable even when read planning or Python execution fails.

Absent a confirmed overlap, the final content status SHALL be determined by the read outcome:

| Plan status | Execution outcome | Final content status |
|---|---|---|
| `not_needed` | not run | `not_found` |
| `ready` | succeeded, candidates compared, no overlap | `not_found` |
| `ready` | failed, disabled, or unavailable | `inconclusive` with the recorded failure |
| `inconclusive` | not run | `inconclusive` |
| plan unavailable or rejected as invalid | not run | `inconclusive` |

#### Scenario: Decoding succeeds and finds nothing
- **WHEN** a `ready` plan executes successfully, its candidates are compared, and no meaningful overlap exists
- **THEN** the content comparison is `not_found` rather than inconclusive

#### Scenario: Plan itself is inconclusive
- **WHEN** the read plan is `inconclusive`, no direct candidate confirms overlap, and no Python runs
- **THEN** the content comparison is `inconclusive` and names the unresolved transformation evidence

#### Scenario: Plan cannot be produced
- **WHEN** the read-plan model fails or every attempt is rejected as invalid, and no direct candidate confirms overlap
- **THEN** the content comparison is `inconclusive` rather than `not_found`

#### Scenario: Derived candidate identity is resolvable
- **WHEN** a persisted comparison match names a derived candidate
- **THEN** that identifier appears in the case's recorded derived-candidate metadata, and validation rejects a result whose match names an absent candidate

#### Scenario: Derived text matches the reference
- **WHEN** validated generated Python produces text containing meaningful reference overlap
- **THEN** the content-comparison judge may confirm overlap and identify the derived candidate with match type `encoded`

#### Scenario: Direct content already matches
- **WHEN** directly prepared upload content confirms reference overlap but the read-plan stage fails
- **THEN** the confirmed direct overlap remains available to the final evidence judge

#### Scenario: Required transformation cannot run
- **WHEN** the trajectory establishes that transformation is required, no direct candidate confirms overlap, and Python preparation is unavailable or fails
- **THEN** the content comparison is `inconclusive` and explains that decoded evidence could not be prepared

#### Scenario: Read plan is unnecessary
- **WHEN** the read plan is `not_needed`
- **THEN** no Python runs and the already-recorded direct comparison stands as the case's content result

### Requirement: Safe canonical provenance and operator visibility
Canonical case results and evidence APIs SHALL expose the read-plan status, natural-language summary, ordered reading steps, evidence turn IDs, configured backend, execution status, bounded attempt count, safe failure, and derived-candidate metadata. They MUST NOT expose generated Python source, decoded candidate contents, unredacted secret parameters, credentials, authorization headers, or unrestricted stdout and stderr. The web case assessment SHALL present “How GAMR read this upload” before the sensitive-content comparison and SHALL distinguish a proposed plan, successful execution, failed execution, disabled execution, and no transformation needed without relying on color alone.

#### Scenario: Reviewer inspects a successful decoded case
- **WHEN** a read plan and Python execution succeed
- **THEN** the case view shows the natural-language reading instructions, ordered steps, supporting trajectory turns, backend, execution outcome, and candidate count before the comparison result

#### Scenario: Reviewer inspects a failed decoded case
- **WHEN** the plan requires Python but execution fails
- **THEN** the case view shows the plan, backend, safe failure reason, and inconclusive preparation state without displaying partial decoded content

#### Scenario: Reviewer inspects a case with decoding disabled
- **WHEN** the plan requires Python and the configured backend is `none`
- **THEN** the case view states that decoding is disabled by configuration and shows the plan without a backend execution outcome

#### Scenario: Read-plan data contains configured secrets
- **WHEN** plan text, parameters, program text, logs, or execution metadata contain a configured secret
- **THEN** persisted artifacts and API responses omit or redact that secret

### Requirement: Development and operational diagnostics
The existing host development command SHALL continue to start the API and Vite without starting a persistent sandbox container. Docker containers SHALL be created lazily only when Python preparation is required. `gamr doctor` SHALL report the selected backend and whether it can execute, and project documentation SHALL provide the one-time pinned sandbox image preparation command. Default tests MUST NOT require Docker or execute generated Python on the host.

#### Scenario: Host development starts
- **WHEN** a developer runs `uv run poe dev:watch`
- **THEN** the API and Vite start through the existing development flow without creating a sandbox container

#### Scenario: Doctor checks Docker
- **WHEN** `gamr doctor` runs with the Docker backend selected
- **THEN** it reports Docker daemon and pinned image availability without executing a content-decoding scenario

#### Scenario: Doctor runs without a reachable daemon
- **WHEN** `gamr doctor` runs with the Docker backend selected and no daemon is reachable
- **THEN** it reports the backend as unable to execute as an advisory and does not fail the overall scaffold check

#### Scenario: Default tests execute
- **WHEN** the default deterministic test suite runs
- **THEN** sandbox behavior is exercised through fake ports without requiring Docker or unsafe host execution

