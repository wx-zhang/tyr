## Why

Researchers repeatedly spend model turns and Tyr interactions rediscovering a target they already know, slowing otherwise identical Experiment runs. A reusable, validated discovery input should let operators skip live discovery while preserving explicit provenance and an opt-in recovery path for stale targets.

## What Changes

- Add a versioned discovery-input JSON document containing an informational Task ID and one complete target candidate: path, workspace, agent, and Bridge ID.
- Allow the CLI to load that document from a local path and allow the web UI to select the document from the researcher's machine.
- Store the validated document in the Experiment Preset and copy it into each resulting Experiment configuration.
- Skip live discovery when a valid document is present, while recording that the target was operator-provided rather than discovered through Tyr or a model.
- Add an opt-in fallback that performs a minimal preflight before any Scenario Execution and runs normal discovery only when the provided target is unavailable.
- Reject malformed or incomplete documents before an Experiment starts; retain the Task ID for human reference without enforcing a match against the selected Task.

## Capabilities

### New Capabilities

- `provided-discovery-input`: Defines the reusable input document, CLI and web configuration behavior, target-selection semantics, fallback behavior, and provenance requirements.

### Modified Capabilities

None.

## Impact

- Core Experiment configuration and JSON schema models.
- Shared engine discovery orchestration, prompt provenance, activity events, and run-bundle discovery evidence.
- CLI Experiment options and local JSON loading.
- API Experiment Preset request/response models and persisted registry records.
- Web Experiment Preset form, JSON file selection, configuration review, and generated API types.
- Generated schemas, relevant behavior documentation, and focused core, engine, CLI, API, and web tests.
