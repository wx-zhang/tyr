#!/usr/bin/env bash
# Shared helpers for the speckit-impl-parallel script family.
# Sourced (not executed) by sibling scripts.

log_status() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die()        { log_status "ERROR: $*" >&2; exit 1; }
repo_root()  { git rev-parse --show-toplevel; }

# Split a comma-separated list into space-separated whitespace-trimmed tokens.
# Usage: csv_to_tokens "US1, US2,US3"  -> "US1 US2 US3"
csv_to_tokens() {
  local csv="${1:-}"
  printf '%s' "$csv" | tr ',' ' ' | xargs
}
