## 1. Engine Sandbox Contract

- [x] 1.1 Write failing engine tests for source-size validation, opaque process-local IDs, structured execution results, typed unavailable/unknown/closed/busy failures, and the asynchronous start-execute-close protocol.
- [x] 1.2 Add the minimal transport-neutral sandbox values, fixed contract limits, failures, and protocol under `gamr_engine.ports`, export the supported surface, and make the focused engine tests pass.

## 2. Attachment Snapshot Boundary

- [x] 2.1 Write failing adapter tests for repeated file and directory roots, preserved logical paths, duplicate and ancestor conflicts, absolute/traversal/empty/invalid names, symlinks and special files, entry and byte limits, source read failures, and atomic rejection.
- [x] 2.2 Implement the non-following filesystem snapshot loader and backend-boundary entry validation without exposing host paths through the engine contract, then make the focused attachment tests pass.

## 3. Configuration and Non-Docker Backends

- [x] 3.1 Write failing configuration and disabled-backend tests for the Docker default, exact accepted values, unknown-value rejection, deferred unavailable failure, idempotent close, and preservation of unrelated settings behavior.
- [x] 3.2 Add `GAMR_SANDBOX_BACKEND` to shared settings, implement the adapter factory and disabled adapter, and make the focused tests pass without probing Docker.
- [x] 3.3 Write failing host-backend tests for fresh Python processes, persistent workspace files, copied input, minimal secret-free environment, non-zero results, source/output/time limits, same-ID overlap rejection, different-ID concurrency, close-during-execution, descendant cleanup, and temporary-tree removal.
- [x] 3.4 Implement the explicitly warned `host-unsafe` adapter with isolated temporary input/workspace roots, fresh process groups, concurrent bounded stream capture, supported resource controls, terminal invalidation, and idempotent cleanup, then make its controlled-snippet tests pass.

## 4. Docker Containment Backend

- [x] 4.1 Write failing unit tests for fixed Docker CLI argument vectors, public/private ID separation, input archive generation, volume population, labels, read-only mounts, unprivileged execution, network/capability/environment/resource flags, same-ID locking, timeout/output invalidation, and cleanup after every partial failure.
- [x] 4.2 Add the pinned Python 3.14 standard-library sandbox image and fixed input-population/bootstrap behavior under the adapters package, keeping untrusted source and attachment values out of shell syntax.
- [x] 4.3 Implement the asynchronous Docker CLI adapter with per-sandbox input volume, read-only execution container, bounded in-memory workspace, stdin source delivery, concurrent output draining, terminal container destruction, and volume cleanup, then make its fake-process unit tests pass.
- [x] 4.4 Add a deselected-by-default `sandbox_docker` marker and opt-in runtime tests for repeated execution, immutable input, workspace persistence, environment and credential exclusion, network denial, CPU/memory/process/workspace controls, metacharacter handling, timeout/output cleanup, and labeled resource removal.

## 5. Developer Commands

- [x] 5.1 Write failing script tests for repeated `--attach` files/directories, exactly one of inline code or UTF-8 source file, JSON ID/result output, Python non-zero propagation, infrastructure failures, disabled rejection, host-unsafe warning, and close in every terminal path.
- [x] 5.2 Implement the thin shared-contract sandbox runner and add `uv run poe sandbox-run` without adding a public `gamr` CLI command, then make its tests pass.
- [x] 5.3 Add `uv run poe sandbox-build` with the fixed image tag and confined build context, and verify command failures cannot report false success.

## 6. Documentation and Verification

- [x] 6.1 Update root and scoped `AGENTS.md` file maps and command tables for every new adapter and script seam, and update `README.md`, `.env.example`, and development documentation with backend semantics, fixed limits, commands, Docker trust assumptions, host-unsafe warnings, and orphan diagnosis/removal.
- [x] 6.2 Run focused engine, adapter, and developer-runner tests plus lint and type checks; confirm every new source file remains below 300 lines and default tests neither contact Docker nor execute untrusted snippets.
- [x] 6.3 Build the sandbox image and run the explicitly selected Docker integration suite when Docker is available, then run `uv run poe check` and record any unavailable opt-in verification honestly.
