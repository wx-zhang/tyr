## Purpose

Defines bounded, isolated, and observable execution of dataset cases while preserving deterministic run results and serial scientist behavior.

## ADDED Requirements

### Requirement: Configurable base-case concurrency
The system SHALL expose `maxConcurrentCases` as experiment configuration with a default value of 5 and SHALL accept only integer values from 1 through 5 inclusive. The configured value SHALL be persisted with the run configuration and completed result. The setting SHALL apply to selected base dataset cases and SHALL NOT parallelize scientist-generated scenarios.

#### Scenario: Default concurrency
- **WHEN** an operator creates or starts an experiment without specifying `maxConcurrentCases`
- **THEN** the run configuration uses a value of 5

#### Scenario: Operator selects lower concurrency
- **WHEN** an operator configures `maxConcurrentCases` to an integer from 1 through 4 through CLI, API, or web
- **THEN** the accepted run configuration preserves that value

#### Scenario: Invalid concurrency is rejected
- **WHEN** an operator configures `maxConcurrentCases` below 1, above 5, or to a non-integer value
- **THEN** the configuration is rejected before execution starts

### Requirement: Bounded parallel base-case execution
After successful discovery, the system SHALL execute selected base dataset cases concurrently without allowing more than `maxConcurrentCases` base cases to be active at once. If fewer cases remain than the configured limit, the system SHALL execute only the remaining cases. A concurrency value of 1 SHALL preserve serial base-case execution.

#### Scenario: Five-case default execution
- **WHEN** discovery succeeds and at least five base cases are selected with the default configuration
- **THEN** no more than five base cases are active concurrently

#### Scenario: Serial compatibility mode
- **WHEN** discovery succeeds and `maxConcurrentCases` is 1
- **THEN** each selected base case finishes before the next base case starts

#### Scenario: Discovery blocks execution
- **WHEN** discovery does not produce a usable target
- **THEN** no base case starts and each selected case receives the existing blocked result behavior

### Requirement: Isolated case execution
Each concurrently executing base case SHALL maintain independent Tyr operation continuity, replay-trimming state, transcript, turn identity, evidence, and checkpoint state. Activity or response state from one case MUST NOT be consumed as the state of another case. Concurrent execution SHALL retain the existing read-only default and SHALL continue to require an explicit, recorded human decision for every Tyr action in action-enabled runs.

#### Scenario: Concurrent Tyr conversations remain separate
- **WHEN** two base cases execute concurrently and each receives a Tyr operation identifier and cumulative replies
- **THEN** each case continues only its own operation and trims replayed content only against its own prior reply

#### Scenario: Concurrent action-enabled cases request approval independently
- **WHEN** multiple action-enabled base cases reach actions concurrently
- **THEN** every action remains pending until its own Tyr-side human approval decision is recorded

### Requirement: Deterministic aggregation and failure isolation
The system SHALL store base-case results in dataset manifest order regardless of start or completion order. An expected case-level failure SHALL produce that case's result and SHALL NOT cancel other selected cases. Run cancellation SHALL cancel every active and pending case and SHALL retain the existing cancelled run outcome.

#### Scenario: Cases complete out of order
- **WHEN** later dataset cases finish before earlier dataset cases
- **THEN** the completed result lists all base cases in dataset manifest order

#### Scenario: One case fails
- **WHEN** one concurrent case returns a case-level failure while other cases remain active
- **THEN** the failed case is recorded and the other cases continue to their own outcomes

#### Scenario: Run is cancelled
- **WHEN** the operator cancels a run with multiple active or pending base cases
- **THEN** all case work is cancelled and no pending base case is started afterward

### Requirement: Scientist execution barrier
The system SHALL wait until every selected base case has reached a terminal case outcome before starting the scientist phase. Scientist iterations SHALL execute one at a time and SHALL consume the aggregated base-case history in deterministic dataset order.

#### Scenario: Scientist waits for slowest base case
- **WHEN** scientist iterations are enabled and base cases finish at different times
- **THEN** scientist generation does not start until the last base case finishes

#### Scenario: Scientist iterations remain serial
- **WHEN** more than one scientist iteration is configured
- **THEN** each generated scientist scenario finishes before the next iteration is generated

### Requirement: Concurrent case observability
Live and persisted run evidence SHALL represent every selected case independently, including multiple cases that are active at the same time. Case progress SHALL distinguish pending, active execution, assessment, and terminal outcomes. A case update SHALL NOT overwrite another active case's latest checkpoint state, and browser responses SHALL NOT expose operation identifiers, idempotency keys, credentials, or configured secrets.

#### Scenario: Multiple cases are active
- **WHEN** two or more base cases are executing concurrently
- **THEN** run visualization identifies every active case and displays each case's current state independently

#### Scenario: One active case advances
- **WHEN** one active case enters assessment while another remains in Tyr execution
- **THEN** both case states remain visible without either state being reduced to unknown

#### Scenario: Concurrent checkpoint updates are persisted
- **WHEN** multiple cases have pending or completed external turns at overlapping times
- **THEN** each case retains its own latest checkpoint state without exposing protected request metadata
