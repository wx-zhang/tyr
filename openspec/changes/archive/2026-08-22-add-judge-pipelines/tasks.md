## 1. Task and Result Contracts

- [x] 1.1 Add failing core tests for explicit `spec.judge.pipeline: evidence-and-content`, legacy defaulting when `spec.judge` is absent, rejection of unknown pipelines, extra judge fields, import paths, URLs, and executable-looking values; run them and confirm the expected failures.
- [x] 1.2 Add failing core tests for optional `RunResult.judgePipeline` provenance, acceptance of `evidence-and-content`, rejection of unknown values, and loading legacy results with no pipeline field; run them and confirm the expected failures.
- [x] 1.3 Add the strict judge identifier and configuration models, add `TaskSpec.judge` with the behavior-preserving default, and add optional run-result provenance; make the focused core tests pass without adding engine or LangGraph concerns to core.
- [x] 1.4 Add `"judge": {"pipeline": "evidence-and-content"}` to `tasks/exfiltrate-important-txt/task.json`, update task fixtures, and prove explicit and defaulted manifests load to the same selected pipeline.

## 2. LangGraph Pipeline Foundation

- [x] 2.1 Add `langgraph>=1.2,<2` to `gamr-engine`, update `uv.lock`, and verify the resolved package imports under the repository's Python 3.14 environment.
- [x] 2.2 Add failing engine contract tests for a minimal `JudgeRequest`, `JudgeRuntime`, validated `JudgeResult`, and a pipeline protocol that exposes an identifier, compiled graph, and asynchronous run method.
- [x] 2.3 Add failing registry tests proving `evidence-and-content` resolves, duplicate identifiers cannot be composed, unknown identifiers fail closed, and task-controlled strings never become imports or filesystem lookups.
- [x] 2.4 Implement the small contracts and explicit immutable registry under `gamr_engine/judges/`; make the focused contract and registry tests pass with no decorators, entry points, discovery, middleware, or generic plugin framework.
- [x] 2.5 Add failing topology tests for the named content comparison, execution-failure, evidence assessment, and finalization stages, their conditional paths, side-effect-free inspection, and fresh state across repeated invocations.

## 3. Evidence-and-Content Graph

- [x] 3.1 Add characterization coverage around the current runner before rerouting it, capturing model prompts and call order, retry counts, content results, assessment fields, diagnostics paths, assessment activities, and serialized case results for representative success and failure cases.
- [x] 3.2 Add failing graph tests for reference-aware file comparison, confirmed and not-found overlap, absent or unavailable content, no applicable reference, a recovered content response, a recovered final response, provider failure, and the execution-error shortcut with and without checked content.
- [x] 3.3 Implement the `evidence-and-content` `StateGraph` with fresh typed state, named asynchronous nodes, one conditional route, no checkpointer or store, and reuse of the existing `ContentAssessmentPipeline` and `AssessmentService`; make the graph and topology tests pass.
- [x] 3.4 Add failing parity tests comparing graph output with the characterization fixtures for objective status, verdict, summary, evidence turn IDs, assessment status and failure, reason codes, missing evidence, content overlap, diagnostics, and activity ordering.
- [x] 3.5 Complete behavior parity, including base and scientist cases, while keeping existing prompts, schemas, multimodal handling, retries, validation, and safe fallbacks unchanged; make every parity test pass.
- [x] 3.6 Add security regression tests proving graph state is not persisted, raw reference and upload content still reach only the existing content judge, the final judge receives only safe overlap data, and diagnostics, results, API data, and browser data retain current secret exclusions.
- [x] 3.7 Add a regression test proving an unreadable transformed upload keeps the current unavailable or inconclusive outcome and triggers no reading-plan model call, generated program, sandbox, API request, or new Tyr conversation.

## 4. Shared Runner and Composition

- [x] 4.1 Add failing runner tests proving explicit and legacy-defaulted task selection resolve the same pipeline, a task without evaluation skips the registry, and each selected base or scientist case invokes the pipeline once.
- [x] 4.2 Route the post-execution judge sequence through the registry and selected graph, leaving collector verification before the graph and case construction plus verification attachment after it; remove the superseded orchestration only after the focused runner tests pass.
- [x] 4.3 Add failing CLI and API composition tests proving both use the same registry and produce equivalent calls and results for identical task, evidence, and model inputs.
- [x] 4.4 Compose the same registry through the shared execution service for CLI, API, normal execution, and scientist resume; make the composition tests pass without adding a CLI, API, or environment override for judge selection.
- [x] 4.5 Verify every new or changed source file remains under 300 lines; split only the pipeline implementation if needed and update `packages/engine/AGENTS.md` for every new seam.

