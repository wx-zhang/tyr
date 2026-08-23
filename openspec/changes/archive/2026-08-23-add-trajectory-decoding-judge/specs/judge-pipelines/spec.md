## MODIFIED Requirements

### Requirement: Behavior-preserving evidence-and-content pipeline
The `evidence-and-content` pipeline SHALL preserve its existing collector-backed comparison and final structured evidence-assessment semantics while adding trajectory analysis and bounded generated-Python execution before content comparison for every reference-aware file case. The decoder stage SHALL use the configured judge model and the shared secure sandbox path. The comparison and final stages MUST preserve their existing prompts, model request modes, attempt limits, validation rules, conservative verdict constraints, reason-code enrichment, diagnostic exclusions, and canonical assessment fields. Decoder lifecycle activities and bounded decoding provenance SHALL be additive and SHALL occur between collector verification and content comparison.

#### Scenario: Reference-aware file case
- **WHEN** a case requests file collector evidence and its evaluation plan contains a valid synthetic reference
- **THEN** the pipeline verifies the collected files, records decoder analysis and its validated route rationale, prepares direct or safely decoded evidence with bounded attempt provenance, performs the existing structured content-overlap assessment, and supplies that result to the existing final evidence assessment

#### Scenario: Content overlap is confirmed
- **WHEN** the current content judge confirms meaningful overlap in directly prepared or safely decoded evidence
- **THEN** the final assessment receives the confirmed overlap and applies the existing reference-aware verdict constraints

#### Scenario: Content is absent, incomplete, unsupported, or invalid
- **WHEN** preparation, trajectory analysis, decoding, or content assessment cannot safely confirm or reject overlap
- **THEN** the pipeline preserves an inconclusive content result, safe stage-specific failure, checked-file metadata, and final-assessment constraints

#### Scenario: No applicable reference-content comparison
- **WHEN** the evaluation has no synthetic reference or the scenario does not request file collector evidence
- **THEN** the pipeline skips trajectory decoding and content comparison and runs the existing final evidence assessment without content-overlap context

#### Scenario: Structured content response is invalid once
- **WHEN** the content judge's first response fails existing validation and its second response is valid
- **THEN** the pipeline preserves the recovered content result and makes no additional content-judge call

#### Scenario: Structured final response is invalid once
- **WHEN** the final judge's first response fails existing validation and its second response is valid
- **THEN** the pipeline preserves the recovered final assessment and makes no additional final-judge call

#### Scenario: Case execution fails without verified content
- **WHEN** case execution reports an error and no verified content is available under the existing rules
- **THEN** GAMR preserves the existing early failed case result and does not start trajectory analysis, generated execution, or final assessment

### Requirement: Follow-up judge behavior remains separate
The `evidence-and-content` pipeline MAY add only the bounded trajectory analysis and sandboxed generated-Python behavior defined by `trajectory-content-decoding`. It SHALL NOT call arbitrary external APIs, initiate new Tyr conversations, approve actions, execute on the host, install runtime packages, or load task-selected code. Any API-checking, Tyr-interacting, action-approving, dynamically installed, or networked judge behavior MUST be introduced through a later specification and a new predefined pipeline or an explicitly revised pipeline contract.

#### Scenario: Transformed upload is not directly readable
- **WHEN** the current content preparation cannot directly read a transformed upload but verified bytes and trajectory context are available
- **THEN** `evidence-and-content` may derive and execute standard-library Python only through its bounded secure decoder stage before invoking the existing comparator

#### Scenario: Future pipeline identifier is not implemented
- **WHEN** a task requests a future API-checking or Tyr-interacting pipeline before that identifier is added to the schema and registry
- **THEN** task validation rejects the request

## ADDED Requirements

### Requirement: Decoder execution parity
CLI and API composition SHALL provide the same judge model, verified content source, secure sandbox, and process-wide decoder-capacity behavior to the existing `evidence-and-content` pipeline. Base cases and scientist-generated cases SHALL use the same graph, trajectory inputs, model limits, sandbox lifecycle, output validation, comparison semantics, safe failures, activity lifecycle, and provenance rules. Delivery surfaces MUST NOT provide a flag, request field, environment override, or model-controlled value that disables the decoder stage for an individual applicable case.

#### Scenario: CLI and API execute equivalent decoder cases
- **WHEN** equivalent CLI and API runs use the same task, verified evidence, judge-model responses, and sandbox results
- **THEN** they produce equivalent decoder calls, route rationale, redacted executed source, structured execution results, activities, accepted outputs, content results, assessments, and safe provenance under the same `evidence-and-content` identifier

#### Scenario: Scientist-generated case is decoded
- **WHEN** a scientist-generated reference-aware file case reaches `evidence-and-content`
- **THEN** its safe task context, rendered test case, evaluation criteria, and own agent–Tyr transcript are analyzed through the same decoder path used for a base case

#### Scenario: Existing exfiltration task executes
- **WHEN** the repository's existing exfiltration task runs a reference-aware file case after this change
- **THEN** its existing `evidence-and-content` selection executes the upgraded decoder path without a task-selected code payload or second judge identifier
