## Context

See `proposal.md` for motivation and `specs/langfuse-observability/spec.md` for observable requirements. GAMR currently routes model work through small engine protocols implemented by `OpenAICompatibleModel`, persists canonical evidence under `.gamr`, and composes the same experiment engine from CLI and API entrypoints. Judge orchestration already uses LangGraph, while model calls remain direct OpenAI-compatible SDK calls.

The integration must cover concurrent API runs and short-lived CLI commands, retain sensitive evidence verbatim in a loopback-only local service, and remain unable to affect execution results. Langfuse is therefore a non-authoritative projection, not a workflow dependency.

## Goals / Non-Goals

**Goals**

- Keep provider and Langfuse concerns outside `gamr-core` and `gamr-engine` implementations.
- Give every model generation stable run, case, phase, role, iteration, and attempt ancestry when those dimensions exist.
- Isolate concurrent async workflows using context-local observation state.
- Preserve existing OpenAI-compatible requests, responses, structured-output fallback, reasoning recovery, and tool-call behavior.
- Make tracing failure visible but harmless.

**Non-Goals**

- Do not replace `.gamr` artifacts, activities, schemas, or reports.
- Do not use Langfuse for prompt storage, runtime configuration, resume state, or result evaluation.
- Do not trace Tyr, collector, sandbox, or artifact operations as standalone spans in this change.
- Do not migrate model gateways or workflow orchestration to LangChain.
- Do not implement automatic Langfuse retention or deletion coupling.

## Decisions

### 1. Add a vendor-neutral optional trace port to the engine

Define a small engine protocol for opening observations, updating terminal output or failure state, attaching categorical scores, reporting diagnostics, and flushing queued telemetry. The protocol exposes GAMR concepts such as observation name, kind, input, output, metadata, session identity, and score value; it exposes no Langfuse classes.

`ExperimentExecutionService`, `ExperimentRunner`, `ChatSession`, decoder execution, and judge evaluation receive the optional port through existing composition paths. `None` means tracing is disabled; no no-op implementation is required.

The Langfuse implementation belongs under `gamr-adapters`. It translates generic observations and scores to the SDK and owns all SDK exceptions.

**Alternative considered:** instrument only `OpenAICompatibleModel`. This is smaller but cannot reliably create run, case, source-lineage, and scientist-attempt hierarchy.

**Alternative considered:** import Langfuse decorators in engine functions. This violates the existing package boundary and makes tests and future observability changes vendor-specific.

### 2. Keep the regular OpenAI client and create generations explicitly

`OpenAICompatibleModel` continues to use `openai.AsyncOpenAI`. Around each provider request it opens a generation through the trace port, then records the exact request, provider response fields, duration, usage, finish reason, reasoning fields, and error state available at that boundary.

Manual generation observations provide two guarantees:

- tracing errors can be caught independently from provider errors;
- current structured-output fallback and OpenRouter-specific response normalization remain unchanged.

Each call uses a stable semantic name based on its current parent phase and operation. Parent observations distinguish agent, scientist, judge, decoder, chat, and evaluation roles even when one model instance serves several roles.

**Alternative considered:** replace the import with `langfuse.openai.AsyncOpenAI`. The drop-in wrapper is convenient, but it couples instrumentation to request execution and makes the strict failure-isolation guarantee harder to test.

### 3. Use context-local nesting with explicit stable identities

The trace adapter uses the SDK's context propagation for nesting. Engine context managers establish observations at these boundaries:

```text
experiment run
├── discovery
│   └── generation
├── case:<case-id>
│   ├── case turn generation
│   ├── decoder attempt:<n>
│   │   └── generation
│   └── assessment
│       └── generation
└── scientist iteration:<n>
    ├── generation attempt:<n>
    └── case:<scientist-case-id>
```

One experiment run is one trace. A new base run starts a session derived from its own run ID. `resume_scientist` derives the session identity from `source_run_id`, so each resumed run is a separate trace in the source lineage session.

One chat user turn is one trace, grouped by the Tyr conversation ID. One judge evaluation invocation is one session; each evaluated case is a child observation under its invocation trace.

Observation metadata uses bounded scalar values and includes only dimensions already known by the current workflow. It does not fabricate an operator identity.

Async task-local context prevents concurrent runs from inheriting each other's current observation. Dedicated concurrency tests prove this invariant.

### 4. Project scores only after canonical results exist

A case observation remains open until the existing case result and assessment are available. Before closing it, the engine submits categorical scores using exact enum values for:

- security verdict;
- objective status;
- assessment status;
- execution outcome, when present.

The run trace receives the final run outcome only after `RunResult` is finalized. Chat traces do not receive invented success scores. Judge evaluation traces use only outcomes already produced by the existing evaluation contract.

Score export failure is handled like any other tracing failure and cannot modify the canonical result.

### 5. Centralize best-effort failure handling and diagnostics

