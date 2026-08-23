# python-execution-sandbox Specification

## Purpose

Defines bounded, backend-selectable execution of generated Python against caller-provided input trees without exposing application credentials or treating unsafe host subprocesses as a security boundary.

## Requirements

### Requirement: Process-local sandbox lifecycle
The system SHALL expose one asynchronous sandbox capability with operations to start an instance, execute Python in an existing instance, and close an instance. A successful start SHALL return a newly generated opaque sandbox ID that is valid only in the creating process. Sandbox IDs MUST NOT be persisted in canonical tasks, run bundles, or operational registries, and the system MUST NOT reconnect to an instance after a process restart. Close SHALL be idempotent, SHALL remove the instance's ephemeral storage, and SHALL make later executions for that ID fail as closed. An unknown ID MUST be rejected without affecting another instance.

#### Scenario: Sandbox completes its lifecycle
- **WHEN** a caller starts a sandbox, executes one or more fragments by its returned ID, and closes it
- **THEN** every execution addresses the same sandbox workspace and close removes the sandbox resources

#### Scenario: Closed sandbox is used again
- **WHEN** a caller executes code with an ID after that sandbox has closed
- **THEN** execution is rejected as closed and no replacement sandbox is created

#### Scenario: Sandbox is closed more than once
- **WHEN** a caller closes an already closed sandbox ID
- **THEN** close succeeds without recreating resources or affecting another sandbox

#### Scenario: Process restarts
- **WHEN** the creating GAMR process terminates and a later process receives an old sandbox ID
- **THEN** the later process rejects the ID and does not adopt an existing Docker container or host directory

### Requirement: Bounded attachment tree
Start SHALL accept zero or more attachment roots, where each root is a regular file or directory tree. Attached directories SHALL preserve their relative regular-file paths below the root name. The complete input tree MUST contain at most 256 regular files and at most 64 MiB of file content. The system MUST reject the whole start before execution when an attachment contains a symlink, special file, absolute path, empty or traversal segment, invalid UTF-8 name, or destination conflict. Destination conflicts include duplicate paths and any path that is both a file and an ancestor or descendant of another file. The accepted tree SHALL be a content snapshot exposed below `/input`, and its source host paths MUST NOT be mounted or disclosed inside the sandbox.

#### Scenario: Multiple files and directories are attached
- **WHEN** a caller starts a sandbox with uniquely named regular files and directory trees within the entry and byte limits
- **THEN** their captured contents are available at the corresponding paths below `/input`

#### Scenario: Attachment destinations conflict
- **WHEN** two attachment roots or nested entries resolve to the same input path, or a file path conflicts with a directory path
- **THEN** start fails before a sandbox ID is returned

#### Scenario: Unsafe attachment entry is supplied
- **WHEN** an attachment tree contains a symlink, device, socket, named pipe, absolute path, or parent traversal
- **THEN** start rejects the complete attachment set without starting executable code

#### Scenario: Attachment limits are exceeded
- **WHEN** the captured tree exceeds 256 regular files or 64 MiB in total
- **THEN** start fails before allocating a usable sandbox

### Requirement: Immutable input and persistent workspace
The Docker backend SHALL expose `/input` as read-only to executed Python and SHALL provide an initially empty writable `/workspace` limited to 128 MiB. Every execution SHALL start with `/workspace` as its working directory. Workspace files SHALL persist across successful executions in the same sandbox and SHALL disappear when it closes. The host-unsafe backend SHALL use separate input and workspace directories and make input read-only on a best-effort basis, but MUST identify that restriction as non-enforceable against hostile code running as the host user.

#### Scenario: Executions communicate through files
- **WHEN** one execution writes a file below `/workspace` and a later execution uses the same sandbox ID
- **THEN** the later fresh Python process can read that file

#### Scenario: Python process state is changed
- **WHEN** an execution changes globals, imported modules, environment values, or its current directory without writing those changes to the workspace
- **THEN** those process-local changes are absent from the next execution

#### Scenario: Docker execution attempts to alter input
- **WHEN** executed Python attempts to create, replace, rename, or modify a path below `/input`
- **THEN** the operation fails and the captured input remains unchanged for later executions

