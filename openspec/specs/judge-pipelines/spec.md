# judge-pipelines Specification

## Purpose

Defines how tasks select a predefined judge pipeline and how GAMR executes and identifies that pipeline while preserving the current assessment behavior.

## Requirements

### Requirement: Task-selected predefined judge pipeline
A task manifest SHALL accept a `spec.judge` object whose required `pipeline` field is defined by the task schema. The first allowed identifier SHALL be `evidence-and-content`. A task-provided value MUST identify a predefined pipeline and MUST NOT name an import path, source file, class, prompt template, URL, or executable payload. The judge object MUST reject unknown fields.

#### Scenario: Task selects the current pipeline
- **WHEN** a task manifest declares `"judge": {"pipeline": "evidence-and-content"}` under `spec`
- **THEN** task validation succeeds and GAMR uses that pipeline for every selected case in the task

#### Scenario: Legacy task manifest omits selection
- **WHEN** a valid existing task manifest omits `spec.judge`
- **THEN** GAMR selects `evidence-and-content` and preserves the task's current behavior

#### Scenario: Unknown pipeline is requested
- **WHEN** a task manifest declares a judge pipeline identifier that is not predefined
- **THEN** task validation fails before an experiment starts

#### Scenario: Evaluation is not configured
- **WHEN** a task has no evaluation plan
- **THEN** GAMR preserves the existing skipped-assessment result and does not execute a judge pipeline

### Requirement: Inspectable pipeline topology
Each predefined judge pipeline SHALL have a deterministic graph with stable, human-readable node names. GAMR SHALL be able to obtain the compiled graph's topology without running a case, calling a model, contacting Tyr, loading collector content, or exposing task evidence. Topology inspection SHALL be suitable for later rendering as a flow diagram.

#### Scenario: Pipeline topology is inspected
- **WHEN** a developer inspects the `evidence-and-content` pipeline graph
- **THEN** the graph reports its named stages and conditional paths without executing any stage

#### Scenario: Pipeline is executed repeatedly
- **WHEN** multiple cases use the same predefined pipeline
- **THEN** each case starts with fresh pipeline state and no case evidence is retained in the compiled graph

### Requirement: Offline judge graph image generation
The repository SHALL provide `uv run poe judge-graph <judge-directory>` to render the inspected topology of one registered judge pipeline as a PNG under `docs/assets/judges/`. The command SHALL derive the output filename from the registered pipeline identifier, SHALL render without network access or case execution, and SHALL atomically replace the same output file when it already exists.

#### Scenario: Registered judge directory is rendered
- **WHEN** a developer runs `uv run poe judge-graph packages/engine/src/gamr_engine/judges/evidence_and_content`
- **THEN** the command writes a non-empty PNG to `docs/assets/judges/evidence-and-content.png` containing the registered graph's named nodes and edges

#### Scenario: Existing image is regenerated
- **WHEN** the target PNG already exists and rendering succeeds
- **THEN** the command atomically replaces it with the newly rendered graph

#### Scenario: Rendering fails after an image exists
- **WHEN** validation or rendering fails before a replacement image is complete
- **THEN** the command exits unsuccessfully and leaves the existing target PNG unchanged

#### Scenario: Judge path is invalid
- **WHEN** the supplied path is missing, is not a directory, escapes the repository judge root directly or through a symlink, or does not identify a registered judge directory
- **THEN** the command exits unsuccessfully without importing code from that path or writing a documentation image

#### Scenario: Graph image is generated offline
- **WHEN** a registered judge graph is rendered without network access
- **THEN** the command completes without calling a model, Tyr, collector services, a browser, or an external rendering service

### Requirement: Shared pipeline execution path
CLI and API experiments SHALL resolve the task's selected pipeline through the same engine path. A selected pipeline SHALL receive only the case context and engine capabilities provided to it by that path, and its output SHALL be validated before becoming the canonical case assessment.

#### Scenario: CLI and API execute the same task
- **WHEN** equivalent CLI and API runs execute the same task, case evidence, model responses, and selected judge pipeline
- **THEN** they produce equivalent judge model calls, content results, assessment status, objective status, verdict, reason codes, and missing evidence

#### Scenario: Scientist-generated case is assessed
- **WHEN** a scientist-generated case reaches evaluation
- **THEN** the task-selected pipeline assesses it through the same path used for a base case

#### Scenario: Pipeline output is invalid
- **WHEN** the selected pipeline cannot produce a valid assessment
- **THEN** the case remains inconclusive with the existing safe failed-assessment summary and missing-evidence behavior

### Requirement: Behavior-preserving evidence-and-content pipeline
The `evidence-and-content` pipeline SHALL preserve its existing collector-backed comparison and final structured evidence-assessment semantics while adding trajectory analysis and bounded generated-Python execution before content comparison for every reference-aware file case. The decoder stage SHALL use the configured judge model and the shared secure sandbox path. The comparison and final stages MUST preserve their existing judgment criteria, model request modes, attempt limits, validation rules, conservative verdict constraints, reason-code enrichment, diagnostic exclusions, and canonical assessment fields. Decoder lifecycle activities and bounded decoding provenance SHALL be additive and SHALL occur between collector verification and content comparison.

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

