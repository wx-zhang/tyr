## Why

Uploaded evidence can be transformed with encodings, ciphers, compression, or a scientist-designed procedure that the current content preparation cannot interpret reliably. The existing content judge needs a trajectory-aware stage that can derive and safely execute Python before comparing uploaded content with the synthetic reference.

## What Changes

- Upgrade the existing `evidence-and-content` pipeline with trajectory analysis and bounded generated-Python execution for every applicable reference-aware file case.
- Use the configured judge model to analyze the rendered task, test case, evaluation criteria, and agent–Tyr transcript, then either keep directly prepared content or execute case-specific Python.
- Reuse one healthy sandbox for at most three attempts in a case, while isolating each attempt's accepted output and replacing the sandbox only after a terminal failure destroys it.
- Mount only digest-verified uploaded bytes into the Docker sandbox and collect validated files from a confined output directory.
- Keep Python standard-library-only and keep synthetic reference content, credentials, Tyr access, network access, and host execution outside the decoder sandbox.
- Feed validated decoded outputs into the existing content-overlap assessment, then retain the existing final evidence assessment and conservative verdict rules.
- Return only coarse safe execution feedback to the decoder model and fail closed with an inconclusive content result when analysis, execution, or validation fails.
- Record a concise decoder decision rationale, the executed Python after standard secret redaction, its digest, and bounded sanitized execution results without persisting hidden model reasoning, decoded file content, raw tool transcripts, sandbox identifiers, or unsafe diagnostics.
- Emit decoder analysis, routing, execution-attempt, and terminal activities into canonical run history, and present the same safe provenance through artifacts, reports, API responses, and the web run view.
- Use one canonical relative attachment contract mapped to stable `/input/<opaque-id>/<filename>` runtime paths, preserve safe stage-specific infrastructure diagnostics, and cover the composed decoder path with Docker integration tests.
- Limit active decoder sandboxes across concurrent runs through one configurable process-wide capacity gate that defaults to 2.
- Exercise the upgraded behavior through the existing exfiltration task rather than adding a second example task or a new pipeline identifier.

## Capabilities

### New Capabilities

- `trajectory-content-decoding`: Trajectory analysis, bounded generated-Python execution, decoded-output validation, lineage, retries, global capacity, and safe failure behavior before content comparison.

### Modified Capabilities

- `judge-pipelines`: Extend the existing `evidence-and-content` graph and shared CLI/API/base/scientist execution path with trajectory decoding while preserving its selection and provenance identifier.
- `python-execution-sandbox`: Add confined collection of generated output files and require the judge integration to use the Docker security boundary without automatic unsafe-host fallback.

## Impact

- Core content-result models and generated schemas gain optional bounded decoding decisions and execution-attempt provenance; the allowed judge identifier and compatibility default do not change.
- Engine judge contracts, the existing graph topology, model interaction, content evidence contracts, and execution composition gain the decoder-agent path and process-wide capacity coordination.
- The collector content adapter must make verified raw uploads available as ephemeral sandbox inputs without persisting another copy.
- The Docker sandbox gains bounded output collection with regular-file, path, size, count, and symlink validation.
- CLI and API composition inject the same sandbox-backed runtime and capacity gate. Run logs, reports, and the web run view present the safe decoder rationale, redacted executed code, bounded sanitized execution results, status, and lineage metadata without exposing decoded file content or secrets.
- The existing exfiltration task remains selected on `evidence-and-content` and becomes the canonical adoption case for the upgraded behavior.
- Generated schemas, judge graph documentation, task and development documentation, environment examples, module maps, and critical security tests require updates.
