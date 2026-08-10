#!/usr/bin/env bash
# Final repository checks and OpenAPI consistency check for the integration branch.

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Runs (from repo root):
  1. uv run poe check
  2. pnpm run web:lint
  3. pnpm run web:test
  4. openapi.json drift    (uv run poe export-openapi must not change tracked file)

Exits non-zero on first failure section.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

REPO_ROOT="$(repo_root)"
cd "$REPO_ROOT"

log_status "final-validate: uv run poe check"
uv run poe check || exit 1

log_status "final-validate: pnpm run web:lint"
pnpm run web:lint || exit 1

log_status "final-validate: pnpm run web:test"
pnpm run web:test || exit 1

if [[ -f schemas/openapi.json ]]; then
  snapshot="$(mktemp)"
  cp schemas/openapi.json "$snapshot"
  log_status "final-validate: openapi drift check"
  uv run poe export-openapi >/dev/null
  if ! cmp -s "$snapshot" schemas/openapi.json; then
    cp "$snapshot" schemas/openapi.json
    rm -f "$snapshot"
    log_status "openapi.json differs from regenerated export"
    exit 1
  fi
  rm -f "$snapshot"
fi

log_status "final-validate: all sections passed"