### Requirement: Judge-authored output language
Judge and decoder prompts SHALL apply `.agents/skills/prompt-language/SKILL.md` to authored instructions and generated natural-language fields, including summaries, reasons, missing-evidence descriptions, match explanations, and route rationales. Generated prose SHALL use direct active factual outcome statements, cite supplied evidence identifiers exactly, and name missing or conflicting evidence when describing uncertainty. Prompts SHALL exclude filler, hedges, prohibited terms and phrases, self-referential narration, negative contrast frames, em dashes, and emoji from authored prose. Prompts SHALL permit imperative recommendations only when explicitly requested. These language instructions SHALL reach initial requests, correction requests, and the non-structured final-assessment fallback.

The language requirement MUST preserve quoted evidence and exact expected and received values verbatim, including language excluded from authored prose. The content judge MUST retain Markdown headings and a fenced `diff` block inside `summary`, with expected reference categories on `-` lines and received evidence categories on `+` lines. Judge responses MUST retain the raw JSON output contract, required keys, identifiers, and enum values. Language guidance SHALL NOT add prose postprocessing, style-based rejection, or changes to judgment criteria or validation rules.

#### Scenario: Judge writes an assessment
- **WHEN** a final judge, content judge, or decoder generates a natural-language field
- **THEN** its prompt requires direct factual outcome prose and exact supplied evidence references
- **AND** its output retains the stage's schema and required Markdown formatting

#### Scenario: Judge corrects an invalid response
- **WHEN** a structured judge receives a correction request after an invalid response
- **THEN** the correction retains the same authored-language guidance and judgment criteria

#### Scenario: Final judge uses the non-structured fallback
- **WHEN** the configured final judge lacks structured completion
- **THEN** its completion prompt includes the same evidence-handling and authored-language instructions as the structured path
- **AND** GAMR preserves the fallback's existing attempt limit and validation behavior

#### Scenario: Evidence contains excluded language
- **WHEN** quoted evidence contains a prohibited phrase, an em dash, or an emoji
- **THEN** the judge preserves that evidence verbatim while applying the language requirement only to its authored prose

### Requirement: Judge pipeline provenance
Canonical run results and normalized evaluation evidence SHALL identify the selected judge pipeline. This provenance SHALL be additive: existing content-overlap fields, assessment fields, diagnostic locations, and reviewer-facing content SHALL retain their current meaning and shape. Readers SHALL continue to accept legacy run bundles that have no pipeline identifier.

#### Scenario: New run completes
- **WHEN** a run uses `evidence-and-content`
- **THEN** its canonical result and normalized evaluation evidence identify `evidence-and-content`

#### Scenario: Reviewer opens a new run
- **WHEN** the API or web run view presents an evaluation produced by a selected pipeline
- **THEN** it identifies the pipeline without removing or changing the existing content comparison and judge assessment presentation

#### Scenario: Legacy run is loaded
- **WHEN** a completed run bundle predates judge-pipeline provenance
- **THEN** result loading, evidence normalization, API delivery, and web presentation remain valid without inventing persisted historical data

### Requirement: Existing evidence and secret boundaries
Pipeline extraction MUST NOT broaden model, target, filesystem, credential, or evidence access. The `evidence-and-content` pipeline SHALL retain the current separation between raw reference or uploaded content, safe content-overlap results, final judge input, diagnostics, persisted artifacts, API responses, and browser-visible data.

#### Scenario: Final judge is called for a reference-aware case
- **WHEN** content comparison finishes before final assessment
- **THEN** the final judge receives the validated content-overlap result and does not receive raw reference or uploaded file content

#### Scenario: Diagnostics are persisted
- **WHEN** either current judge stage records model diagnostics
- **THEN** persisted artifacts contain the same bounded metadata and exclusions as before this change

#### Scenario: Pipeline identifier is untrusted input
- **WHEN** a task supplies a malformed or code-like pipeline identifier
- **THEN** schema validation rejects it and GAMR does not import or execute task-selected code

### Requirement: Follow-up judge behavior remains separate
The `evidence-and-content` pipeline MAY add only the bounded trajectory analysis and sandboxed generated-Python behavior defined by `trajectory-content-decoding`. It SHALL NOT call arbitrary external APIs, initiate new Tyr conversations, approve actions, execute on the host, install runtime packages, or load task-selected code. Any API-checking, Tyr-interacting, action-approving, dynamically installed, or networked judge behavior MUST be introduced through a later specification and a new predefined pipeline or an explicitly revised pipeline contract.

#### Scenario: Transformed upload is not directly readable
- **WHEN** the current content preparation cannot directly read a transformed upload but verified bytes and trajectory context are available
- **THEN** `evidence-and-content` may derive and execute standard-library Python only through its bounded secure decoder stage before invoking the existing comparator

#### Scenario: Future pipeline identifier is not implemented
- **WHEN** a task requests a future API-checking or Tyr-interacting pipeline before that identifier is added to the schema and registry
- **THEN** task validation rejects the request

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
