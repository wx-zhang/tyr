# provided-discovery-input Specification

## Purpose
Allow researchers to reuse a complete, operator-supplied discovery target across Experiment runs while preserving deterministic execution, optional recovery, and truthful provenance.

## Requirements

### Requirement: Versioned discovery input document
The system SHALL accept a dedicated discovery-input JSON document with schema version `1.0`, kind `discovery-input`, an informational Task ID, and exactly one candidate containing non-empty `path`, `workspace`, `agent`, and `bridgeId` values. The candidate path SHALL be an absolute child of `/home` without parent traversal. Unsupported versions, incorrect kinds, missing fields, invalid paths, and undeclared fields SHALL be rejected before an Experiment starts.

#### Scenario: Valid complete document
- **WHEN** a researcher supplies a version `1.0` discovery-input document with all required candidate fields and a confined `/home` path
- **THEN** the system accepts the document as a complete provided discovery target

#### Scenario: Incomplete document
- **WHEN** a discovery-input document omits any required candidate field
- **THEN** the system rejects the configuration before creating or starting an Experiment

#### Scenario: Unsafe candidate path
- **WHEN** the supplied candidate path is relative, is outside `/home`, or contains parent traversal
- **THEN** the system rejects the configuration before creating or starting an Experiment

#### Scenario: Informational Task ID differs
- **WHEN** the document's Task ID differs from the Task selected for the Experiment
- **THEN** the system retains and presents the supplied Task ID without rejecting the document or changing the selected Task

### Requirement: CLI discovery input selection
The CLI SHALL provide an optional discovery-input path for `gamr experiment run`. It SHALL read and validate the document before creating the Experiment and SHALL persist the validated content rather than relying on the external path during execution.

#### Scenario: CLI runs with provided input
- **WHEN** a researcher starts an Experiment with a valid local discovery-input path
- **THEN** the resulting Experiment configuration contains the validated document and execution does not depend on the source file remaining available

#### Scenario: CLI input cannot be read
- **WHEN** the discovery-input path does not exist, cannot be read, or does not contain valid JSON
- **THEN** the CLI exits with a validation error before creating the Experiment

### Requirement: Web discovery input selection
The web Experiment Preset form SHALL allow a researcher to select a local JSON discovery-input document, review its Task ID and candidate fields, and store the validated document in the created Experiment Preset. The API SHALL accept the document content and SHALL NOT accept a client-supplied server filesystem path as a substitute.

#### Scenario: Web Preset stores provided input
- **WHEN** a researcher selects a valid discovery-input document and creates an Experiment Preset
- **THEN** the Preset review displays the provided target and each Experiment started from that Preset receives the same validated document

#### Scenario: Web selection is invalid
- **WHEN** the selected file is unreadable, malformed, or fails discovery-input validation
- **THEN** the form reports the error and does not create the Experiment Preset

#### Scenario: API receives a server path
- **WHEN** a client attempts to configure discovery input using a server filesystem path rather than document content
- **THEN** the API rejects the unsupported field

### Requirement: Provided input bypasses live discovery
When an Experiment contains a valid discovery input and fallback is disabled, the system SHALL use the supplied candidate directly, SHALL NOT conduct a discovery model conversation or discovery Tyr interaction, and SHALL begin Scenario Execution with the supplied values. When no discovery input is configured, existing live discovery behavior SHALL remain unchanged.

#### Scenario: Deterministic discovery bypass
- **WHEN** an Experiment has valid discovery input and fallback is disabled
- **THEN** no live discovery turn occurs and Scenario Execution uses the supplied path, workspace, agent, and Bridge ID

#### Scenario: No provided input
- **WHEN** an Experiment has no discovery input
- **THEN** the system performs the Task's configured live discovery flow

#### Scenario: Supplied target fails without fallback
- **WHEN** fallback is disabled and Scenario Execution cannot use the supplied target
- **THEN** the Experiment reports the resulting failure without starting live discovery

### Requirement: Opt-in discovery fallback
The system SHALL expose fallback to live discovery as an option that defaults to disabled and is valid only when discovery input is configured. When enabled, the system SHALL perform a minimal read-only target-availability preflight before any Scenario Execution. A successful preflight SHALL retain the supplied candidate; an unavailable target SHALL start the existing live discovery flow. The preflight SHALL NOT execute Scenario steps or request an action approval.

#### Scenario: Fallback remains disabled by default
- **WHEN** a researcher provides discovery input without enabling fallback
- **THEN** the system performs no target-availability preflight and does not automatically start live discovery

#### Scenario: Provided target passes preflight
- **WHEN** fallback is enabled and the read-only preflight confirms the supplied target is available
- **THEN** the system executes Scenarios with the supplied candidate without running live discovery

#### Scenario: Provided target fails preflight
- **WHEN** fallback is enabled and the read-only preflight cannot confirm the supplied target is available
- **THEN** the system runs normal discovery before starting any Scenario Execution

#### Scenario: Fallback configuration lacks input
- **WHEN** fallback is enabled without a discovery-input document
- **THEN** the system rejects the configuration before creating or starting an Experiment

### Requirement: Discovery provenance remains truthful
The system SHALL persist whether the target was provided, discovered live, or discovered after a failed provided-target preflight. It SHALL represent provided target fields in the discovery result and Experiment history without fabricating model turns, Tyr replies, or evidence turn identifiers. Every actual preflight and fallback discovery interaction SHALL remain traceable in the execution log.

#### Scenario: Provided target is recorded
- **WHEN** the system uses a provided target without live discovery
- **THEN** the run bundle and Experiment history identify the target as provided and contain no fabricated discovery transcript or evidence IDs

#### Scenario: Fallback is recorded
- **WHEN** a preflight fails and live discovery runs
- **THEN** the execution log records the provided-target rejection, each real preflight interaction, and each subsequent live discovery interaction in order

#### Scenario: Scenario prompt uses provided provenance
- **WHEN** Scenario execution receives values from a provided target
- **THEN** the prompt identifies them as operator-provided facts and does not claim they were confirmed by live discovery