### Requirement: Structured Python execution result
Each execute operation SHALL accept at most 64 KiB of UTF-8 Python source and SHALL run it in a fresh Python 3.14 isolated process with only the standard library supplied by the sandbox image. Runtime package installation and network dependency retrieval MUST NOT be available. A completed execution SHALL return its exit code, separately captured stdout and stderr, elapsed duration, and explicit timeout and output-limit statuses. A normal non-zero exit or unavailable import SHALL be returned as an execution result and SHALL leave the sandbox usable. Backend startup, communication, or cleanup failures SHALL be reported distinctly from Python process results.

#### Scenario: Python succeeds
- **WHEN** valid Python finishes within every limit
- **THEN** execute returns exit code zero, its bounded stdout and stderr, elapsed duration, and false limit statuses

#### Scenario: Python exits unsuccessfully
- **WHEN** Python raises an exception, imports an unavailable third-party package, or exits non-zero without exceeding a limit
- **THEN** execute returns the non-zero result and a later execution may still use the same sandbox

#### Scenario: Source is oversized or invalid
- **WHEN** source is not valid UTF-8 or exceeds 64 KiB
- **THEN** execute rejects it without starting Python or changing the sandbox workspace

### Requirement: Fixed execution limits and terminal cleanup
The Docker backend SHALL limit each execution to 10 seconds, the sandbox to one CPU, 256 MiB of memory, 64 processes, and a 128 MiB workspace, and captured stdout plus stderr to 1 MiB per execution. The common execution contract SHALL enforce the source, attachment, duration, and output limits for every executable backend; host-level CPU, memory, process, input immutability, and workspace controls in `host-unsafe` SHALL be documented and enforced only where the host operating system supports them. When duration or output exceeds its limit, or when descendant-process cleanup cannot be confirmed, the system SHALL terminate the execution, destroy the whole sandbox, return the applicable limit status when a reliable result can be formed, and reject all later execution for that ID.

#### Scenario: Execution times out
- **WHEN** Python remains active for more than 10 seconds
- **THEN** the process and its descendants are terminated, the sandbox is destroyed, and its ID cannot be reused

#### Scenario: Execution exceeds captured output
- **WHEN** combined stdout and stderr exceeds 1 MiB
- **THEN** execution is terminated, returned output is bounded, the output-limit status is true, and the sandbox ID cannot be reused

#### Scenario: Memory or process limit terminates Docker execution
- **WHEN** Docker stops Python because it exceeds the memory or process limit
- **THEN** execute reports a non-successful bounded result or a distinct backend failure without exposing host diagnostics or leaving the instance usable when cleanup is uncertain

### Requirement: Per-sandbox execution serialization
Only one execute operation SHALL be active for a sandbox ID. A second overlapping execute for the same ID MUST be rejected immediately rather than queued. Different sandbox IDs SHALL be allowed to execute concurrently. Closing a sandbox during execution SHALL cancel the active execution, terminate its descendants, wait for cleanup to reach a known terminal state, and then complete the close.

#### Scenario: Same sandbox executes concurrently
- **WHEN** a second execute request arrives while the same sandbox ID is already executing
- **THEN** the second request is rejected without interrupting or queueing behind the active execution

#### Scenario: Different sandboxes execute concurrently
- **WHEN** execute requests overlap for different sandbox IDs
- **THEN** each may proceed subject to its own lifecycle and resource limits

#### Scenario: Active sandbox is closed
- **WHEN** close is requested while Python is executing
- **THEN** the active execution and descendants are terminated and close does not return until cleanup is terminal

### Requirement: Environment-selected backend
The system SHALL select exactly one backend from `GAMR_SANDBOX_BACKEND`, accepting `docker`, `host-unsafe`, or `disabled` and defaulting to `docker`. An unknown value MUST fail configuration validation. Backend selection SHALL be composed outside engine workflow logic so future CLI and API consumers can receive the same sandbox contract.

#### Scenario: Backend is not configured
- **WHEN** `GAMR_SANDBOX_BACKEND` is absent
- **THEN** the system selects the Docker backend

#### Scenario: Backend value is invalid
- **WHEN** `GAMR_SANDBOX_BACKEND` contains any other value
- **THEN** configuration fails before a sandbox can start

### Requirement: Docker containment profile
The Docker backend SHALL use the fixed GAMR sandbox image and MUST run each sandbox as an unprivileged user with no network, no host bind mounts, no Docker socket, no added devices, no inherited application environment or credentials, a read-only root filesystem, dropped Linux capabilities, no-new-privileges, fixed resource limits, and ephemeral input and workspace storage. Untrusted attachment names, code, and sandbox IDs MUST NOT select the image or become shell syntax, Docker command options, environment names, labels, mount sources, or container names. Containers SHALL have no restart policy and SHALL carry a non-secret GAMR label for diagnosis of orphaned instances.

