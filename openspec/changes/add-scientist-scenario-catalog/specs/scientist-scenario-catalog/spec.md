## Purpose

Provides a safe operator catalog for reviewing, filtering, exporting, archiving, and restoring scientist-generated scenarios across retained runs.

## ADDED Requirements

### Requirement: Scientist scenario catalog
The system SHALL expose every valid scientist-generated scenario retained by an existing run as a catalog entry. Each entry SHALL contain the canonical scenario document, originating task and run, archive state, and matching case result when one exists. Entries SHALL be ordered by originating run from newest to oldest with a deterministic order within each run.

When a matching case result does not yet exist, the entry SHALL report `pending` while its run can still produce a result and `unavailable` after its run becomes terminal. The catalog SHALL preserve `vulnerable`, `protected`, `inconclusive`, and `not_applicable` as distinct security verdicts.

#### Scenario: Completed scientist scenario is listed
- **WHEN** a retained run contains a valid scientist scenario and a matching case result
- **THEN** the catalog returns its canonical definition, originating task and run, archive state, and security verdict

#### Scenario: Active scenario has no result yet
- **WHEN** a scientist scenario has been persisted but its originating run can still produce the matching case result
- **THEN** the catalog lists the scenario with result state `pending`

#### Scenario: Terminal run has no scenario result
- **WHEN** a scientist scenario remains in a terminal run without a matching case result
- **THEN** the catalog lists the scenario with result state `unavailable`

#### Scenario: Source run no longer exists
- **WHEN** an originating run and its evidence have been deleted through the existing run-deletion behavior
- **THEN** its scientist scenarios no longer appear in either catalog view

### Requirement: Scenario browsing and origin navigation
The web application SHALL provide a scientist scenario page reachable from primary navigation. Active scenarios SHALL be shown by default, archived scenarios SHALL be available in a separate view, and each entry SHALL expose its full scenario definition and a link to the originating run case.

The full definition SHALL include the scenario identifier, title, tags, objective, steps, success criteria when present, expected control, evidence requirements, and collector-evidence mode when present.

#### Scenario: Operator browses an active scenario
- **WHEN** an operator opens the scientist scenario page and expands an active entry
- **THEN** the complete retained scenario definition and result summary are available without opening the run

#### Scenario: Operator follows the origin link
- **WHEN** an operator activates a scenario's run link
- **THEN** the application opens the originating run with that scenario case selected

#### Scenario: Operator views archived scenarios
- **WHEN** an operator selects the Archived view
- **THEN** only archived entries are listed with restore and export actions

### Requirement: Security verdict filtering
The catalog SHALL allow operators to filter the selected Active or Archived view by one result value. Supported values SHALL be `vulnerable`, `protected`, `inconclusive`, `not_applicable`, `pending`, and `unavailable`. Clearing the filter SHALL restore every entry in the selected archive view.

#### Scenario: Filter by security verdict
- **WHEN** an operator selects the `protected` result filter
- **THEN** only scenarios whose matching case result has verdict `protected` are shown in the current archive view

#### Scenario: Filter scenarios awaiting results
- **WHEN** an operator selects the `pending` result filter
- **THEN** only persisted scientist scenarios whose runs can still produce a matching result are shown

#### Scenario: Clear result filter
- **WHEN** an operator clears an active result filter
- **THEN** all scenarios in the selected Active or Archived view are shown again

### Requirement: Reversible scenario archiving
The system SHALL allow an operator to archive an active scientist scenario and restore an archived scenario. Archive state SHALL be scoped to the scenario artifact in its originating run so scenarios with the same scenario identifier in different runs remain independent.

Archiving and restoring SHALL be idempotent and SHALL NOT modify or delete the originating scenario artifact, run result, transcript, activity, or other run evidence. The interface SHALL explain that archiving hides the entry from the active catalog, excludes it from later scientist history, preserves run evidence, and can be reversed.

#### Scenario: Archive an active scenario
- **WHEN** an operator archives an active scientist scenario
- **THEN** it moves to the Archived view while every file in its originating run bundle remains unchanged

#### Scenario: Restore an archived scenario
- **WHEN** an operator restores an archived scientist scenario
- **THEN** it moves to the Active view and its originating evidence remains unchanged

#### Scenario: Repeated archive request
- **WHEN** an already archived scenario is archived again
- **THEN** the request succeeds without creating a duplicate archive record or changing run evidence

#### Scenario: Same scenario ID exists in another run
- **WHEN** an operator archives one of two catalog entries with the same scenario identifier but different originating runs
- **THEN** only the selected originating entry becomes archived

### Requirement: Canonical JSON export
The system SHALL allow one active or archived scientist scenario at a time to be downloaded as a JSON file. The response body SHALL be the exact canonical scenario document retained in the run bundle, SHALL validate as a scenario task document, and SHALL exclude catalog, run, result, and archive metadata. The download filename SHALL be safely derived from the scenario identifier and end in `.json`.

Export SHALL NOT add the file to the repository or modify a task manifest. Operator guidance SHALL state that a committed scenario file must also be referenced from the destination task's `task.json`.

#### Scenario: Export active scenario
- **WHEN** an operator exports an active scientist scenario
- **THEN** the browser downloads its canonical schema-valid JSON document as one `.json` file

#### Scenario: Export archived scenario
- **WHEN** an operator exports an archived scientist scenario
- **THEN** the browser downloads the same canonical JSON document retained by the originating run

#### Scenario: Export identifier is invalid
- **WHEN** an export request does not resolve to a confined scientist scenario artifact in the stated run
- **THEN** the API returns a safe not-found response without exposing filesystem paths or reading outside the artifact root
