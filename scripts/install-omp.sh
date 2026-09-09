#!/usr/bin/env bash
set +x
set -euo pipefail
umask 077

fail() { printf '\nError: %s\n' "$*" >&2; exit 1; }
step() {
    if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then printf '\n\033[1m%s\033[0m\n' "$*"
    else printf '\n%s\n' "$*"; fi
}
confirm() {
    local answer
    printf '%s [y/N] ' "$1"
    IFS= read -r answer || fail 'Input ended. Nothing else will be changed.'
    case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}
secret() {
    printf '%s (hidden; Enter to skip): ' "$1"
    IFS= read -rs REPLY || fail 'Input ended while reading a key.'
    printf '\n'
    case "$REPLY" in *[!a-zA-Z0-9_./:+\=\-]*) fail 'Key contains unsupported characters. Paste only the API key.' ;; esac
}
regular_or_missing() {
    [[ ! -L "$1" ]] || fail "Refusing a symlink: $1"
    [[ ! -e "$1" || -f "$1" ]] || fail "Expected a regular file: $1"
}
backup() {
    local copy
    if [[ -f "$1" ]]; then
        mkdir -p "$HOME/.omp/agent/backups"
        copy=$(mktemp "$HOME/.omp/agent/backups/${1##*/}.backup.XXXXXX")
        cat "$1" > "$copy"
        printf 'Private backup saved: %s\n' "$copy"
    fi
}

DRY=false
case "${1:-}" in
    --dry) DRY=true ;;
    -h|--help)
        printf 'Usage: bash scripts/install-omp.sh [--dry]\n\n--dry  Preview only. No writes, downloads, keys, or sign-in.\n'
        exit 0 ;;
    '') ;;
    *) fail 'Unknown option. Use --help or --dry.' ;;
esac
[[ $# -le 1 ]] || fail 'Pass only --dry or --help.'
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TARGET="$HOME/.omp/agent/models.yml"
ENV_FILE="$ROOT/.env"
TEMPLATE="$ROOT/docs/oh-my-pi/models.yml"
[[ -f "$TEMPLATE" ]] || fail "Missing provider file: $TEMPLATE"

if $DRY; then
    step 'DRY RUN: preview only'
    printf 'Repository: %s\nSettings: %s\n' "$ROOT" "$TARGET"
    printf '%s\n' \
        '1. Check existing settings. Ask before replacement; save a private backup.' \
        '2. Ask for OpenRouter key: repository .env, personal models.yml, or skip.' \
        '3. Ask for Abliteration.ai key, or skip. Ask team if you need keys.' \
        '4. Install omp from https://omp.sh/install only after confirmation.' \
        '5. Save selected providers with private file permissions.' \
        '6. Offer to open omp for /login openai-codex and /model.' \
        'No files changed. No programs installed or launched. No keys requested.'
    exit 0
fi

case "$(uname -s)" in Darwin|Linux) ;; *) fail 'Use the manual Windows steps in docs/oh-my-pi/how-to.md.' ;; esac
[[ -z "${PI_CODING_AGENT_DIR:-}${OMP_CODING_AGENT_DIR:-}" ]] || fail 'Custom OMP settings directory detected. Use the manual setup guide.'
for directory in "$HOME/.omp" "$HOME/.omp/agent" "$HOME/.omp/agent/backups"; do
    [[ ! -L "$directory" ]] || fail "Refusing a symlink: $directory"
    [[ ! -e "$directory" || -d "$directory" ]] || fail "Expected a directory: $directory"
done
regular_or_missing "$TARGET"
regular_or_missing "$ENV_FILE"
for alternate in "$HOME/.omp/agent/models.yaml" "$HOME/.omp/agent/models.json"; do
    [[ ! -e "$alternate" && ! -L "$alternate" ]] || fail "Existing alternate configuration: $alternate. Ask a teammate to merge it first."
done
step 'Oh My Pi setup'
printf 'Ask team for API keys unless you already have your own. Keys are never printed.\n'
if [[ -f "$TARGET" ]]; then
    printf 'Existing settings: %s\nReplacement removes providers not selected here. A private backup will be kept.\n' "$TARGET"
    if ! confirm 'Back up and replace this file?'; then
        printf 'Kept your settings. No changes made. Use the manual guide to merge providers.\n'
        exit 0
    fi
fi

