# Application scope

## Purpose

Own delivery applications and composition roots under `apps/`.

## Standards

Apps may depend on shared packages, but packages never depend on apps. Keep HTTP, terminal, and browser concerns at the edges; workflow belongs in `gamr-engine`.

## Safety/testing

Use injected fake ports only in tests. Production commands require configured providers. Read-only is the default, and real actions require explicit opt-in and approval.
