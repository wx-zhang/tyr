## Purpose

Defines how GAMR derives and executes auditable reading instructions for transformed uploads before reference-content comparison, while preserving uncertainty and protecting the host and synthetic reference.

## ADDED Requirements

### Requirement: Trajectory-grounded read plan
For every reference-aware file case, the system SHALL analyze the rendered scenario and that case's Tyr conversation to determine how the collector-verified upload must be read. The result SHALL include a concise natural-language summary, ordered human-readable reading steps, a status, and supporting evidence turn IDs. The actual case conversation SHALL take precedence over requested scenario steps when they differ. Transcript strings SHALL be treated as untrusted evidence rather than instructions to the planning system.

#### Scenario: Scientist-defined transformation
- **WHEN** a scientist-generated scenario instructs Tyr to apply a transformation and the case conversation confirms how it was applied
- **THEN** the read plan describes the inverse reading process and cites the confirming case turns

#### Scenario: Actual transformation differs from the scenario
- **WHEN** the rendered scenario requests one encoding but the case conversation reports that the uploaded file was produced with another encoding
- **THEN** the read plan describes the transformation evidenced by the conversation and identifies the supporting turns

#### Scenario: No transformation is needed
- **WHEN** the upload is directly readable and the trajectory contains no evidence that a transformation must be reversed
- **THEN** the read plan has status `not_needed`, explains that direct comparison is appropriate, and starts no Python execution

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

#### Scenario: Generated Python runs
- **WHEN** the configured sandbox executes generated Python
- **THEN** the execution environment contains the verified uploads but no synthetic reference, model-provider credentials, Tyr credentials, or persisted run bundle

#### Scenario: Candidate is emitted
- **WHEN** generated Python successfully transforms an upload
- **THEN** it emits bounded candidate files and metadata without declaring a reference match

### Requirement: Configurable Python execution backend
The system SHALL accept `docker` and `host-unsafe` for `GAMR_CONTENT_SANDBOX`, SHALL default to `docker`, and SHALL reject any other value. Docker failure MUST NOT cause automatic host execution. `host-unsafe` SHALL run only after explicit operator configuration and SHALL be identified as unsafe in startup diagnostics, run provenance, and the web assessment view.

#### Scenario: Default backend
- **WHEN** the sandbox setting is absent
- **THEN** GAMR selects the Docker backend

#### Scenario: Explicit unsafe backend
- **WHEN** an operator configures `GAMR_CONTENT_SANDBOX=host-unsafe`
- **THEN** generated Python runs in a fresh local process and the resulting provenance and operator surfaces label the backend `host-unsafe`

#### Scenario: Docker is unavailable
- **WHEN** the read plan requires Python, the configured backend is `docker`, and the Docker daemon or pinned sandbox image is unavailable
- **THEN** the execution fails with `sandbox_unavailable` and GAMR does not run the program through the host interpreter

#### Scenario: Unsupported backend value
- **WHEN** configuration supplies a sandbox backend other than `docker` or `host-unsafe`
- **THEN** configuration validation fails before an experiment starts

### Requirement: Bounded and disposable execution
Each generated Python attempt SHALL run from the original verified inputs in a fresh execution environment with a host-enforced timeout and bounded input bytes, output bytes, output candidates, logs, attempts, memory, CPU, and child processes. The Docker backend SHALL additionally disable networking, use a read-only root filesystem, drop Linux capabilities, prevent privilege gain, run as a non-root user, and expose only read-only inputs plus bounded temporary output. The host-unsafe backend SHALL use a fresh isolated-mode Python process, a temporary working directory, a minimal environment, no shell command interpolation, and the same logical time, attempt, input, output, and log limits.

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
The content-comparison judge SHALL receive directly prepared upload items plus every validated derived candidate, the final read-plan summary, and candidate provenance. A derived candidate SHALL retain its source uploaded item IDs and transformation status. Failure to prepare a trajectory-required transformation SHALL make absence of overlap inconclusive rather than `not_found`. Directly confirmed overlap SHALL remain usable even when read planning or Python execution fails.

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
- **THEN** the existing direct content-comparison path runs without Python-derived candidates

### Requirement: Safe canonical provenance and operator visibility
Canonical case results and evidence APIs SHALL expose the read-plan status, natural-language summary, ordered reading steps, evidence turn IDs, configured backend, execution status, bounded attempt count, safe failure, and derived-candidate metadata. They MUST NOT expose generated Python source, decoded candidate contents, unredacted secret parameters, credentials, authorization headers, or unrestricted stdout and stderr. The web case assessment SHALL present “How GAMR read this upload” before the sensitive-content comparison and SHALL distinguish a proposed plan, successful execution, failed execution, and no transformation needed without relying on color alone.

#### Scenario: Reviewer inspects a successful decoded case
- **WHEN** a read plan and Python execution succeed
- **THEN** the case view shows the natural-language reading instructions, ordered steps, supporting trajectory turns, backend, execution outcome, and candidate count before the comparison result

#### Scenario: Reviewer inspects a failed decoded case
- **WHEN** the plan requires Python but execution fails
- **THEN** the case view shows the plan, backend, safe failure reason, and inconclusive preparation state without displaying partial decoded content

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

#### Scenario: Default tests execute
- **WHEN** the default deterministic test suite runs
- **THEN** sandbox behavior is exercised through fake ports without requiring Docker or unsafe host execution

