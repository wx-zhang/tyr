# Feature Specification: Run Evidence Visualization

**Feature Branch**: `main`

**Created**: 2026-08-08

**Status**: Implemented

**Architecture update (2026-08-09)**: Activity search, relationships, progress, and reconnect
delivery are derived directly from canonical JSON bundles. The optional single-instance service
starts read-only runs in process; approval-required runs remain CLI-owned and are review-only here.

**Input**: User description: "Add visualization in the web interface for ongoing and previous test runs, tracking progress, current activity, captured evidence, communication with agents, and activity in the Tyr network."

## Clarifications

### Session 2026-08-08

- Q: Which coordinated views must the run visualization provide? → A: Synchronized progress overview, chronological timeline, agent/Tyr relationship graph, and evidence inspector.
- Q: Must reviewers be able to compare multiple previous runs within this feature? → A: No. The visualization covers one selected run; cross-run comparison is out of scope.
- Q: How must reviewers search within a selected run's captured evidence? → A: Search permitted redacted text and filter structured metadata within the selected run.
- Q: How should the agent/Tyr relationship graph handle a run with many repeated interactions? → A: Aggregate repeated relationships under current filters and expose individual evidence on selection.
- Q: How should retained raw diagnostic evidence be exposed in the web interface? → A: Show summaries first and reveal complete permitted redacted evidence on demand.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand Live Run Progress (Priority: P1)

As a red-team operator, I can open an ongoing run and immediately understand its overall state, completed work, current phase and case, remaining work, and whether anything needs my attention.

**Why this priority**: The primary value is replacing uncertainty during a long-running test with a trustworthy view of progress and blockers.

**Independent Test**: Start a multi-case run, advance it through multiple phases, and verify that the run view identifies completed, active, pending, blocked, and terminal work without requiring the operator to inspect raw evidence.

**Acceptance Scenarios**:

1. **Given** a run is processing multiple cases, **When** the operator opens its run view, **Then** the view shows the exact run state, action mode, current phase and case, completed case count, total case count, latest update time, and any pending approval.
2. **Given** the active case or phase changes, **When** the next persisted update is received, **Then** the visualization updates in order and never marks active work as completed.
3. **Given** a run is waiting for approval, **When** the operator views progress, **Then** the blocked work and required human decision are prominent and the rest of the known progress remains visible.
4. **Given** a run completes, fails, or is cancelled, **When** the terminal update is shown, **Then** the view identifies the outcome and preserves the full reviewable history.

---

### User Story 2 - Explore Previous Run Evidence (Priority: P2)

As a red-team operator or reviewer, I can open a previous run and explore its outcome and captured evidence from a clear overview down to a specific case, participant, operation, communication, approval, finding, transcript entry, or artifact.

**Why this priority**: GAMR captures substantial evidence for audit and evaluation. A previous run must be understandable without manually reading separate raw files or reconstructing relationships.

**Independent Test**: Open a completed multi-case run with transcripts, findings, agent communication, Tyr operations, approvals, errors, and artifacts, then verify that a reviewer can navigate from the outcome summary to each permitted supporting evidence item and back to its run context.

**Acceptance Scenarios**:

1. **Given** a previous run has completed, failed, been cancelled, or been interrupted, **When** a reviewer opens it, **Then** the view shows its terminal status, duration, case outcomes, findings, errors, approvals, participants, Tyr activity, and available evidence categories.
2. **Given** a reviewer selects a case, finding, participant, relationship, operation, or point in the timeline, **When** supporting evidence exists, **Then** the related communications, state changes, approvals, tool activity, and artifacts can be reached without losing the broader run context.
3. **Given** a previous run contains a large amount of evidence, **When** the reviewer filters by case, participant, activity type, status, evidence type, or time range, **Then** matching evidence is shown with its original identity and sequence intact.
4. **Given** summarized or visualized evidence is displayed, **When** the reviewer requests detail, **Then** complete permitted redacted evidence is revealed on demand and the interface states when content is unavailable, redacted, or omitted from the current view.
5. **Given** a reviewer selects an item in the progress overview, chronological timeline, agent/Tyr relationship graph, or evidence inspector, **When** the item has related content in another view, **Then** all four views synchronize to the same run context without changing the evidence's identity or sequence.
6. **Given** a selected run contains permitted redacted text and structured evidence metadata, **When** the reviewer enters exact text and applies filters, **Then** matching evidence is shown with its original identity, sequence, and run context.

---

### User Story 3 - Follow Agent and Tyr Activity (Priority: P3)

