## 1. Trace contracts

- [x] 1.1 Add failing engine tests for nested observations, terminal updates, categorical scores, bounded diagnostics, and disabled `None` behavior through a deterministic fake trace port.
- [x] 1.2 Add the vendor-neutral trace protocols and observation context contracts under `gamr_engine.ports`, keeping provider types out of the engine.
- [x] 1.3 Add failing concurrency coverage proving interleaved async workflows cannot inherit another run's active observation.

## 2. Langfuse adapter and configuration

- [x] 2.1 Add failing adapter settings tests for explicit enablement, credentials-without-enablement, valid local configuration, and invalid enabled configuration.
- [x] 2.2 Add the pinned Langfuse SDK dependency to `gamr-adapters`, update `uv.lock`, and implement settings for enablement, public key, secret key, host URL, container URL, and environment.
- [x] 2.3 Add failing adapter tests for observation nesting, verbatim input/output updates, categorical scores, diagnostic deduplication, and harmless SDK exceptions using a fake Langfuse client.
- [x] 2.4 Implement the process-shared Langfuse trace adapter and factory, including context-local observations, bounded best-effort flush, and no client initialization while disabled.


## 3. Model generation evidence

- [x] 3.1 Add failing `OpenAICompatibleModel` tests covering traced plain, structured, structured-fallback, multimodal, chat, empty, and provider-error requests without changing existing response contracts.
- [x] 3.2 Instrument every OpenAI-compatible gateway method with explicit generation observations while retaining `openai.AsyncOpenAI`, request payloads, JSON fallback, reasoning recovery, tool calls, and provider exception behavior.
- [x] 3.3 Verify model generations retain verbatim request content, normalized and raw available response evidence, model, usage, finish reason, refusal or reasoning fields, duration, and failure diagnostics.


## 4. Experiment hierarchy and scores

- [x] 4.1 Add failing runner and execution-service tests for one run trace with discovery, case, assessment, scientist iteration, scientist retry-attempt, and decoder ancestry.
- [x] 4.2 Add failing tests proving independent base runs use distinct sessions and scientist resumes reuse the source-run lineage session while retaining distinct traces.
- [x] 4.3 Add failing tests proving security verdict, objective status, assessment status, execution outcome, and final run outcome scores are emitted only from existing terminal results.
- [x] 4.4 Thread the optional trace port through `ExperimentExecutionService`, `ExperimentRunner`, assessment, judge runtime, and decoder execution, and implement the specified observation boundaries and score timing.
- [x] 4.5 Add an interleaved multi-run regression test proving run, case, iteration, attempt, and model generations remain isolated under API-level concurrency.
- [x] 4.6 Add failure-isolation tests proving observation, score, export, and diagnostic failures do not add `RunResult.errors`, alter artifacts, trigger retries, or change outcomes.


## 5. Chat and judge evaluation coverage

- [x] 5.1 Add failing chat tests for one trace per user turn, Tyr conversation session grouping, nested model rounds, verbatim tool-call messages, and harmless tracing failures.
- [x] 5.2 Instrument `ChatSession` and its CLI composition without adding Tyr-operation spans or changing approval, idempotency, settling, or tool filtering behavior.
- [x] 5.3 Add failing judge evaluation tests for stable invocation sessions, case observations, model generations, existing evaluation outcomes, and tracing-failure isolation.
- [x] 5.4 Instrument judge evaluation entrypoints and traced model composition while preserving current summary artifacts and evaluation results.


## 6. Composition and lifecycle

- [x] 6.1 Add failing CLI and API composition tests proving explicit enablement creates one shared trace adapter and disabled or invalid configuration continues with no exporter.
- [x] 6.2 Wire the shared trace adapter into experiment, resume, chat, and evaluation model gateways in every CLI and API composition root.
- [x] 6.3 Add failing lifecycle tests proving CLI commands attempt bounded flush before exit and API lifespan flushes after the run manager shuts down.
- [x] 6.4 Implement best-effort CLI and API flushing plus bounded local diagnostics without changing command exit codes, API run states, or terminal results.


## 7. Local deployment and documentation

- [x] 7.1 Add an optional Docker Compose profile with pinned compatible Langfuse web, worker, and required storage services; publish only the Langfuse endpoint on `127.0.0.1` and persist data in named volumes.
- [x] 7.2 Configure separate host-loopback and API-container ingestion URLs and verify the standard Compose stack starts no Langfuse services when the profile is absent.
- [x] 7.3 Update `.env.example`, README configuration and commands, dependency documentation, and affected module `AGENTS.md` files with explicit enablement, external-local mode, bundled mode, manual volume retention, and trusted-operator evidence warnings.
- [x] 7.4 Add a deterministic Compose configuration check covering profile isolation, loopback bindings, internal-only storage services, and persistent volumes without contacting a live Langfuse instance.


## 8. Verification

- [x] 8.1 Run the focused engine, adapter, CLI, and API tests covering observability, model gateways, runner concurrency, chat, evaluation, composition, and lifecycle behavior.
- [x] 8.2 Run OpenSpec strict validation and schema generation checks, confirming task and run-result schemas remain unchanged.
- [x] 8.3 Run `uv run poe check` with live Tyr, OpenRouter, Langfuse, action-enabled, and sandbox Docker integration tests disabled.

