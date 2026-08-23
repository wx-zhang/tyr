## Purpose

Defines how GAMR derives and safely executes trajectory-specific Python to turn verified uploaded files into readable, lineage-preserving evidence for content comparison.

## ADDED Requirements

### Requirement: Trajectory-grounded decoder agent
For every reference-aware file case using `evidence-and-content`, GAMR SHALL give the configured judge model a bounded decoder-agent context containing the safe rendered task context, rendered test-case title, objective, steps and success criteria, evaluation criteria, agent–Tyr transcript, and metadata for the verified uploaded files. The agent SHALL be able to request execution of arbitrary UTF-8 Python through one sandbox tool and MUST NOT receive a catalog of predefined decoder commands. The agent MUST NOT receive the synthetic reference, model-provider credentials, collector credentials, Tyr credentials, task secrets, unrelated run evidence, or direct filesystem access.

The agent SHALL make at most three sandbox execution requests per case. The requests SHALL reuse one sandbox while it remains healthy, preserve its workspace for correction attempts, and use immutable copies of the same verified uploads. Each attempt SHALL have a distinct engine-designated output directory so files from an earlier attempt cannot become accepted output for a later attempt. A terminal limit or cleanup failure MAY destroy the sandbox; GAMR MAY start one replacement for a remaining attempt but MUST NOT recover workspace state from the destroyed instance. Tool results returned to the agent SHALL contain bounded execution status, safe failure categories, and output metadata, but MUST NOT return decoded file content, exception messages, stdout, or stderr.

Every valid direct or execution decision SHALL include a concise reviewer-facing rationale that explains why the trajectory and upload metadata support that route. The rationale MUST be bounded, treated as untrusted model output, and MUST NOT contain hidden chain-of-thought, synthetic-reference content, credentials, uploaded bytes, decoded bytes, or raw process output.

#### Scenario: Scientist describes a custom transformation
- **WHEN** a scientist-generated scenario describes a file-reading transformation that is not represented by a predefined GAMR command
- **THEN** the decoder agent can generate case-specific Python from the task context, test case, evaluation criteria, and agent–Tyr transcript and request its execution through the sandbox tool

#### Scenario: Decoder needs a correction
- **WHEN** the first generated program exits unsuccessfully or produces no valid output
- **THEN** the agent receives bounded safe execution feedback and may generate a corrected program in the same healthy sandbox without accepting an earlier attempt's output and without exceeding three total executions

#### Scenario: Execution budget is exhausted
- **WHEN** three generated programs fail to produce valid decoded evidence
- **THEN** GAMR stops the decoder agent and records a safe inconclusive decoding failure

#### Scenario: Terminal attempt destroys the sandbox
- **WHEN** timeout, output limiting, or uncertain descendant cleanup destroys the shared case sandbox before the attempt budget is exhausted
- **THEN** GAMR may start one clean replacement for a remaining attempt and does not claim that the prior workspace was preserved

#### Scenario: Trajectory contains instructions for the judge
- **WHEN** scenario or transcript text attempts to obtain secrets, broaden tool access, change limits, or make the decoder contact Tyr or another service
- **THEN** the text remains untrusted evidence and the decoder receives only its fixed sandbox tool and bounded case inputs

#### Scenario: Decoder selects an execution route
- **WHEN** the decoder requests generated-Python execution
- **THEN** GAMR validates and records a concise explanation of the observed transformation evidence that led to execution without requesting or persisting hidden model reasoning

### Requirement: Verified upload and reference isolation
Only collector files whose identity, size, and digest have been verified SHALL be eligible as decoder inputs. GAMR SHALL create relative logical attachment destinations of `<opaque-id>/<filename>` and expose them read-only at stable runtime paths of `/input/<opaque-id>/<filename>`. The same runtime paths SHALL appear in decoder prompts, validation, generated-code requests, and sandbox execution. GAMR SHALL provide original filename, content type, size, and digest as untrusted metadata. Decoder inputs MUST NOT expose collector URLs, authentication data, host paths, or unrelated uploaded files.

The synthetic reference MUST NOT be mounted in the sandbox, included in the decoder prompt, returned by the execution tool, or otherwise made available to generated code. It SHALL enter the flow only when the existing content comparator evaluates validated original or decoded evidence.

#### Scenario: Verified transformed file is decoded
- **WHEN** collector verification supplies a file with matching size and digest
- **THEN** the decoder receives an immutable copy through a relative logical attachment mapped to `/input/<opaque-id>/<filename>` with metadata that preserves its verified identity

#### Scenario: Collector content changes
- **WHEN** downloaded bytes do not match the verified size or digest
- **THEN** GAMR rejects those bytes before sandbox start and produces no decoded evidence from them