As a red-team operator, I can follow the ordered communication among GAMR, model agents, Tyr operations, delegated agents, bridges, tools, and human approvals so that I know what is happening and why the run is moving or waiting.

**Why this priority**: Progress counts alone cannot explain stalls, delegation, policy decisions, or the path an action took through Tyr.

**Independent Test**: Run a case containing agent messages, a delegated Tyr operation, a tool request, and an approval decision, then verify that each activity appears once, in order, with its source, target, type, status, and case context.

**Acceptance Scenarios**:

1. **Given** communication and operation activity exists for a run, **When** the operator opens the live activity view, **Then** each item has a visible type, timestamp, source, destination when known, status, and related case or phase.
2. **Given** Tyr delegates work or uses a bridge, **When** the relationship is present in run evidence, **Then** the visualization connects the observed participants and operations without presenting inferred or unavailable relationships as facts.
3. **Given** a tool action requires human approval, **When** the request and decision occur, **Then** both appear in their chronological context with the action mode, approval status, recorded actor, and decision time.
4. **Given** communication content or operation details contain protected values, **When** they are displayed, expanded, copied, or announced, **Then** the protected values remain redacted.
5. **Given** participants have repeated interactions, **When** the relationship graph is shown or filtered, **Then** matching interactions are aggregated into readable relationships and selecting one reveals every contributing permitted evidence item in authoritative order.

---

### User Story 4 - Investigate a Busy or Interrupted Run (Priority: P4)

As a reviewer, I can pause automatic following, filter or select activity, inspect an earlier point in the run, and resume following without losing the authoritative sequence of events.

**Why this priority**: Busy runs can produce more activity than a person can follow live, and connection loss must not undermine auditability.

**Independent Test**: Generate a long run history, inspect an earlier activity item while new updates arrive, apply a case or activity-type filter, disconnect and reconnect, and verify that the complete ordered history remains available.

**Acceptance Scenarios**:

1. **Given** the operator is inspecting older activity, **When** new activity arrives, **Then** the view indicates that updates are available without moving the operator away from the selected evidence.
2. **Given** a run has many cases and activity types, **When** the operator filters by case, participant, activity type, or status, **Then** matching items are shown while overall run progress and the presence of pending approvals remain visible.
3. **Given** the live connection is interrupted, **When** the view reconnects, **Then** missed persisted activity is restored in order without duplicates and the connection state is stated in text.
4. **Given** the retained live view is intentionally bounded, **When** older permitted evidence is omitted from the current view, **Then** the interface states what was omitted and provides a route to the complete permitted run evidence.

### Edge Cases

