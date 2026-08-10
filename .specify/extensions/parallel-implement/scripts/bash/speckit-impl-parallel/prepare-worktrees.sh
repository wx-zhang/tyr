#!/usr/bin/env bash
# Create one git worktree per story id for the speckit-implement-parallel
# orchestrator. Replaces N successive `git worktree add` calls with a single
# script invocation (one approval prompt instead of N).

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage: prepare-worktrees.sh <integration-branch> <integration-head> <storyIds-csv>

Arguments:
  integration-branch   Branch that worktrees will be merged back into.
  integration-head     Commit SHA each new worktree branch is created from.
  storyIds-csv         Comma-separated list of story ids (e.g. "US1,US2,US3,US4").

Behaviour:
  For each storyId in storyIds-csv (case preserved as supplied):
    - Computes worktree path "<repo>/.worktrees/<integration-branch>-<storyId>".
    - Computes branch        "<integration-branch>-<storyId>".
    - If an existing worktree or branch is already there, force-removes them
      (loud log line) so a re-run after a previous failure is idempotent.
    - Creates the worktree pointing at <integration-head> on a new branch.
    - Prints one JSON line to stdout for the caller to parse.

Exit codes:
  0  All worktrees created successfully.
  1  Argument error, not inside a git repo, or git failure.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 3 ]]; then
  usage >&2
  exit 1
fi

INTEGRATION_BRANCH="$1"
INTEGRATION_HEAD="$2"
STORY_IDS_CSV="$3"

REPO_ROOT="$(repo_root)" || die "not inside a git repository"
WORKTREE_ROOT="$REPO_ROOT/.worktrees"
mkdir -p "$WORKTREE_ROOT"

STORY_IDS_TOKENS="$(csv_to_tokens "$STORY_IDS_CSV")"
[[ -n "$STORY_IDS_TOKENS" ]] || die "storyIds-csv expanded to an empty list"

for storyId in $STORY_IDS_TOKENS; do
  branch="${INTEGRATION_BRANCH}-${storyId}"
  worktree="${WORKTREE_ROOT}/${branch}"

  if git worktree list --porcelain | grep -q "^worktree ${worktree}$"; then
    log_status "removing existing worktree at ${worktree}"
    git worktree remove --force "$worktree"
  fi

  if git show-ref --verify --quiet "refs/heads/${branch}"; then
    log_status "deleting stale branch ${branch}"
    git branch -D "$branch"
  fi

  log_status "creating worktree ${worktree} (branch ${branch}) from ${INTEGRATION_HEAD}"
  git worktree add "$worktree" -b "$branch" "$INTEGRATION_HEAD"

  printf '{"storyId":"%s","branch":"%s","worktree":"%s"}\n' \
    "$storyId" "$branch" "$worktree"
done