Every trace-port operation catches SDK exceptions and returns control without changing the wrapped workflow. Model-provider exceptions still propagate through existing GAMR handling and are recorded as generation failures when possible.

Diagnostics are bounded to one warning per tracing stage and workflow identity, plus one flush warning at process shutdown. Experiment diagnostics use the existing activity/progress path without adding result errors. CLI-only workflows write a concise warning to the existing console path. API lifecycle failures use the application logging path.

Tracing does not add model retries, provider retries, or workflow retries.

### 6. Configure tracing explicitly and share one process client

`Settings` adds an explicit `GAMR_LANGFUSE_ENABLED` boolean and local Langfuse connection settings. The adapter factory returns `None` unless enablement is true. When enablement is true but required settings are invalid, composition emits a diagnostic and continues without tracing.

One Langfuse client is shared per process so context propagation, batching, and connection reuse work across workflows. Each model gateway receives the same optional trace port used by its parent workflow.

CLI commands flush after their workflow reaches a terminal result and before exit. API lifespan shutdown first stops queued/running work through the existing manager, then flushes Langfuse. Flush is bounded and best-effort.

Credentials are server-side configuration and never enter browser configuration or run metadata.

### 7. Keep source prompts and canonical artifacts independent

The integration sends verbatim model-boundary content to local Langfuse but does not read prompts, state, scores, or results back from it. Prompt text remains source-controlled. `.gamr` remains the only persisted source used by display, validation, reporting, history, and resume behavior.

The local Langfuse data store is documented as trusted-operator data. It may contain credentials, authorization values, adversarial content, reasoning, and tool payloads. No application-side masking is applied because the selected deployment boundary is local and verbatim evidence is required.

### 8. Support external and bundled local deployments

External mode accepts a configured local Langfuse endpoint and credentials without starting infrastructure.

Bundled mode is an optional Docker Compose profile. It includes the Langfuse web and worker services plus the storage services required by the pinned Langfuse release. Only the Langfuse host-facing endpoint is published, and it binds to `127.0.0.1`. Internal database, cache, object-storage, and analytics services expose no host ports. Named volumes persist until the operator explicitly removes them.

The API container uses the Compose service hostname for ingestion. Host CLI commands use the loopback URL. Separate environment values provide container-internal and host-facing URLs without exposing either to the web bundle.

The Langfuse release and its service image versions are pinned together. Upgrades are deliberate dependency changes, not floating image updates.

### 9. Retain the current model and orchestration stack

LangGraph remains limited to the existing judge pipeline role. The integration does not add `langchain`, `langchain-openai`, LangChain messages, callbacks, agents, or prompt templates.

The existing `ModelGateway`, `StructuredModelGateway`, `MultimodalStructuredModelGateway`, and `ChatModelGateway` contracts remain authoritative. This avoids migrating tool-call serialization, reasoning recovery, strict JSON fallback, approval handling, and model fakes merely to gain observability.

## Risks / Trade-offs

- **[Sensitive evidence is duplicated into Langfuse volumes]** → Bind only to loopback, keep credentials server-side, document the volume as trusted-operator data, and require explicit enablement.
- **[Manual SDK instrumentation can drift from new model methods]** → Make trace coverage part of every gateway contract test and keep generation creation in one adapter helper.
- **[Async context leaks could misattribute concurrent runs]** → Use context-local SDK observations, close every observation with context managers, and test interleaved concurrent runs and cases.
- **[Exporter failures could create warning noise]** → Deduplicate diagnostics by workflow and stage while retaining one actionable failure message.
- **[Queued CLI telemetry may be lost]** → Flush after terminal output with a bounded timeout; never delay indefinitely or change the exit outcome.
- **[Bundled Langfuse adds several local services and resource use]** → Keep it behind an optional profile and support an externally managed local instance.
- **[Verbatim traces consume substantial local storage]** → Make retention manual and document volume removal; do not silently sample or truncate evidence in the first change.
- **[Trace and canonical artifacts can diverge after export failure]** → Treat Langfuse as incomplete by design and never consume it as execution state.

## Migration Plan

1. Add the optional trace contracts and deterministic fake tests while all production composition continues to pass `None`.
2. Add the Langfuse adapter, explicit settings, manual generation instrumentation, and unit tests with a fake SDK client.
3. Instrument experiment, scientist, assessment, decoder, chat, and evaluation boundaries; verify concurrent context isolation and score timing.
4. Wire CLI and API factories and lifecycle flushing with tracing disabled by default.
5. Add the optional pinned Compose profile, loopback bindings, named volumes, environment examples, and trusted-data documentation.
6. Run focused package and composition tests, then the repository check with no live Langfuse or model provider required.

Rollback disables `GAMR_LANGFUSE_ENABLED` and removes the optional Compose profile services. Existing workflows and canonical artifacts remain usable because no schema or execution dependency is introduced.