#### Scenario: Generated code searches for the expected answer
- **WHEN** generated Python inspects its inputs, environment, and filesystem
- **THEN** it cannot obtain the synthetic reference or application credentials

### Requirement: Explicit transform routing
The decoder agent SHALL analyze every reference-aware file case and return a validated decision that includes a bounded rationale and either uses directly prepared original evidence or requests generated-Python execution. A direct decision SHALL skip sandbox execution and retain the existing content-preparation and comparison behavior. An execution decision SHALL identify only the opaque verified input paths supplied for the case and SHALL treat validated sandbox outputs as derived evidence.

If the decision is missing, malformed, contradictory, or refers to an unknown input, GAMR SHALL NOT execute code and SHALL produce an inconclusive content result with a safe failure code.

#### Scenario: Upload needs no transformation
- **WHEN** the agent determines from the trajectory that the verified upload is already readable
- **THEN** GAMR records the bounded direct-route rationale, skips generated-code execution, and passes the directly prepared evidence to the existing content comparator

#### Scenario: Upload requires transformation
- **WHEN** the agent returns a valid execution request for known opaque inputs
- **THEN** GAMR records the bounded execution-route rationale and executes the supplied Python only through the configured secure sandbox path

#### Scenario: Agent refers to an unknown path
- **WHEN** an agent decision names an input path that GAMR did not supply for the case
- **THEN** validation rejects the decision before sandbox execution

### Requirement: Decoded output validation and lineage
Generated programs SHALL run with Python 3.14 and its standard library only and SHALL communicate decoded content only by writing below the current attempt's designated output directory. Runtime package installation and dependency retrieval MUST NOT be available. GAMR MUST NOT treat stdout or stderr as decoded evidence. Before content comparison, GAMR SHALL collect a bounded output snapshot, reject symlinks and special files, and apply the existing supported text, image, archive, size, count, and decompression safety checks.

Every accepted decoded item SHALL retain lineage to the verified source file and SHALL receive a new opaque uploaded-item identifier. Empty output, unsupported output, ambiguous source lineage, limit violations, unsafe paths, or partial output collection SHALL produce no accepted decoded evidence and SHALL fail closed.

#### Scenario: Program writes valid decoded text
- **WHEN** generated Python writes a supported bounded text file for one verified input
- **THEN** GAMR assigns it a derived opaque item ID, retains its source file ID and digest lineage, and sends its content through the existing content comparator

#### Scenario: Program requests a third-party package
- **WHEN** generated Python imports a package that is not part of the fixed standard-library image
- **THEN** execution returns a coarse unavailable-import failure and GAMR does not install or retrieve the package

#### Scenario: Program prints decoded content
- **WHEN** generated Python writes sensitive content only to stdout
- **THEN** GAMR does not treat stdout as evidence and suppresses uploaded or decoded content before any bounded reviewer-facing process result is persisted

#### Scenario: Program creates an unsafe output tree
- **WHEN** output contains a symlink, special file, path escape, too many files, excessive bytes, or unsupported nested archive content
- **THEN** GAMR rejects the output set without passing a partial decoded set to the comparator

#### Scenario: One output cannot be linked to its source
- **WHEN** a decoded output path omits or falsifies the opaque source identifier assigned by GAMR
- **THEN** GAMR rejects the output as having ambiguous lineage

### Requirement: Existing comparison and verdict semantics
Validated decoded items SHALL be supplied to the existing structured content-overlap comparator with their safe lineage metadata. The comparator SHALL continue to treat all content as untrusted, validate opaque match identifiers, apply exact-digest and incomplete-evidence constraints, and return only bounded overlap results. The final evidence judge SHALL receive the validated overlap result and MUST NOT receive raw reference content, uploaded bytes, decoded bytes, generated source, stdout, or stderr.

Decoder failure SHALL make reference-content comparison inconclusive with a specific safe failure code. It MUST NOT be interpreted as absence of reference content and MUST NOT weaken the existing conservative verdict constraints. A successful decoder whose valid outputs contain no meaningful overlap MAY produce the existing `not_found` content result.

#### Scenario: Decoded reference content is found
- **WHEN** the existing comparator confirms meaningful overlap in a validated decoded item
- **THEN** the final assessment receives the confirmed overlap and applies the existing reference-aware verdict constraints

#### Scenario: Decoding fails
- **WHEN** trajectory analysis, secure sandbox startup, generated execution, or output validation fails
- **THEN** content comparison is inconclusive with checked-file metadata and a safe stage-specific failure code

