## Context

See `proposal.md` for motivation and `specs/judge-pipelines/spec.md` for the behavior contract. Today `ExperimentRunner._run_case` owns the judging sequence directly. It verifies collector evidence, optionally calls `ContentAssessmentPipeline`, handles the existing execution-error shortcut, calls `AssessmentService`, enriches reason codes and missing evidence, emits assessment activities, and builds the case result.

The content and final assessment services already have focused contracts and tests. The change should preserve those services and their prompts. The architectural seam belongs around their orchestration, not inside either judge call.

LangGraph's Graph API models workflows with typed state, named nodes, edges, and a compiled graph. Compiled graphs also expose their topology as Mermaid, which gives GAMR a direct path to later flow visualization without defining a second diagram model.

## Goals / Non-Goals

**Goals:**

- Let `task.json` select one predefined judge pipeline.
- Express the existing judge sequence as a small compiled graph.
- Make the selected graph easy to locate, test, inspect, and later visualize.
- Generate an up-to-date PNG of any registered judge graph through one root uv command.
- Keep pipeline extension explicit and repeatable.
- Preserve all current judge behavior and security boundaries.

**Non-Goals:**

- Adding another judge pipeline in this change.
- Making prompts, graph nodes, edges, or Python imports configurable from task files.
- Adding checkpointing, resumable judge graphs, LangSmith, graph persistence, or a graph editor.
- Exposing graph visualization through the API or web UI yet.
- Reading transformed files, executing generated code, calling arbitrary APIs, or starting new Tyr conversations from a judge.

## Decisions

### Select a closed judge configuration from task.json

Add a strict core model conceptually shaped as:

```text
JudgeConfig
  pipeline: evidence-and-content
```

`TaskSpec.judge` contains this object and defaults to the same value when absent. The current task writes the object explicitly. `extra="forbid"` and the pipeline enum reject arbitrary configuration and code-like identifiers during normal task validation.

Judge selection is task-owned. CLI flags, API run forms, environment variables, scenario text, and model output cannot override it. The selected identifier is copied into the completed `RunResult` as optional `judgePipeline` provenance and into normalized evaluation evidence. The result field remains optional so old bundles load unchanged. A task with no evaluation plan still records the resolved task pipeline in its task snapshot but does not run it; the completed result omits judge provenance because no judge produced an assessment.

Putting the identifier in `evaluation.json` was considered. `task.json` is the better ownership boundary because it already chooses the evaluation plan and cases, and the user needs to see the task's judge without opening a second file. A bare string was considered, but the object gives future predefined pipelines a schema-owned place for their small validated settings without introducing arbitrary dictionaries now.

### Use one small LangGraph abstraction

Add `langgraph>=1.2,<2` only to `gamr-engine`. Use `StateGraph` with a typed state, named asynchronous nodes, normal edges, and one conditional edge. Compile each predefined graph once when the judge registry is built. Invoke it with fresh state for every case and no checkpointer or store.

The common surface stays small:

```text
JudgePipeline
  id
  graph
  run(request, runtime) -> JudgeResult

JudgeRequest
  rendered scenario
  transcript and turn IDs
  execution error
  collector verifications
  evaluation plan and optional reference

JudgeRuntime
  judge model
  content evidence provider
  artifact store
  activity emitter
  run and case identity

JudgeResult
  assessment fields
  assessment status and safe failure
  optional content-overlap result
```

The compiled graph is the pipeline. `run` only validates initial state, invokes the graph asynchronously, and validates the terminal result. There is no separate pipeline engine, base node class, middleware layer, event bus, or generic graph configuration format.

A plain Python strategy object was considered. It would be smaller for one sequence, but it would require GAMR to invent a topology model later for visualization. LangGraph already provides compilation checks and `graph.get_graph().draw_mermaid()` from the same named nodes that execute.

### Keep registry composition explicit

Create one immutable mapping from `JudgePipelineId` to a constructed `JudgePipeline`. Build it in the shared engine composition used by both CLI and API. Resolution fails closed if the schema and registry ever drift.

Do not use decorators, entry points, import strings, filesystem discovery, or mutable global registration. A new predefined judge follows this checklist:

1. Add its strict JSON configuration variant and identifier in core.
2. Add one directory under `gamr_engine/judges/` containing state, nodes, and graph construction.
3. Register its constructed pipeline in the explicit registry.
4. Add contract, topology, behavior, failure, and security tests.
5. Update task-format and engine documentation plus generated schemas.

The initial layout is:

```text
packages/engine/src/gamr_engine/judges/
  contracts.py
  registry.py
  evidence_and_content/
    pipeline.py
packages/engine/tests/judges/
  test_registry.py
  test_evidence_and_content.py
```

The pipeline remains in one implementation file while it fits the 300-line gate. Split state or nodes only when the file would cross that limit. The nearest `AGENTS.md` documents this layout and checklist.

### Model the current judge sequence directly

The first graph is:

```text
START
  -> compare_reference_content
  -> route_after_content
       -> preserve_execution_failure -> END
       -> assess_evidence
            -> finalize_judgment -> END
```

`compare_reference_content` invokes the existing content pipeline only when the current reference-aware file conditions hold. Otherwise it stores no content result. `route_after_content` reproduces the current rule: an execution error without checked content takes the existing early case result; all other cases continue.

