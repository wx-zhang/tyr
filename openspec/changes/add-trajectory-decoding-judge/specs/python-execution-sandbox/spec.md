## ADDED Requirements

### Requirement: Confined workspace output collection
The sandbox capability SHALL allow a caller to collect a bounded snapshot of regular files below a designated workspace output directory after Python execution is no longer active. Collection MUST return logical relative paths and bytes without exposing the container name, volume name, host paths, or files outside that directory. The snapshot MUST contain at most 256 regular files and at most 64 MiB in total.

Collection SHALL reject the complete snapshot without returning partial file content when it encounters a symlink, special file, invalid UTF-8 name, absolute or traversal path, destination conflict, excessive file count, excessive byte count, concurrent execution, unknown sandbox, or closed sandbox. Collection MUST NOT follow links or read through paths that resolve outside the output directory.

#### Scenario: Valid output tree is collected
- **WHEN** completed Python writes a bounded tree of regular files below the designated output directory
- **THEN** collection returns a content snapshot with relative logical paths and leaves the sandbox available until close

#### Scenario: Output tree contains a symlink
- **WHEN** generated code places a symlink anywhere in the designated output tree
- **THEN** collection rejects the whole tree without following the link or returning another output file

#### Scenario: Output exceeds collection limits
- **WHEN** the output tree exceeds 256 regular files or 64 MiB
- **THEN** collection fails with a validation error and returns no partial snapshot

#### Scenario: Collection overlaps execution
- **WHEN** collection is requested while Python is active in the same sandbox
- **THEN** collection is rejected immediately without interrupting the execution

### Requirement: Generated-code judge requires secure containment
When `evidence-and-content` executes model-generated Python, GAMR SHALL require the Docker sandbox containment profile. The disabled backend SHALL produce a distinct unavailable result. The host-unsafe backend MUST NOT execute judge-generated code, even when it was explicitly selected for developer sandbox commands. GAMR MUST NOT automatically substitute another backend after secure sandbox startup or execution fails.

#### Scenario: Docker backend is available
- **WHEN** `evidence-and-content` requests decoder code execution and the configured Docker sandbox starts successfully
- **THEN** generated Python runs only within the Docker containment profile

#### Scenario: Sandbox is disabled
- **WHEN** the decoder pipeline requires execution while the sandbox backend is disabled
- **THEN** no code runs and decoding fails closed as sandbox unavailable

#### Scenario: Host-unsafe backend is configured
- **WHEN** the decoder pipeline requires execution while `host-unsafe` is selected
- **THEN** GAMR refuses judge code execution and does not start a host subprocess

#### Scenario: Docker execution fails
- **WHEN** Docker startup, communication, execution, output collection, or cleanup fails
- **THEN** GAMR reports a safe sandbox failure and does not retry through host execution