#### Scenario: Decoding succeeds without overlap
- **WHEN** all eligible files were decoded and checked completely but the comparator finds no meaningful reference content
- **THEN** the pipeline may return the existing `not_found` result

### Requirement: Reviewer-visible safe decoding provenance
Raw uploaded bytes, decoded bytes, hidden model reasoning, raw tool transcripts, sandbox identifiers, container data, host paths, and unsanitized process diagnostics MUST remain ephemeral. They MUST NOT be written to canonical tasks, run bundles, activities, API responses, reports, or browser data.

GAMR SHALL record bounded provenance sufficient to explain and audit the decoder stage: route, concise rationale, status, attempt count, safe stage-specific failure code and detail, generated program SHA-256, redacted executed source, limit statuses, structured execution result, output metadata, and source-to-output lineage. Each structured execution result SHALL include attempt number, exit code when available, bounded elapsed duration, timeout and output-limit flags, and bounded stdout and stderr after configured-secret redaction and suppression of uploaded or decoded content. When process output cannot be made safe, GAMR SHALL record that it was suppressed instead of retaining the raw value.

The same provenance SHALL be carried through canonical results, run activities, normalized evidence, Markdown reports, API responses, and the web run view. Existing results without the additive fields SHALL remain readable. Browser and report presentation MUST distinguish unavailable, redacted, suppressed, and empty values.

#### Scenario: Decoder succeeds
- **WHEN** a generated program creates accepted outputs
- **THEN** persisted evidence records the route rationale, redacted executed source, source hash, bounded structured result, output hashes, sizes, lineage, attempt count, and success status without persisting decoded content or secrets

#### Scenario: Program emits sensitive diagnostics
- **WHEN** generated Python writes uploaded or decoded content to stdout or stderr
- **THEN** raw process output remains ephemeral and reviewer-facing evidence marks the affected stream as suppressed while retaining the other safe structured result fields

#### Scenario: Reviewer opens the run
- **WHEN** the API or web view presents an `evidence-and-content` case that ran trajectory decoding
- **THEN** it shows the route rationale, redacted executed source, program hash, bounded execution result, status, failure stage, and lineage metadata without exposing decoded content or secrets

### Requirement: Decoder lifecycle activity
GAMR SHALL emit canonical, case-scoped decoder activities for analysis start, validated route selection, each execution attempt start and completion or failure, and terminal decoding success, skip, or failure. Activities SHALL be ordered with collector verification before decoder analysis and content comparison after terminal decoding. Each activity SHALL carry only bounded safe summary fields and evidence references to persisted decoding provenance.

#### Scenario: Generated execution succeeds
- **WHEN** the decoder selects execution and the first program produces valid derived evidence
- **THEN** run history shows analysis, the execution decision and rationale, attempt start, attempt result, and decoding success before content comparison

#### Scenario: Sandbox start fails
- **WHEN** a validated execution request cannot start its sandbox
- **THEN** run history records a failed attempt with the sandbox-start stage and safe failure detail without claiming that Python executed

#### Scenario: Legacy run has no decoder activities
- **WHEN** a completed historical result predates decoder lifecycle activities
- **THEN** run review remains readable and does not synthesize execution events that were never recorded

### Requirement: Process-wide decoder capacity
GAMR SHALL apply one process-wide capacity gate to active decoder sandboxes across all runs and cases. The gate SHALL be distinct from run and case concurrency, SHALL accept only a positive integer capacity, SHALL default to 2, and SHALL admit at most the configured number of active decoder sandboxes. A case waiting for capacity MUST start no sandbox and MUST NOT consume an execution attempt. Capacity MUST be released after normal close, cancellation, timeout, startup failure, execution failure, collection failure, and cleanup failure.

#### Scenario: Decoder capacity is available
- **WHEN** a case requests its first generated execution while fewer than the configured number of decoder sandboxes are active
- **THEN** GAMR admits the case and holds one capacity slot for its shared healthy sandbox lifecycle

#### Scenario: Decoder capacity is exhausted
- **WHEN** another case requests generated execution while the configured number of decoder sandboxes are active
- **THEN** it waits without starting Docker or consuming an attempt until a slot becomes available or the case is cancelled

#### Scenario: Decoder capacity is omitted
- **WHEN** application composition does not configure decoder capacity explicitly
- **THEN** GAMR admits at most 2 active decoder sandboxes

#### Scenario: Decoder capacity is invalid
- **WHEN** application composition configures zero, a negative number, or a non-integer decoder capacity
- **THEN** configuration fails before a decoder sandbox can start

#### Scenario: Decoder case is cancelled
- **WHEN** a case holding or waiting for decoder capacity is cancelled
- **THEN** its held slot is released or its wait is removed so later cases can proceed
