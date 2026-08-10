# Changelog

All notable changes to the Parallel Implement extension will be documented in this file.

## [1.1.0] - 2026-05-18

### Changed

- Refactored to Spec Kit extension conventions: all orchestrator and delegate logic now lives in `commands/` and registers via `provides.commands`
- Removed non-standard `claude-skills/` bundle and manual post-install copy step
- Orchestrator delegates via registered commands (`/speckit.parallel-implement.phase`, `.story`, `.merge`, `.validate`)

### Added

- Four internal delegate commands registered automatically on install

## [1.0.0] - 2026-05-18

### Added

- Initial release as a Spec Kit extension
- Orchestrator command `speckit.parallel-implement.run`
- Bash helpers: `prepare-worktrees`, `cleanup-worktrees`, `merge-story`, `final-validate`
- Optional `after_tasks` hook
