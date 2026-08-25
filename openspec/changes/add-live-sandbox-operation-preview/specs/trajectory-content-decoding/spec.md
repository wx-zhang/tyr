## ADDED Requirements

### Requirement: Reusable sandbox observation integration
Every applicable trajectory decoder invocation that requests generated Python execution SHALL create one generic sandbox-operation session and route sandbox start, execute, output collection, replacement, and close work through it. Decoder analysis, route selection, comparison ordering, result provenance, attempt limits, and fail-closed behavior SHALL retain their existing meanings. Decoder lifecycle activities SHALL reference the generic operation identifier, while sandbox progress details SHALL remain pipeline-neutral and suitable for reuse by another predefined judge pipeline.

#### Scenario: Decoder executes one program
- **WHEN** trajectory decoding selects execution and its first program produces accepted derived evidence
- **THEN** the case records decoder analysis and route activities plus one generic sandbox session containing the actual execution and cleanup lifecycle

#### Scenario: Decoder retries after timeout
- **WHEN** a decoder attempt times out and a later attempt uses a replacement sandbox
- **THEN** the decoder provenance and generic session contain matching attempt order and hashes while the generic session records both logical sandbox generations

#### Scenario: Decoder is cancelled
- **WHEN** cancellation interrupts trajectory decoding during sandbox work
- **THEN** the decoder retains its existing cancellation behavior and the associated generic session terminates as cancelled after cleanup is attempted

### Requirement: Non-duplicated decoding postmortem
For new runs with generic sandbox-operation events, the sandbox session SHALL be the canonical browser presentation of executed source and structured execution results. The decoding provenance presentation SHALL continue to show decoder route, status, hashes, failure summary, and derived-file lineage without duplicating the session's attempt transcript. Historical runs that have decoding provenance but no generic session SHALL continue to show the complete bounded attempt postmortem from that provenance.

#### Scenario: New decoded run is reviewed
- **WHEN** a completed run contains both decoding provenance and generic sandbox-operation events
- **THEN** the browser shows one attempt transcript in the sandbox session and retains decoder route and lineage context in the content comparison

#### Scenario: Legacy decoded run is reviewed
- **WHEN** a completed run contains decoding attempts but no generic sandbox-operation events
- **THEN** the browser renders the bounded source and execution results from decoding provenance as before