- A queued run has no active phase, case, participants, or activity yet.
- Progress totals are not yet known or the dataset contains zero selected cases.
- Several cases or Tyr operations overlap, complete out of order, or publish activity at nearly the same time.
- An event arrives late, is repeated after reconnection, or refers to a participant or operation not previously observed.
- Tyr reports an outer terminal state while delegated or bridge work is still settling.
- A case fails while the overall run continues, or the run ends before every case reaches a terminal state.
- A pending approval blocks one operation while other read-only work continues.
- Communication content is empty, malformed, very large, unavailable, or entirely redacted.
- Historical evidence contains gaps because a source did not emit an item or the user lacks permission to view it.
- A completed run has evidence artifacts but no canonical result because it was interrupted before finalization.
- Related evidence uses several identifiers for the same operation or participant, or an item has no resolvable relationship.
- The live connection is stale, reconnecting, or unavailable while previously persisted state remains readable.
- A participant has no safe display name or two participants share the same display name.
- The viewport is narrow, the user navigates only by keyboard, or reduced motion is enabled.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web interface MUST provide a unified visualization for both ongoing and previous runs within the selected run's review experience.
- **FR-002**: The visualization MUST show the exact run state, action mode, dataset, start time, latest persisted update time, and live connection state using text rather than color alone.
- **FR-003**: The visualization MUST show progress across the known run phases and selected cases, distinguishing completed, active, pending, waiting, failed, cancelled, and unknown states without treating active work as complete.
- **FR-004**: The visualization MUST identify the current phase, current case or cases when concurrent work is known, and the latest meaningful activity.
- **FR-005**: The visualization MUST show completed and total case counts when totals are known and explicitly state when a total or remaining-work estimate is unavailable.
- **FR-006**: The visualization MUST make pending approvals and other blockers prominent while preserving visibility of already completed work and work that may continue.
- **FR-007**: The visualization MUST present persisted run activity in authoritative order and give every item a visible activity type, time, status, and related phase or case when known.
- **FR-008**: Activity MUST distinguish human prompts and decisions, model-agent messages, GAMR system activity, Tyr operations, delegated-agent activity, bridge activity, tool calls, approvals, errors, and state changes when those distinctions exist in the evidence.
- **FR-009**: The visualization MUST identify the source and destination of communication or operational activity when known and MUST label either side as unknown when the evidence does not identify it.
- **FR-010**: The visualization MUST show observed relationships among participants, operations, delegations, bridges, tools, and approvals without inventing or implying unobserved Tyr-network topology.
- **FR-011**: Selecting a participant, relationship, progress step, or activity item MUST reveal its permitted supporting details and corresponding chronological context.
- **FR-012**: Previous-run views MUST summarize the terminal outcome, duration, case results, findings, errors, approval history, observed participants, Tyr activity, and available evidence categories.
- **FR-013**: The visualization MUST make permitted transcripts, messages, state changes, tool calls and results, approvals, findings, errors, artifacts, and retained diagnostics discoverable from their related case, participant, operation, relationship, or point in time.
- **FR-014**: Operators MUST be able to filter evidence by case, participant, activity type, status, evidence type, and time range without changing original identities or ordering and without hiding overall run state or pending-approval indicators.
- **FR-015**: Summaries and graphical representations MUST link back to their permitted supporting evidence and MUST clearly state when evidence is missing, unavailable, redacted, or omitted from the current view.
- **FR-016**: The visualization MUST preserve context when moving between overview, progress, relationship, activity, and evidence-detail views so users can return to the same selection and filters.
- **FR-017**: The live view MUST automatically follow new activity only while the operator is at the current end of the history; otherwise it MUST preserve the operator's position and indicate that newer activity is available.
- **FR-018**: The interface MUST explicitly communicate connected, reconnecting, stale, and disconnected states while keeping the last known persisted run state visible.
- **FR-019**: After an interruption, the visualization MUST restore missed persisted activity in sequence and MUST NOT display duplicate activity.
- **FR-020**: The visualization MUST preserve full review access after the run completes, fails, is cancelled, or is interrupted, subject to the user's evidence permissions and retention rules.
- **FR-021**: A terminal outer Tyr state MUST NOT be presented as settled while observed delegated, bridge, or late response activity remains pending.
- **FR-022**: Secrets and configured protected fields MUST remain redacted in summaries, visual relationships, details, collapsed content, copied content, and accessible representations.
- **FR-023**: The visualization MUST NOT expose Tyr credentials, model-provider credentials, authorization data, or server-only diagnostic data to the browser.
- **FR-024**: The visualization MUST support keyboard navigation, visible focus, text alternatives for graphical relationships, restrained status announcements, and reduced-motion preferences.
- **FR-025**: When run history or evidence is bounded for usability, the interface MUST identify omitted content and provide access to the complete permitted evidence.
- **FR-026**: Empty, loading, unavailable, malformed, partially captured, and partially redacted evidence MUST have clear non-deceptive states that do not erase valid persisted information.
- **FR-027**: The visualization MUST provide a synchronized progress overview, chronological timeline, agent/Tyr relationship graph, and evidence inspector; selecting supported content in one view MUST update the context shown in the other views.
- **FR-028**: The visualization MUST show one selected run at a time and MUST NOT include cross-run comparison or aggregate trends across runs.
- **FR-029**: Reviewers MUST be able to search exact text within permitted redacted evidence content and combine that search with case, participant, activity type, status, evidence type, and time-range filters for the selected run.
- **FR-030**: The agent/Tyr relationship graph MUST aggregate repeated observed relationships that match the current search and filters, show the number and types of contributing interactions, and expose every contributing permitted evidence item on selection.
- **FR-031**: The evidence inspector MUST show a readable summary by default and MUST allow the reviewer to deliberately reveal the complete permitted redacted content of a retained diagnostic evidence item on demand.
- **FR-032**: The Updates timeline MUST show each canonical case evaluation, including scientist-generated cases, with security verdict as the primary result and objective status, execution outcome, and redacted assessment summary as supporting evidence.
- **FR-033**: An execution with selected case IDs MUST run those cases and MAY run scientist iterations; an execution with an explicitly empty case-ID list MUST run scientist iterations only when iterations are enabled. Discovery MUST precede either mode, and an empty case-ID list with scientist disabled MUST be rejected.
- **FR-034**: Each scientist iteration MUST persist a bounded, redacted progress update identifying the case IDs used as history, or explicitly state that no prior tests were available. The history indicator MUST be available to live, API, and historical run views without exposing prompts, transcripts, credentials, or server paths.
- **FR-035**: Verified remote-backed collector artifacts MUST refresh automatically during a live run, appear chronologically as entries in Updates, and offer bounded, run-scoped previews for common text, Markdown, and raster-image files without exposing collector credentials or server paths. Unsupported and oversized artifacts MUST remain download-only.
- **FR-035**: Scientist-enabled executions MUST support configurable history windows for prior test-case runs and prior scientist runs, defaulting to the latest 10 and 5 runs respectively. Only completed or terminal persisted runs for the same dataset with available results MAY be used, and the selected records MUST be combined with the current run's records using the existing scientist history rebuild process.

