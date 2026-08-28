# scientist-scenario-catalog Specification

## Purpose

Provides a safe operator catalog for reviewing, filtering, exporting, archiving, and restoring
Adversarial Researcher-generated Scenarios across retained Experiments.

## Canonical terminology

Generated content is authored by the **Adversarial Researcher** during a
**Research Iteration**. It produces Task **Scenarios**, not executions. When a
generated Scenario runs, the result is a **Scenario Execution Result** carrying
both the authored `scenarioId` and unique `scenarioExecutionId`. Existing
scientist directories, event names, URLs, and archive markers remain readable
compatibility boundaries.

## Requirements

### Requirement: Adversarial Researcher Scenario catalog
The system SHALL expose every valid Adversarial Researcher-generated Scenario retained by an existing
Experiment as a catalog entry. Each entry SHALL contain the canonical Scenario document, originating
Task and Experiment, archive state, and matching Scenario Execution Result when one exists. Entries
SHALL be ordered by originating Experiment from newest to oldest with a deterministic order within
each Experiment.

When a matching Scenario Execution Result does not yet exist, the entry SHALL report `pending` while
its Experiment can still produce a result and `unavailable` after its Experiment becomes terminal. The
catalog SHALL preserve `vulnerable`, `protected`, `inconclusive`, and `not_applicable` as distinct
security verdicts.

#### Scenario: Completed researcher Scenario is listed
- **WHEN** a retained Experiment contains a valid Adversarial Researcher Scenario and a matching Scenario Execution Result
- **THEN** the catalog returns its canonical definition, originating Task and Experiment, archive state, and security verdict

#### Scenario: Active Scenario has no result yet
- **WHEN** an Adversarial Researcher Scenario has been persisted but its originating Experiment can still produce the matching Scenario Execution Result
- **THEN** the catalog lists the Scenario with result state `pending`

#### Scenario: Terminal Experiment has no Scenario Execution Result
- **WHEN** an Adversarial Researcher Scenario remains in a terminal Experiment without a matching Scenario Execution Result
- **THEN** the catalog lists the Scenario with result state `unavailable`

#### Scenario: Source Experiment no longer exists
- **WHEN** an originating Experiment and its evidence have been deleted through the existing deletion behavior
- **THEN** its Adversarial Researcher Scenarios no longer appear in either catalog view

### Requirement: Scenario browsing and origin navigation
The web application SHALL expose Adversarial Researcher-generated Scenarios from the Task details
Scenarios section through a dedicated Adversarial Researcher tab or equivalent labeled selection
alongside authored Task Scenarios. The selected Task view SHALL show only generated Scenarios
originating from that Task. The generated Scenario view SHALL use the same list-and-detail pattern as
authored Scenarios, with the full Scenario definition in the detail panel. It SHALL NOT require a
separate primary-navigation entry or standalone catalog page. Active Scenarios SHALL be shown by
default, archived Scenarios SHALL be available in a separate view, and each entry SHALL expose a link
to the originating Experiment with its Scenario Execution selected.

The full definition SHALL include the Scenario identifier, title, tags, objective, steps, success
criteria when present, expected control, evidence requirements, and collector-evidence mode when
present.

#### Scenario: Operator browses an active Scenario
- **WHEN** an operator opens a Task's Scenarios section, selects Adversarial Researcher Scenarios, and selects an active entry
- **THEN** the complete retained Scenario definition and result summary for that Task are available in the detail panel without opening the Experiment

#### Scenario: Adversarial Researcher Scenarios are not a standalone menu
- **WHEN** an operator navigates the application primary menu
- **THEN** the application does not present a separate Adversarial Researcher destination; the Scenarios are available from Task details

#### Scenario: Operator follows the origin link
- **WHEN** an operator activates a Scenario's Experiment link
- **THEN** the application opens the originating Experiment with that Scenario Execution selected

#### Scenario: Operator views archived Scenarios
- **WHEN** an operator selects Adversarial Researcher Scenarios in a Task's Scenarios section and then selects the Archived view
- **THEN** only archived entries originating from that Task are listed with restore and export actions

### Requirement: Security verdict filtering
The catalog SHALL allow operators to filter the selected Active or Archived view by one result value. Supported values SHALL be `vulnerable`, `protected`, `inconclusive`, `not_applicable`, `pending`, and `unavailable`. Clearing the filter SHALL restore every entry in the selected archive view.

#### Scenario: Filter by security verdict
- **WHEN** an operator selects the `protected` result filter
- **THEN** only Scenarios whose matching Scenario Execution Result has verdict `protected` are shown in the current archive view

#### Scenario: Filter Scenarios awaiting results
- **WHEN** an operator selects the `pending` result filter
- **THEN** only persisted Adversarial Researcher Scenarios whose Experiments can still produce a matching result are shown

#### Scenario: Clear result filter
- **WHEN** an operator clears an active result filter
- **THEN** all scenarios in the selected Active or Archived view are shown again

### Requirement: Reversible Scenario archiving
The system SHALL allow an operator to archive an active Adversarial Researcher Scenario and restore
an archived Scenario. Archive state SHALL be scoped to the Scenario artifact in its originating
Experiment so Scenarios with the same identifier in different Experiments remain independent.

Archiving and restoring SHALL be idempotent and SHALL NOT modify or delete the originating Scenario
artifact, Experiment result, transcript, activity, or other Experiment evidence. The Active and
Archived controls and the archive or restore action labels SHALL make the reversible catalog state
clear.

#### Scenario: Archive an active Scenario
- **WHEN** an operator archives an active Adversarial Researcher Scenario
- **THEN** it moves to the Archived view while every file in its originating Experiment bundle remains unchanged

#### Scenario: Restore an archived Scenario
- **WHEN** an operator restores an archived Adversarial Researcher Scenario
- **THEN** it moves to the Active view and its originating evidence remains unchanged

#### Scenario: Repeated archive request
- **WHEN** an already archived scenario is archived again
- **THEN** the request succeeds without creating a duplicate archive record or changing Experiment evidence.
#### Scenario: Same Scenario ID exists in another Experiment
- **WHEN** an operator archives one of two catalog entries with the same Scenario identifier but different originating Experiments
- **THEN** only the selected originating entry becomes archived

### Requirement: Canonical JSON export
The system SHALL allow one active or archived Adversarial Researcher Scenario at a time to be downloaded as JSON. The response body SHALL be the exact canonical Scenario document retained in the Experiment bundle, SHALL validate as a Scenario Task document, and SHALL exclude catalog, Experiment, result, and archive metadata. The download filename SHALL be safely derived from the Scenario identifier and end in `.json`.

Export SHALL NOT add the file to the repository or modify a task manifest. Operator guidance SHALL state that a committed scenario file must also be referenced from the destination task's `task.json`.

#### Scenario: Export active Scenario
- **WHEN** an operator exports an active Adversarial Researcher Scenario
- **THEN** the browser downloads its canonical schema-valid JSON document as one `.json` file

#### Scenario: Export archived Scenario
- **WHEN** an operator exports an archived Adversarial Researcher Scenario
- **THEN** the browser downloads the same canonical JSON document retained by the originating Experiment

#### Scenario: Export identifier is invalid
- **WHEN** an export request does not resolve to a confined scientist scenario artifact in the stated run
- **THEN** the API returns a safe not-found response without exposing filesystem paths or reading outside the artifact root