#### Scenario: Code inspects its environment
- **WHEN** executed Python reads environment variables, filesystem mounts, or network interfaces
- **THEN** it cannot obtain GAMR credentials, application environment values, host-mounted files, the Docker socket, or a usable network connection

#### Scenario: Untrusted values resemble Docker options
- **WHEN** an attachment name, sandbox ID, or Python fragment begins with dashes or contains shell metacharacters
- **THEN** it remains data and cannot alter the image, containment options, command, mounts, labels, or container identity

#### Scenario: GAMR exits unexpectedly
- **WHEN** the creating process crashes before close
- **THEN** the container does not restart automatically, retains its diagnostic label if orphaned, and is never adopted automatically by a later process

### Requirement: Explicit unsafe and disabled behavior
Selecting `host-unsafe` SHALL require the exact environment value and SHALL emit a prominent warning when the backend is composed or exercised. It MUST use a fresh confined temporary input and workspace tree, a minimal environment without configured GAMR secrets, a fresh Python process per execution, and process-group termination, but every user-facing description MUST state that hostile code can access the host with the current user's permissions. Selecting `disabled` SHALL allow unrelated GAMR features to compose and operate, while sandbox start SHALL fail with a distinct unavailable error and SHALL execute no code.

#### Scenario: Host-unsafe is selected
- **WHEN** `GAMR_SANDBOX_BACKEND=host-unsafe` is configured
- **THEN** sandbox operations use the host subprocess implementation and visibly warn that it is not a security boundary

#### Scenario: Host-unsafe Python inspects application secrets
- **WHEN** host-unsafe Python reads its inherited process environment
- **THEN** configured GAMR, Tyr, collector, and model-provider secrets are absent even though host filesystem access cannot be prevented

#### Scenario: Sandbox is disabled
- **WHEN** `GAMR_SANDBOX_BACKEND=disabled` and a caller starts a sandbox
- **THEN** start fails as unavailable without executing code or preventing unrelated task, experiment, result, API, or web behavior

### Requirement: Developer image and execution commands
The repository SHALL provide `uv run poe sandbox-build` to build the fixed local Docker sandbox image and `uv run poe sandbox-run --attach <path> --code <source>` to exercise the configured backend. `--attach` SHALL accept files or directories and be repeatable, and the runner SHALL also support reading source from a file to avoid shell quoting for multiline code. The runner SHALL perform start, execute, and close through the shared sandbox contract, print the sandbox ID and structured bounded result, close in a `finally` path, and return non-zero for configuration, start, execution infrastructure, or cleanup failures. Under `disabled`, it SHALL fail without executing code; under `host-unsafe`, it SHALL print the unsafe warning.

#### Scenario: Docker image is built
- **WHEN** a developer runs `uv run poe sandbox-build` with a working Docker installation
- **THEN** the command builds the fixed local image used by the default backend or exits non-zero without reporting false success

#### Scenario: Attached input is inspected
- **WHEN** a developer runs `sandbox-run` with valid attachments and Python that reads their `/input` paths
- **THEN** the command prints the sandbox ID and structured execution result and removes the instance before exiting

#### Scenario: Multiline source is provided by file
- **WHEN** a developer supplies a source file instead of inline `--code`
- **THEN** the runner executes its UTF-8 content under the same source and execution limits

#### Scenario: Sandbox runner is disabled
- **WHEN** a developer runs `sandbox-run` with the disabled backend selected
- **THEN** the command exits non-zero and no Python fragment executes

### Requirement: Offline default verification
Default lint, type, and test checks MUST NOT require a Docker daemon, network access, live Tyr, a model provider, or human action approval. Backend contract and rejection paths SHALL be covered with controlled implementations. Runtime verification of the Docker containment profile SHALL be opt-in and marker-gated.

#### Scenario: Default tests run without Docker
- **WHEN** the repository test suite runs in an environment without Docker or network access
- **THEN** non-live sandbox tests execute and Docker runtime tests are not selected

#### Scenario: Docker integration checks are selected
- **WHEN** an operator explicitly selects sandbox Docker integration tests with Docker available
- **THEN** the tests verify lifecycle, input isolation, environment exclusion, network denial, fixed limits, and cleanup against the built image

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
