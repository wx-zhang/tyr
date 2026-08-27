## Purpose

Provide explicitly enabled, locally hosted observability for every GAMR model workflow without changing execution outcomes or replacing canonical run evidence.

## ADDED Requirements

### Requirement: Explicit tracing enablement
The system SHALL export Langfuse telemetry only when `GAMR_LANGFUSE_ENABLED` is explicitly true and valid local Langfuse connection settings are configured. Langfuse credentials or an endpoint alone MUST NOT enable telemetry.

#### Scenario: Tracing remains disabled when credentials exist
- **WHEN** Langfuse credentials and an endpoint are configured but `GAMR_LANGFUSE_ENABLED` is false or absent
- **THEN** the system performs the requested GAMR workflow without initializing or exporting Langfuse telemetry

#### Scenario: Tracing is explicitly enabled
- **WHEN** `GAMR_LANGFUSE_ENABLED` is true and valid local Langfuse connection settings are configured
- **THEN** the system exports telemetry for the requested model workflow

### Requirement: Complete model-workflow coverage
When tracing is enabled, the system SHALL trace model calls made by experiment execution, scientist generation, case assessment, trajectory decoding, interactive chat, and judge evaluation workflows.

#### Scenario: Experiment model calls are traced
- **WHEN** an enabled experiment performs agent, scientist, judge, or decoder model calls
- **THEN** every attempted model call is represented as a generation under the corresponding run, case, phase, iteration, or attempt observation

#### Scenario: Non-experiment model calls are traced
- **WHEN** enabled interactive chat or judge evaluation performs model calls
- **THEN** every attempted model call is represented in the corresponding chat or evaluation trace

### Requirement: Hierarchical experiment correlation
The system SHALL create one trace per GAMR experiment run and SHALL nest case and phase observations beneath that run so each model generation is attributable to its run, model role, case or phase, and iteration or attempt where applicable.

#### Scenario: Concurrent runs remain isolated
- **WHEN** two experiment runs execute concurrently
- **THEN** each observation and generation is correlated only with its own run and case hierarchy

#### Scenario: Scientist retry is correlated
- **WHEN** scientist generation retries an invalid or empty completion
- **THEN** each generation is recorded under the same scientist iteration with a distinct one-based attempt identity

### Requirement: Stable session grouping
The system SHALL group a base experiment run and every scientist-resume run derived from it into one Langfuse session. Independent base runs SHALL use distinct sessions. Interactive chat SHALL use its Tyr conversation identity as the session identity, and each judge evaluation invocation SHALL have a stable session identity.

#### Scenario: Scientist resume shares source lineage
- **WHEN** a scientist run resumes from an existing source run
- **THEN** the resumed run trace uses the same session identity as the source run while retaining its own trace and run identity

#### Scenario: Independent run starts a new session
- **WHEN** an experiment is not derived from a source run
- **THEN** its trace does not join the session of another independent base run

### Requirement: Verbatim trusted-operator evidence
When tracing is enabled, the system SHALL export complete model inputs and provider outputs, including prompts, messages, tool-call content, reasoning fields returned by the provider, usage, finish reasons, and failures available at the model boundary. The system SHALL document that the local Langfuse data store contains trusted-operator evidence that may include credentials and authorization values.

#### Scenario: Successful completion retains provider evidence
- **WHEN** a model call returns a completion
- **THEN** the corresponding generation retains the input, complete available provider output, model identity, usage, finish reason, and timing without content masking

#### Scenario: Failed completion retains diagnostics
- **WHEN** a model call raises an error or returns an unusable completion
- **THEN** the corresponding generation records the available request context and failure diagnostics without fabricating output

### Requirement: Outcome score projection
The system SHALL publish categorical Langfuse scores derived from existing GAMR case and run results. Case observations SHALL receive security verdict, objective status, assessment status, and execution outcome scores when those values exist. Run traces SHALL receive the final run outcome.

#### Scenario: Completed case is scored
- **WHEN** a case result reaches its terminal assessment state
- **THEN** its observation receives scores using the exact existing GAMR enum values and no parallel verdict vocabulary

#### Scenario: Completed run is scored
- **WHEN** a run result is finalized
- **THEN** its trace receives the final outcome from that canonical result

### Requirement: Observability failure isolation
Langfuse initialization, observation, scoring, export, and flush failures MUST NOT fail, cancel, retry, or otherwise change a GAMR workflow, model request, approval decision, artifact, result, or exit outcome. The system SHALL expose a bounded local diagnostic when tracing fails.

#### Scenario: Langfuse is unavailable
- **WHEN** tracing is enabled but the configured local Langfuse service cannot be reached
- **THEN** the GAMR workflow completes according to its normal execution semantics and exposes a local tracing diagnostic

#### Scenario: Flush fails during shutdown
- **WHEN** queued telemetry cannot be flushed before a CLI process exits or an API process shuts down
- **THEN** the process preserves the workflow result and reports the tracing failure without changing the workflow exit outcome

### Requirement: Canonical evidence independence
The system SHALL keep canonical tasks, source-controlled prompts, `.gamr` run bundles, result validation, reporting, resume behavior, and evaluation independent of Langfuse data. Deleting or losing Langfuse data MUST NOT make a GAMR workflow artifact unusable.

#### Scenario: Langfuse data is deleted
- **WHEN** the local Langfuse data volume is removed after a run
- **THEN** GAMR can still validate, display, report on, and resume from the canonical artifacts supported by that run

### Requirement: Local deployment options
The project SHALL support both a separately managed local Langfuse endpoint and an optional bundled deployment. The bundled deployment SHALL be opt-in, SHALL bind host-facing services only to loopback, and SHALL retain its data until the operator explicitly deletes the local volumes.

#### Scenario: Bundled deployment is not requested
- **WHEN** the operator starts the standard GAMR development or application stack without the Langfuse option
- **THEN** no bundled Langfuse service is started

#### Scenario: Bundled deployment is requested
- **WHEN** the operator starts the bundled Langfuse option
- **THEN** the Langfuse UI and ingestion endpoint are reachable from the workstation only through loopback and data persists across service restarts

#### Scenario: External local endpoint is configured
- **WHEN** tracing is enabled with a separately managed local Langfuse endpoint
- **THEN** GAMR uses that endpoint without requiring the bundled deployment