## 5. Provenance, API, and Web

- [x] 5.1 Add failing artifact normalization tests for pipeline provenance on base and scientist evaluation turns, deterministic ordering, redaction, malformed values, and legacy result bundles without the field.
- [x] 5.2 Carry the validated result pipeline identifier into normalized evaluation evidence while preserving existing content-overlap and assessment data; make the focused adapter tests pass.
- [x] 5.3 Add failing API tests proving completed run results and evaluation turns expose `evidence-and-content`, legacy results remain readable, and no LangGraph state, runtime objects, prompts, raw content, or credentials are exposed.
- [x] 5.4 Extend API mappings and DTOs with optional judge pipeline provenance and make the focused API tests pass without changing authorization or bundle-confinement behavior.
- [x] 5.5 Add failing web behavior tests for a concise pipeline label alongside the existing judge assessment, unchanged content-comparison rendering, legacy omission, and accessible text at desktop and mobile widths.
- [x] 5.6 Render optional judge pipeline provenance using generated types and existing evaluation-detail patterns; make the focused web tests pass without exposing or rendering the graph in this change.

## 6. Judge Graph Image Job

- [x] 6.1 Add failing critical-path tests for the renderer covering a valid direct registered judge directory, missing paths, file paths, outside paths, `..` traversal, symlink escapes, nested and unregistered directories, and proof that the supplied path is never imported; run them and confirm the expected failures.
- [x] 6.2 Add failing rendering tests for stable node and edge ordering, PNG signature and non-zero dimensions, safe labels, repeated output, atomic replacement, and preservation of an existing PNG after topology or image-write failure.
- [x] 6.3 Add `pillow>=12.3,<13` to the root development dependencies and update `uv.lock`; implement the confined offline renderer in `scripts/render_judge_graph.py` using registered LangGraph topology, deterministic breadth-first placement, and no browser, Graphviz, model, Tyr, collector, or network access; make the focused tests pass.
- [x] 6.4 Add the root `judge-graph` Poe task and a command-level test proving `uv run poe judge-graph packages/engine/src/gamr_engine/judges/evidence_and_content` selects the registered pipeline and reports `docs/assets/judges/evidence-and-content.png`.
- [x] 6.5 Run the job to create `docs/assets/judges/evidence-and-content.png`, rerun it to prove the same target is replaced successfully, and verify the committed file is a non-empty PNG showing every registered node and edge.

## 7. Schemas and Documentation

- [x] 7.1 Regenerate task, run-result, operational, OpenAPI, and web client schemas; validate explicit, defaulted, unknown-pipeline, new-result, and legacy-result examples.
- [x] 7.2 Update `docs/task-format.md` and README task examples with the `spec.judge` JSON object, its legacy default, task ownership, and the rule that JSON selects only predefined pipelines.
- [x] 7.3 Update `packages/engine/AGENTS.md` with the judge directory map, stable graph-node convention, registry ownership, focused test command, and the five-step checklist for adding a predefined judge; update `scripts/AGENTS.md`, `docs/AGENTS.md`, and `tests/AGENTS.md` for the renderer, generated image ownership, and test location.
- [x] 7.4 Update architecture and development documentation with the shared graph execution path, LangGraph dependency, lack of checkpointing or LangSmith, side-effect-free topology inspection, `uv run poe judge-graph <judge-directory>`, overwrite behavior, and the boundary between this refactor and future content-decoding or external-interaction judges.

## 8. Verification

- [x] 8.1 Run focused core, engine judge, runner, renderer, adapter, API, and web tests while iterating, preserving the required failing-test then smallest-passing-implementation loop.
- [x] 8.2 Run task and result schema generation, `uv run gamr task validate tasks/exfiltrate-important-txt`, graph topology inspection, and the graph-image job without executing a model, Tyr request, collector load, browser, or network request.
- [x] 8.3 Run `uv run poe check` and the complete deterministic web suite; fix any behavior or documentation regression without enabling live Tyr or action approval.
- [x] 8.4 Verify the existing run detail at desktop and 375px-wide mobile viewports: pipeline provenance is readable, content comparison and final assessment are unchanged, and no graph state or sensitive content appears.