`assess_evidence` builds the existing prompt and calls the existing `AssessmentService`. `finalize_judgment` applies the current failed-assessment fallback, collector and content reason codes, missing evidence, and completed activity fields. The alternate terminal node preserves the current unknown assessment status, objective status, verdict, summary, and evidence-turn selection for an execution failure.

Collector verification stays before the graph because it is execution evidence gathering shared with case results, not a judge decision. Attaching verification evidence and constructing the final `CaseResult` stay after the graph. This keeps nodes focused and avoids duplicating case persistence.

Existing content and assessment diagnostics retain their paths. Nodes use the runtime's existing artifact port and activity emitter, so `assessment.started` still occurs before the final model call and `assessment.completed` still occurs after validation. The graph adds no new user-visible stage activities in this change.

### Make topology inspectable without making it an API

Use stable snake-case node identifiers that describe domain stages. A focused topology test calls the compiled graph's inspection API and asserts the node and edge set. A Mermaid snapshot is unnecessary because formatting can change between LangGraph versions; the semantic node and edge set is the contract.

The registry exposes constructed pipeline objects to engine code, so a later change can serialize `pipeline.graph.get_graph().draw_mermaid()` or stream node execution. This change does not persist diagrams or expose LangGraph types through core, API, or task schemas.

### Render documentation PNGs offline

Add a root Poe task:

```text
uv run poe judge-graph <judge-directory>
```

The task calls `scripts/render_judge_graph.py`. The script resolves the repository root and the supplied real path, requires the path to be a direct directory beneath `packages/engine/src/gamr_engine/judges/`, converts its snake-case directory name to the corresponding kebab-case pipeline identifier, and resolves that identifier through the fixed registry. It never imports a module from the supplied path. This keeps the developer command consistent with runtime selection and closes path and symlink escapes.

The script obtains nodes and edges through the compiled graph inspection API. It uses `pillow>=12.3,<13` from the root development dependency group to draw a deterministic white-background PNG with labeled boxes and directed edges. A small breadth-first layout places nodes by distance from the start node, sorts nodes and edges for stable output, and draws backward edges without attempting a general graph-layout framework. This is sufficient for readable registered judge graphs while avoiding Graphviz, browser automation, Mermaid services, and network access.

The output is always `docs/assets/judges/<pipeline-id>.png`. Rendering happens in a temporary file in the target directory. The script validates the PNG before replacing the destination with `Path.replace`, so a failed render leaves an earlier image intact. Successful reruns update the existing file. The command prints the repository-relative output path and exits nonzero with a concise error for invalid paths, unregistered directories, topology errors, or image-write failures.

Focused tests call the rendering functions with temporary destinations and fake graph topology. They cover the successful PNG signature and dimensions, deterministic node and edge ordering, overwrite behavior, atomic failure, missing paths, file paths, outside paths, symlink escapes, and unregistered directories. One command-level test uses the real registry but does not invoke a model, Tyr, collector, browser, or network. The implementation workflow runs the command once for `evidence_and_content` and commits the resulting PNG.

## Risks / Trade-offs

- [A framework dependency is added before the second pipeline exists] -> Keep use limited to `StateGraph`, named nodes, edges, compilation, async invocation, and topology inspection; prohibit framework-specific types outside `gamr_engine.judges`.
- [Refactoring a security verdict path changes behavior accidentally] -> Add characterization and parity tests before moving orchestration, then assert prompts, model calls, retries, diagnostics, activities, and serialized case fields.
- [Graph state retains sensitive evidence] -> Use a fresh in-memory state per case, configure no checkpointer or store, never serialize graph state, and preserve existing diagnostic redaction.
- [Task selection becomes a code-loading surface] -> Use a closed schema enum and explicit registry; never resolve imports or files from JSON.
- [Stable node names constrain future refactors] -> Treat names as inspectable topology only, not persisted run data in this change; change them later with an intentional visualization-contract update.
- [LangGraph releases change inspection details] -> Bound the dependency to major version 1 and test semantic topology instead of rendered Mermaid text.
- [A documentation renderer becomes a path-controlled write tool] -> Confine real paths to direct registered judge directories, derive a fixed docs target from the registry identifier, and replace only after a valid temporary PNG exists.
- [Custom layout becomes a second workflow engine] -> Read only inspected nodes and edges, keep one deterministic breadth-first layout, and defer interactive or execution-aware visualization to a later change.

## Migration Plan

1. Add the optional task judge configuration, optional run-result provenance, and legacy-loading tests.
2. Add LangGraph to `gamr-engine` and establish contracts plus explicit registry.
3. Add current-behavior characterization tests, then implement the graph and route the runner through it.
4. Make the current task's `task.json` explicitly select `evidence-and-content`.
5. Add the offline renderer and root Poe task, generate the first registered judge PNG, and document the command.
6. Carry provenance through artifact normalization, API DTOs, generated schemas, and the existing web evaluation detail.
7. Update module maps and the repeatable new-judge guide, then run the full deterministic checks.

Rollback removes the task's explicit `judge` object and restores direct runner orchestration. Legacy task and run-result tolerance means no canonical task or completed run bundle needs rewriting.
