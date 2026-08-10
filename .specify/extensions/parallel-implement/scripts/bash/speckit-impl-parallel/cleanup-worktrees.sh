#!/usr/bin/env bash
# Remove git worktrees and story branches produced by prepare-worktrees.sh.

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage:
  cleanup-worktrees.sh <integration-branch> <storyIds-csv> [--keep keepIds-csv]

For each story id in storyIds-csv that does not appear in --keep:
  - git worktree remove --force ".worktrees/<integration-branch>-<storyId>"
  - git branch -D "<integration-branch>-<storyId>"

Ends with git worktree prune.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

KEEP_CSV=""
positional=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep)
      shift
      KEEP_CSV="${1:-}"
      shift
      ;;
    *)
      positional+=("$1")
      shift
      ;;
  esac
done

if [[ ${#positional[@]} -lt 2 ]]; then
  usage >&2
  exit 1
fi

INTEGRATION_BRANCH="${positional[0]}"
STORY_IDS_CSV="${positional[1]}"

REPO_ROOT="$(repo_root)"
cd "$REPO_ROOT"
WORKTREE_ROOT="$REPO_ROOT/.worktrees"

should_skip() {
  local id="$1"
  [[ -z "$KEEP_CSV" ]] && return 1
  for keep in $(csv_to_tokens "$KEEP_CSV"); do
    if [[ "$id" == "$keep" ]]; then
      return 0
    fi
  done
  return 1
}

for storyId in $(csv_to_tokens "$STORY_IDS_CSV"); do
  if should_skip "$storyId"; then
    log_status "keeping ${storyId} (--keep)"
    continue
  fi

  branch="${INTEGRATION_BRANCH}-${storyId}"
  wt="${WORKTREE_ROOT}/${branch}"

  if git worktree list --porcelain 2>/dev/null | grep -q "^worktree ${wt}$"; then
    log_status "git worktree remove --force '${wt}'"
    git worktree remove --force "$wt" || die "failed to remove worktree ${wt}"
  else
    log_status "(no worktree registered at ${wt})"
  fi

  if git show-ref --verify --quiet "refs/heads/${branch}"; then
    log_status "git branch -D '${branch}'"
    git branch -D "$branch" || true
  fi
done

git worktree prune || true
