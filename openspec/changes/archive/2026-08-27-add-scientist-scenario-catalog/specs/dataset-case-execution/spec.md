## MODIFIED Requirements

### Requirement: Scientist execution barrier
The system SHALL wait until every selected base case has reached a terminal case outcome before starting the scientist phase. Scientist iterations SHALL execute one at a time and SHALL consume the aggregated base-case history in deterministic dataset order.

Immediately before generating each scientist scenario, the system SHALL exclude every archived scientist-generated scenario from the history supplied to the scientist model. The exclusion SHALL apply to generated scenarios from earlier iterations of the active run, configured scientist history loaded from retained runs, and explicit scientist resume history. It SHALL NOT remove authored base cases, cancel a scenario already executing, or recall a scientist model request that has already started. Restoring an archived scenario SHALL make it eligible for later prompts whenever the existing history-selection configuration includes its originating run.

Persisted history-used evidence SHALL identify only the case records actually supplied to that scientist iteration.

#### Scenario: Scientist waits for slowest base case
- **WHEN** scientist iterations are enabled and base cases finish at different times
- **THEN** scientist generation does not start until the last base case finishes

#### Scenario: Scientist iterations remain serial
- **WHEN** more than one scientist iteration is configured
- **THEN** each generated scientist scenario finishes before the next iteration is generated

#### Scenario: Scenario is archived before a later active-run iteration
- **WHEN** a generated scenario is archived after its execution and before the next scientist prompt is built in the same run
- **THEN** the later prompt and its history-used evidence exclude that scenario

#### Scenario: Configured prior-run history contains an archived scenario
- **WHEN** a new run selects scientist history from a retained run containing an archived generated scenario
- **THEN** the new run excludes that scenario while preserving eligible base and active scientist history

#### Scenario: Resume source contains an archived scenario
- **WHEN** explicit scientist resume loads a source run containing an archived generated scenario
- **THEN** resumed scientist prompts exclude that scenario

#### Scenario: Archive occurs after generation starts
- **WHEN** an operator archives a scenario after a scientist model request has started
- **THEN** the current request continues and the archive decision applies before the next scientist prompt

#### Scenario: Archived scenario is restored
- **WHEN** an archived scenario is restored before a later prompt and its originating run remains selected by history configuration
- **THEN** the scenario is eligible for that later prompt's history
