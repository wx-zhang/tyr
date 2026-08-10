<!--
Sync Impact Report
- Version change: 1.0.0 -> 2.0.0
- Added principles: Human Authority and Safe Defaults; Inward Dependencies and One Engine;
  Canonical, Validated Evidence; Risk-Weighted Test-First Development; Simplicity and
  Maintainability; Token-Governed, Accessible UI; Reproducible Tooling and Current Docs
- Added sections: Operational Guarantees; Development and Review
- Removed sections: none; template placeholders were replaced
- Follow-up TODOs: none
-->
# GAMR Constitution

## Core Principles

### Article I — Human Authority and Safe Defaults

1. Read-only operation MUST be the default for experiments and chat.
2. `approval_required` MUST be the only action-enabled mode. Starting that mode MUST require
   explicit human confirmation, and every Tyr action MUST require a recorded human decision.
3. Automatic approval is forbidden. Secrets MUST be redacted before any value is persisted,
   logged, returned by an API, rendered, copied, or exposed to assistive technology.

These rules preserve human control and prevent evidence collection from becoming an unsafe action.

### Article II — Inward Dependencies and One Engine

1. Apps MAY depend on shared packages; packages MUST NOT depend on apps.
2. `gamr-core` MUST remain free of framework, terminal, database, filesystem, and vendor concerns.
3. `gamr-engine` MUST own workflow decisions behind ports. Concrete I/O MUST live in adapters or
   composition roots.
4. The CLI is the primary entry point. CLI and API execution MUST use the same engine path. The
   optional web app MUST communicate only with the API, and credentials MUST remain server-side.

These boundaries keep business rules reusable, testable, and consistent across entry points.

### Article III — Canonical, Validated Evidence

1. Versioned datasets and completed run results MUST be schema-validated JSON files.
2. JSON run bundles MUST contain operational state and evidence. Markdown and in-memory indexes
   MUST remain derived views rather than sources of truth.
3. A run MUST snapshot its resolved non-secret inputs. Viewing or evaluating data MUST NOT mutate
   canonical datasets or completed run bundles.
4. Workflow state MUST use validated models and explicit transitions. Model text and outer Tyr
   terminal states MUST NOT be treated as authoritative control signals.

These rules make findings reproducible, portable, and independently auditable.

### Article IV — Risk-Weighted Test-First Development

1. Critical and core behavior MUST begin with a meaningful failing test, followed by the smallest
   passing implementation and refactoring.
2. Critical paths MUST test the success case and every rejection path. Core paths MUST test the
   realistic boundary and failure cases. Surface tests MUST assert user-visible behavior.
3. Every bug fix MUST include a regression test at the lowest layer that reproduces the defect.
4. Default tests MUST use deterministic fakes and MUST NOT require live Tyr, a model provider, or
   action approval. Live tests MUST be explicit and marker-gated.

Test depth is proportional to the harm a defect can cause, not to a coverage target.

### Article V — Simplicity and Maintainability

1. Implementations MUST solve only the stated problem with the fewest clear moving parts.
2. New abstractions, dependencies, configuration, and error handling MUST have a current use case.
3. Names and structure MUST make code self-explanatory. Comments are reserved for unavoidable,
   non-obvious constraints or workarounds.
4. Source files SHOULD stay below 300 lines when splitting improves comprehension.

Simplicity reduces audit cost and the number of places where security behavior can diverge.

### Article VI — Token-Governed, Accessible UI

1. `apps/web/UI-DESGIN-TOKEN.md` is the canonical UI contract. Every new UI and every material UI
   change MUST follow it.
2. Visual values MUST use its shared CSS custom properties. Components MUST NOT hard-code colors,
   create a second token layer, or add a UI or CSS framework without an explicit architecture
   decision.
3. A changed design token or design-system rule MUST update the token document in the same change.
4. UI behavior MUST meet WCAG 2.2 AA, support keyboard and reduced-motion use, preserve visible
   focus and semantic labels, and express run, action, approval, and severity state in text rather
   than color alone.
5. The web UI MUST NOT expose action-enabled starts or approval decisions. Redacted data MUST
   remain redacted in every visible and accessible representation.

The interface is an evidence console; consistency and accessibility are safety properties.

### Article VII — Reproducible Tooling and Current Docs

1. Python MUST use version 3.14, one root uv workspace, and `uv.lock`. Only `apps/web` MAY use
   Node.js 24 LTS and pnpm, with one root `pnpm-lock.yaml`.
2. Generated schemas and API contracts MUST be regenerated from their owning sources and MUST NOT
   be hand-edited.
3. Documentation and the nearest scoped `AGENTS.md` MUST change with the behavior, commands,
   dependencies, module seams, test locations, or design rules they govern.
4. A new module is incomplete without its scoped `AGENTS.md`, adjacent `CLAUDE.md` symlink, and
   root instruction-table entry.

Pinned tooling and synchronized guidance make local, CI, and agent behavior repeatable.

## Operational Guarantees

1. Every Tyr request and approval resolution MUST use an idempotency key. An interrupted external
   step MAY be retried only when its checkpoint and idempotency state make the retry safe.
2. Tyr polling and settling MUST remain adapter concerns. A terminal outer state MUST NOT end a run
   while delegated work, bridge work, or a late user-visible response may still arrive.
3. Execution outcome and security verdict MUST remain separate fields.
4. Read-only service work MUST run through a bounded in-process queue owned by one API instance.
   Request handlers MUST return after durable JSON queue creation. Restart MUST interrupt unfinished
   service runs and MUST NOT replay them automatically.

## Development and Review

1. Before editing a subtree, contributors MUST read the root and nearest scoped `AGENTS.md` files.
2. Work MUST follow: failing test, observed failure, smallest passing change, refactor, then the
   narrowest relevant checks.
3. Before handoff, contributors MUST run `uv run poe check`. If an unavailable service or tool
   prevents it, the handoff MUST name the skipped check and evidence from narrower checks.
4. Reviews MUST verify safety invariants, dependency direction, schema effects, design-token
   compliance for UI changes, meaningful tests, and synchronized documentation.
5. Deviations from a SHOULD rule MUST be stated in the change with concrete rationale. Deviations
   from a MUST rule require a constitutional amendment before merge.

## Governance

1. This constitution is the highest project governance document. More specific instructions MAY
   tighten it but MUST NOT weaken or contradict it.
2. An amendment MUST state its rationale, compatibility impact, migration needs, and affected
   principles. It MUST be reviewed before dependent implementation is merged.
3. Versions follow semantic versioning: MAJOR for incompatible governance changes or removed or
   redefined principles; MINOR for new principles or materially expanded obligations; PATCH for
   non-semantic clarification.
4. Every pull request and agent handoff MUST include a constitution compliance review. Known
   non-compliance MUST block completion unless an approved amendment resolves it.
5. Ratification and amendment dates MUST use ISO `YYYY-MM-DD` format. Compliance is reviewed again
   whenever architecture, safety policy, canonical data, test policy, or the UI contract changes.

**Version**: 2.0.0 | **Ratified**: 2026-08-08 | **Last Amended**: 2026-08-09
