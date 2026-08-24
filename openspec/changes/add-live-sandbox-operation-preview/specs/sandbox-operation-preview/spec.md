## Purpose

Defines safe, reusable capture and presentation of judge-owned sandbox progress as live case activity and persistent postmortem evidence.

## ADDED Requirements

### Requirement: Canonical sandbox operation lifecycle
GAMR SHALL record judge-owned sandbox work as append-only, case-scoped operation events sharing one opaque operation identifier for the logical session. The lifecycle SHALL distinguish a sandbox request, readiness, each execution start and result, output collection, cleanup, and a terminal completed, failed, or cancelled outcome. Events SHALL describe the operation actually attempted and MUST NOT claim that code executed when startup or validation failed. A replacement sandbox created after a timeout or output-limit destruction SHALL remain in the same logical session with a new bounded generation number. The persisted operation identifier MUST NOT be a backend sandbox, container, volume, host-process, or filesystem identifier.

#### Scenario: One execution succeeds
- **WHEN** a judge requests a sandbox, executes Python, collects accepted output, and closes the sandbox
- **THEN** the session records the ordered request, readiness, execution, collection, cleanup, and completed states under one opaque operation identifier

#### Scenario: Sandbox startup fails
- **WHEN** a validated program is available but sandbox startup fails
- **THEN** the session records the requested program as not executed, the safe startup failure, and one failed terminal outcome

#### Scenario: Timeout requires replacement
- **WHEN** an execution timeout destroys a sandbox and a later attempt starts a replacement
- **THEN** both attempts remain in one session and identify distinct logical generations without exposing either backend sandbox identifier

#### Scenario: Run is cancelled during execution
- **WHEN** a judge-owned sandbox operation is cancelled
- **THEN** cleanup is attempted and the session records one cancelled terminal outcome after the last observed cleanup state

### Requirement: Pipeline-neutral operation observation
The sandbox-operation lifecycle SHALL be reusable by any predefined judge pipeline that receives the shared sandbox capability. Observation MUST NOT change sandbox execution results, containment, capacity, validation, or cleanup semantics, and MUST NOT require a decoder-specific event name or result type. Concurrent cases and pipelines SHALL receive independent operation identifiers and state.

#### Scenario: Another judge pipeline uses the preview
- **WHEN** a predefined judge pipeline other than trajectory decoding executes Python through the observed sandbox capability
- **THEN** its case receives the same canonical sandbox-operation lifecycle without depending on decoder models or provenance

#### Scenario: Concurrent cases execute sandboxes
- **WHEN** two cases execute judge-owned Python concurrently
- **THEN** their progress remains isolated by case and operation identifier and neither session consumes the other's attempts or terminal state

### Requirement: Safe bounded preview evidence
Every persisted or browser-visible sandbox preview SHALL bound Python source to 64 KiB and each stdout and stderr value to 16 KiB. Configured secrets, authorization material, host paths, sandbox identities, uploaded content, and decoded content MUST NOT be exposed. A stream that cannot be proven safe SHALL be represented as suppressed rather than captured. Preview text SHALL distinguish captured, empty, redacted, suppressed, and unavailable states. Redaction SHALL occur before durable activity persistence and SHALL be applied again at the browser delivery boundary. Raw unsanitized process output MUST remain unavailable to the browser.

#### Scenario: Program prints uploaded content
- **WHEN** generated Python writes uploaded or decoded file content to stdout or stderr
- **THEN** the affected stream is persisted and presented as suppressed while safe exit, duration, and limit fields remain visible

#### Scenario: Program contains a configured secret
- **WHEN** source or process output contains a configured secret or authorization value
- **THEN** the persisted activity, SSE payload, API response, accessible text, and copied browser content contain only a redaction marker

#### Scenario: Safe diagnostic output completes
- **WHEN** bounded process output contains no protected content, secret, unsafe path, or sandbox identity
- **THEN** the preview may present the sanitized value and labels it as captured

### Requirement: Live and postmortem API projection
GAMR SHALL expose sandbox sessions as additive run updates owned by their case. New lifecycle events SHALL become discoverable to a connected run view while the run remains active without waiting for the terminal judge result. The activity stream SHALL check for new persisted activity at least once per second while preserving ordered replay, stable sequence handling, heartbeat, reconnect, and resynchronization behavior. The run-turn projection SHALL fold events sharing an operation identifier into one current session snapshot. Existing clients and historical bundles without sandbox-operation fields SHALL remain readable.

#### Scenario: Active execution advances
- **WHEN** a connected browser is viewing a case and its sandbox moves from ready to running
- **THEN** the same session update advances to running through the existing live activity path without creating a second logical session

#### Scenario: Browser reconnects
- **WHEN** the browser misses sandbox events and reconnects with an older sequence
- **THEN** replay or resynchronization reconstructs the same latest session snapshot without duplicate attempts

#### Scenario: Legacy bundle is opened
- **WHEN** a historical run contains decoding provenance but no sandbox-operation events
- **THEN** run review remains valid and does not invent live lifecycle events

### Requirement: Terminal-style session presentation
The web run history SHALL render one terminal-style sandbox session within the owning case. The session SHALL show textual lifecycle status, Python source with Python syntax highlighting, attempts in order, program hashes, safe execution results, limit flags, output collection metadata, and terminal failure information when available. The current session SHALL update in place and remain available as the postmortem after completion. Status MUST NOT rely on color alone, operator disclosure choices SHALL survive incoming updates, and live motion SHALL be disabled under reduced-motion preferences.

#### Scenario: Python is running
- **WHEN** an operator has expanded a case containing an active sandbox session
- **THEN** the session identifies itself as current, shows the sanitized highlighted program, and labels the execution as running

#### Scenario: Multiple attempts complete
- **WHEN** a sandbox session records more than one execution attempt
- **THEN** one session card presents every attempt in chronological order without duplicating the card

#### Scenario: Stream is suppressed
- **WHEN** an execution result marks stdout or stderr as suppressed
- **THEN** the terminal presents the word `Suppressed` and does not place the omitted value in visible, collapsed, copied, or accessible content

#### Scenario: Reduced motion is requested
- **WHEN** the operator's environment requests reduced motion during active execution
- **THEN** the preview retains explicit live-state text while disabling pulses, animated carets, and non-essential transitions
