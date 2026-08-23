## ADDED Requirements

### Requirement: Canonical decoder input mapping
Decoder callers SHALL provide relative logical attachment destinations. The contained sandbox SHALL map each logical destination below the read-only `/input` runtime root without allowing an absolute destination, traversal, destination conflict, or caller-selected host path. A decoder prompt, its input validator, and the sandbox runtime MUST use the same `/input/<logical-destination>` path.

#### Scenario: Decoder attaches a verified upload
- **WHEN** the decoder supplies the relative logical destination `<opaque-id>/<filename>`
- **THEN** generated Python can read the immutable upload only at `/input/<opaque-id>/<filename>`

#### Scenario: Decoder supplies an absolute attachment destination
- **WHEN** a decoder integration supplies `/workspace/input/<opaque-id>/<filename>` or another absolute logical destination
- **THEN** validation rejects it as an input-contract failure before Docker startup and does not classify the failure as Docker infrastructure failure

#### Scenario: Composed Docker decoder path
- **WHEN** a contained decoder integration starts with a verified upload and executes a program that reads its advertised opaque input path
- **THEN** a real Docker sandbox starts, the program reads the expected immutable bytes, its output is collected, and all resources are removed at close

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

### Requirement: Stage-specific sandbox failure reporting
The generated-code integration SHALL distinguish input validation, capacity admission, Docker startup, execution, output collection, output validation, and cleanup failures. It SHALL preserve a bounded safe stage and failure category for canonical decoder provenance and activities while keeping raw commands, paths, container identifiers, uploaded content, decoded content, and unsanitized daemon or process messages ephemeral.

#### Scenario: Attachment validation fails
- **WHEN** a logical decoder attachment violates the sandbox input contract
- **THEN** GAMR records an input-validation failure and does not report that Docker startup or Python execution occurred

#### Scenario: Docker command fails safely
- **WHEN** a Docker lifecycle command fails after valid attachments were accepted
- **THEN** GAMR records the applicable startup, execution, collection, or cleanup stage with a safe diagnostic category and no raw daemon message