step '1. Choose your providers'
printf 'OpenRouter key location:\n  1) Repository .env (recommended)\n  2) Personal models.yml (works from any folder)\n  3) Skip OpenRouter\nChoice [1]: '
IFS= read -r LOCATION || fail 'Input ended.'
LOCATION=${LOCATION:-1}
case "$LOCATION" in 1|2|3) ;; *) fail 'Choose 1, 2, or 3.' ;; esac
ROUTER=''
ABLITERATION=''
if [[ "$LOCATION" != 3 ]]; then
    secret 'OpenRouter API key'
    ROUTER=$REPLY
    if [[ -n "$ROUTER" && "$LOCATION" == 1 ]]; then
        command -v git >/dev/null || fail 'Git is needed to check that .env is not committed.'
        if git -C "$ROOT" ls-files --error-unmatch .env >/dev/null 2>&1; then
            fail '.env is tracked by Git. Use the personal models.yml option instead.'
        fi
        git -C "$ROOT" check-ignore -q .env || fail '.env must be ignored by Git. Use the personal models.yml option instead.'
        [[ -z "${OPENROUTER_API_KEY:-}" ]] || printf 'Warning: your exported OPENROUTER_API_KEY takes priority over .env.\n'
    fi
fi
secret 'Abliteration.ai API key'
ABLITERATION=$REPLY
unset REPLY

step '2. Install Oh My Pi'
export PATH="$PATH:$HOME/.local/bin"
INSTALLER=''
STAGED=''
cleanup() {
    [[ -z "$INSTALLER" ]] || rm -f -- "$INSTALLER"
    [[ -z "$STAGED" ]] || rm -f -- "$STAGED"
    return 0
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if ! command -v omp >/dev/null; then
    confirm 'Download and run the official installer from https://omp.sh/install?' || fail 'Installation declined. Settings have not been changed.'
    command -v curl >/dev/null || fail 'Install curl, then run this script again.'
    INSTALLER=$(mktemp)
    curl -fsSL --proto '=https' --proto-redir '=https' https://omp.sh/install -o "$INSTALLER"
    PI_INSTALL_DIR="$HOME/.local/bin" sh "$INSTALLER" --binary
fi
omp --version

step '3. Save your settings'
mkdir -p "$HOME/.omp/agent"
backup "$TARGET"
STAGED=$(mktemp "$TARGET.tmp.XXXXXX")
if [[ -z "$ROUTER$ABLITERATION" ]]; then
    printf 'providers: {}\n' > "$STAGED"
else
    section=''
    while IFS= read -r line || [[ -n "$line" ]]; do
        case "$line" in
            'providers:') printf '%s\n' "$line"; continue ;;
            '  openrouter:') section=router ;;
            '  abliteration:') section=abliteration ;;
            '  ollama:') section=ollama ;;
        esac
        case "$section" in
            router)
                [[ -n "$ROUTER" ]] || continue
                if [[ "$line" == '    apiKey: '* && "$LOCATION" == 2 ]]; then
                    line="    apiKey: \"$ROUTER\""
                fi ;;
            abliteration)
                [[ -n "$ABLITERATION" ]] || continue
                if [[ "$line" == '    apiKey: '* ]]; then line="    apiKey: \"$ABLITERATION\""; fi ;;
            ollama) continue ;;
        esac
        printf '%s\n' "$line"
    done < "$TEMPLATE" > "$STAGED"
fi
mv -- "$STAGED" "$TARGET"
STAGED=''
printf 'Saved %s\n' "$TARGET"
if [[ -n "$ROUTER" && "$LOCATION" == 1 ]]; then
    backup "$ENV_FILE"
    STAGED=$(mktemp "$ENV_FILE.tmp.XXXXXX")
    if [[ -f "$ENV_FILE" ]]; then
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ ! "$line" =~ ^[[:space:]]*OPENROUTER_API_KEY[[:space:]]*= ]] || continue
            printf '%s\n' "$line"
        done < "$ENV_FILE" > "$STAGED"
    fi
    printf 'OPENROUTER_API_KEY=%s\n' "$ROUTER" >> "$STAGED"
    mv -- "$STAGED" "$ENV_FILE"
    STAGED=''
    printf 'Saved OpenRouter key in %s\n' "$ENV_FILE"
fi
unset ROUTER ABLITERATION line

step '4. Sign in and choose a model'
printf 'Setup files are saved. Keys are plaintext; keep them and their backups private.\n'
printf 'Open a terminal in %s and run omp.\n' "$ROOT"
printf 'If omp is not found after reopening your terminal, run ~/.local/bin/omp.\n'
printf 'Inside omp:\n  /login openai-codex  (use your ChatGPT subscription)\n  /model               (choose your provider and model)\n'
printf 'Try a greeting first. This installer never runs Tasks, contacts Tyr, or approves actions.\n'
if confirm 'Open Oh My Pi now for subscription sign-in and model selection?'; then
    [[ -t 0 && -t 1 ]] || fail 'Opening omp needs an interactive terminal. Run omp yourself.'
    cd -- "$ROOT"
    omp
fi