### Key Entities

- **Run progress**: The run's current and terminal state, action mode, known phases, selected case totals, completed work, active work, blockers, and timestamps.
- **Execution mode**: The derived case or scientist-only mode determined from the selected case IDs and scientist iteration count.
- **Scientist history window**: The bounded configuration of recent test-case and scientist run bundles whose redacted case records and transcripts seed each scientist iteration.
- **Case progress**: One selected test case's order, current phase, status, security verdict, objective status, execution outcome, assessment summary, and relationship to its activity and approvals.
- **Activity item**: One ordered, persisted occurrence with an identity, timestamp, type, status, summary, permitted details, and related run, phase, case, participants, operation, or approval.
- **Participant**: An observed human, GAMR component, model agent, Tyr agent, delegated agent, bridge, or tool endpoint, identified only to the extent supported by permitted evidence.
- **Observed relationship**: An aggregated communication, delegation, bridge, operation, tool invocation, or approval link between known participants, with counts and types derived from the current search and filters and references to every contributing permitted activity or evidence item.
- **Approval**: A human decision request tied to a run, case, tool action, normalized redacted arguments, status, consequence, actor, and decision time.
- **Evidence item**: A permitted transcript entry, message, state change, tool call or result, finding, error, artifact, or retained diagnostic tied to its original run context and provenance, with a readable summary and complete redacted content when retained and requested.
- **View state**: The shared selection across the progress overview, chronological timeline, agent/Tyr relationship graph, and evidence inspector, plus active filters, freshness, last persisted update, connection condition, missed-update recovery, and live-follow position.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In usability testing, at least 90% of operators can identify the run state, current work, completed case count, and any blocker within 10 seconds of opening an active run.
- **SC-002**: For a reference run containing at least 100 activity items across 10 cases, 100% of persisted items available to the user appear in authoritative order, with no duplicates after a simulated disconnect and reconnect.
- **SC-003**: New persisted activity is visible to a following operator within 2 seconds for at least 95% of updates under normal operating conditions.
- **SC-004**: In task-based testing, at least 90% of operators can trace a selected tool action from initiating communication through Tyr handling and approval outcome, when all relationships are present in the evidence, within 60 seconds.
- **SC-005**: In task-based testing, at least 90% of reviewers can start from a previous run's summary and locate the supporting evidence for a selected case outcome or finding within 60 seconds.
- **SC-006**: Across redaction tests, zero configured secret values appear in visible text, graphical labels, expandable details, copied content, or assistive-technology output.
- **SC-007**: All primary monitoring, filtering, selection, evidence inspection, context-return, and resume-following tasks can be completed using only a keyboard and meet WCAG 2.2 AA expectations.
- **SC-008**: For a run with 10,000 permitted evidence and activity items, reviewers can open the overview, search exact text, apply a filter, select an item, and return to the same context without an interaction taking longer than 2 seconds under normal operating conditions.
- **SC-009**: In usability testing, at least 85% of operators rate the visualization as clear and trustworthy for understanding both what happened in a previous run and why an active run is progressing, waiting, or failing.

## Assumptions

- The feature extends the existing run view in the web interface. Live monitoring and historical evidence review are equal parts of the scope.
- The intended users are authenticated red-team operators and reviewers who already have permission to view the selected run.
- “Tyr network” means the observed logical relationships in redacted run evidence, including operations, agents, delegations, bridges, tools, and approvals. It does not mean hidden physical infrastructure or inferred topology.
- Persisted run evidence is authoritative. Transient animation, elapsed time, or a Tyr outer status does not override it.
- Exact time remaining is not promised because case duration can vary. Known counts and states are shown; unavailable estimates are labeled as unavailable.
- Concurrent activity may be visualized when evidence identifies it, but the interface does not infer concurrency from close timestamps alone.
- Existing run permissions, retention rules, action-mode rules, approval workflows, and evidence access controls continue to apply.
- The feature does not add automatic approval, direct Tyr control from the browser, or a new action-enabled mode.
- Cross-run comparison and aggregate trends across multiple runs are out of scope.
