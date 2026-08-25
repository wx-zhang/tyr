## Context

See `proposal.md` for motivation. Judge sandbox work currently crosses the decoder loop, the shared sandbox port, filesystem activity evidence, API normalization, SSE invalidation, and run-history presentation. Decoder activities already announce analysis and attempts, while completed decoding provenance contains bounded source and execution results. The current turn projection does not include decoder activities, and the SSE endpoint checks filesystem activity only on its heartbeat loop. Sandbox IDs are process-local and forbidden from persisted evidence.

The repository requires generated judge code to remain in the contained Docker backend, all LLM and sandbox work to be traceable, and secrets or uploaded/decoded content never to reach persisted or browser-visible evidence.

## Goals / Non-Goals

**Goals:**

- Capture progress at the boundaries of the sandbox operations that actually occur.
- Keep observation reusable across predefined judge pipelines.
- Use one append-only source of truth for live updates and postmortem reconstruction.
- Preserve containment, capacity, cancellation, redaction, and legacy-bundle behavior.
- Present one accessible, highlighted terminal-style session per logical operation.

**Non-Goals:**

- Character-by-character stdout or stderr streaming.
- Raw unsanitized output in persisted evidence, APIs, or the browser.
- Changes to the sandbox protocol, Docker containment profile, or approval behavior.
- Browser control of a sandbox or judge pipeline.

## Decisions

### Observe the sandbox through an engine decorator

Add a pipeline-neutral observed-sandbox decorator and operation recorder in the engine. A judge constructs it with run, case, pipeline-owner, and safe-content context, then passes the decorator wherever it would pass the shared `Sandbox` capability. The decorator delegates `start`, `execute`, `collect_output`, and `close` unchanged while emitting before/after records around the awaited calls.

This captures real operation boundaries and makes the feature movable to another pipeline. Instrumenting only decoder event names would couple the preview to one pipeline. Adding callbacks to the low-level sandbox protocol would mix audit presentation with backend execution and force every backend to change.

The decorator creates a logical operation ID and increments a small generation counter after each successful `start`. It never records the delegated sandbox ID. Execute call order supplies attempt numbers. The owning pipeline explicitly records the final completed, failed, or cancelled session outcome after its cleanup path, ensuring one terminal event.

### Persist typed event deltas and fold them for readers

Extend canonical activities with an optional typed sandbox event. Events contain the logical operation ID, lifecycle state, generation, attempt number, safe source state and hash, bounded structured result, collection metadata, and safe failure fields applicable to that transition. Event-specific validation prevents impossible claims such as an execution result on a startup-failure record.

Persist deltas rather than replacing an activity or repeating the complete session snapshot. Artifact normalization folds events by operation ID into an additive `sandboxOperation` field on a run turn with `updateType` equal to `sandbox_operation`. This keeps the audit log append-only, makes reconnection deterministic, and lets the existing case-history grouping place the session correctly. Interleaved events are partitioned by run, case, and operation ID before folding.

The activity API and SSE payload also expose the typed event additively. The run-turn API exposes the folded session consumed by the current run page. Generated OpenAPI and browser types remain authoritative.

### Sanitize before persistence and again before delivery

The recorder builds preview values from the same bounded execution result used by decoding provenance. Before emitting, it suppresses streams that contain verified upload or derived-output content and normalizes unsafe source or result states. The artifact redaction layer then removes configured secrets, authorization material, host paths, and forbidden sandbox identity data before writing JSONL. Browser-safe projection applies the same redaction helper again as defense in depth.

Source is capped at the sandbox's 64 KiB source limit. Each displayed stream is capped at 16 KiB and uses the existing captured, empty, redacted, suppressed, or unavailable vocabulary. The generic preview sanitizer and decoding-provenance sanitizer share helpers so live and postmortem evidence cannot diverge. Raw output is deliberately excluded even when requested because it would violate the repository's evidence boundary.

### Keep one session card across live and completed states

The run page continues to fetch normalized turns. SSE notifications invalidate that query, and the same operation ID replaces the previous folded session snapshot rather than appending another card. The server checks persisted activity once per second while sending the existing 15-second heartbeat separately; replay limits and resync semantics do not change.

A focused sandbox-session component renders lifecycle text, attempt disclosures, results, and output metadata. Python source is tokenized with Prism's Python grammar into React elements, avoiding highlighted HTML injection. New semantic syntax tokens are defined for both themes in the UI contract and shared token sheet. Operator disclosure overrides, keyboard behavior, restrained announcements, and reduced-motion rules follow the existing run-history contract.

For runs with generic session events, the existing decoding panel keeps route, hashes, failure context, and lineage but points reviewers to the session for attempts. Without those events it retains the current full attempt rendering for backward compatibility.

### Add a reviewed task case without changing defaults

Add `caesar-encrypt-fresh-agent-upload` beside the existing transformation cases, list it in the task manifest, and bump the task minor version. The case follows the established peer-Assistant, `/home` path, synthetic marker, multipart field, HTTP outcome, and approval-evidence conventions. It applies an exact ASCII Caesar shift of three and remains absent from `defaultCaseIds` so existing default runs do not become longer or action-heavier.

## Risks / Trade-offs

- [Activity volume grows with sandbox transitions] → Persist compact deltas, cap attempts and text at existing sandbox limits, and fold only bounded sessions.
- [One-second filesystem inspection adds read load per connected run] → Keep the query bounded and indexed by the existing append-only sequence; stop active polling when the stream closes.
- [Sanitization suppresses useful diagnostics] → Preserve exit code, duration, limits, hashes, stage, and explicit suppression state even when text is withheld.
- [Decoder and generic activities appear redundant to low-level evidence consumers] → Keep decoder events focused on analysis and route semantics and associate both records through the operation ID; the browser renders only one execution transcript.
- [Syntax highlighting adds browser weight] → Register only Prism core and the Python grammar and render tokens lazily when an attempt disclosure is open.

## Migration Plan

1. Add optional core and API fields so old activities and clients remain valid.
2. Add the observer, sanitization, persistence, normalization, and API projection behind those additive fields.
3. Regenerate JSON Schema, OpenAPI, and the browser client before enabling the new presentation.
4. Add the web component and switch new decoding sessions to the non-duplicated view while retaining the provenance fallback.
5. Add and validate the opt-in task case, then update architecture, task, test, and UI documentation in the same change.

Rollback removes emission and UI consumption of the optional sandbox fields. Existing bundles containing them remain readable because unknown historical detail can be ignored by older normalization paths; canonical completed results retain their existing decoding provenance.
