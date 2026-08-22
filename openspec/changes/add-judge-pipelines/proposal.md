## Why

GAMR's judge sequence is embedded in the experiment runner, which makes the current evidence and file-content assessment path difficult to reuse or replace for tasks that will need a different judging method. GAMR needs a task-selected, predefined judge-pipeline boundary before adding new judge behavior.

## What Changes

- Add a schema-validated `spec.judge` object to task manifests. Its `pipeline` field selects a predefined judge, with the existing judge behavior as the compatible default for legacy tasks.
- Add an explicit engine registry and common pipeline contract. Tasks select a predefined pipeline by identifier and cannot load modules, classes, prompts, or executable code.
- Implement predefined pipelines as compiled LangGraph `StateGraph` workflows with stable node names, so their topology can be inspected and visualized later without changing the task contract.
- Add `uv run poe judge-graph <judge-directory>` to render a registered judge's inspected topology as `docs/assets/judges/<pipeline-id>.png`, atomically replacing the existing image when rerun and requiring no network service.
- Move the current judge sequence behind the first predefined pipeline, `evidence-and-content`: optional collector-backed reference-content comparison followed by the existing final evidence assessment.
- Preserve the current prompts, model calls, retry limits, validation rules, conservative outcomes, diagnostics, activities, result fields, and API and web presentation.
- Record the selected pipeline identifier in canonical run results and evidence so reviewers can tell which predefined judge produced the assessment.
- Establish a repeatable source layout, registration checklist, contract-test suite, and documentation pattern for future judge pipelines.
- Keep transformed-file reading, generated-code execution, API-checking judges, and Tyr-interacting judges out of this change. They require follow-up specifications.

## Capabilities

### New Capabilities

- `judge-pipelines`: Task-level selection, validation, execution, provenance, and extension rules for predefined judge pipelines, including the behavior-preserving `evidence-and-content` pipeline.

### Modified Capabilities

None.

## Impact

- Core task and run-result models and their generated JSON schemas gain structured judge selection and judge pipeline provenance.
- The shared engine gains the LangGraph dependency, small judge-pipeline contracts, an explicit registry, and the predefined pipeline that owns the existing content and final assessment sequence.
- Root development tooling gains a Poe task, a confined offline graph-rendering script, a Pillow development dependency, and generated judge images under `docs/assets/judges/`.
- Task loading, CLI and API composition, artifact normalization, and generated web types carry the selected identifier without changing verdict behavior or sensitive-content handling.
- The current task manifest is made explicit by selecting `evidence-and-content`; legacy task manifests without `spec.judge` remain readable and select the same pipeline.
- Engine and task-format documentation define how to add and test another predefined pipeline. No new model provider, sandbox, network, or Tyr capability is introduced.
