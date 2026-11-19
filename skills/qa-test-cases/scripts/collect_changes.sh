#!/usr/bin/env bash
# Collecte les modifications courantes d'un dépôt git pour l'analyse QA.
#
# Usage : collect_changes.sh [--base <ref>] [--staged] [--max-untracked-lines N]
#
# Portée :
#   (défaut)      auto : changements non commités (index + working tree + non suivis)
#                 s'il y en a, sinon commits de la branche absents de la branche par défaut.
#   --staged      seulement l'index.
#   --base <ref>  merge-base(<ref>, HEAD) → working tree (commits de la branche + non commités).
set -euo pipefail

BASE=""
STAGED=0
MAX_UNTRACKED_LINES=400

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE="${2:?--base requiert une référence}"; shift 2 ;;
    --staged) STAGED=1; shift ;;
    --max-untracked-lines) MAX_UNTRACKED_LINES="${2:?}"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Argument inconnu : $1" >&2; exit 2 ;;
  esac
done

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERREUR : le répertoire courant n'est pas un dépôt git." >&2
  exit 1
fi

cd "$(git rev-parse --show-toplevel)"

section() { printf '\n===== %s =====\n' "$1"; }

detect_default_branch() {
  local ref
  ref=$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null || true)
  if [[ -n "$ref" ]]; then echo "${ref#refs/remotes/}"; return; fi
  for cand in origin/main origin/master origin/develop main master develop; do
    if git rev-parse --verify --quiet "$cand" >/dev/null; then echo "$cand"; return; fi
  done
}

HAS_HEAD=1
git rev-parse --verify --quiet HEAD >/dev/null || HAS_HEAD=0

REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
BRANCH=$(git branch --show-current 2>/dev/null || echo "")
HEAD_SHA=$([[ $HAS_HEAD -eq 1 ]] && git rev-parse --short HEAD || echo "")

UNCOMMITTED=$(git status --porcelain --untracked-files=all)

SCOPE=""
DIFF_ARGS=()
if [[ $STAGED -eq 1 ]]; then
  SCOPE="staged"
  DIFF_ARGS=(--cached)
elif [[ -n "$BASE" ]]; then
  git rev-parse --verify --quiet "$BASE" >/dev/null || { echo "ERREUR : référence inconnue : $BASE" >&2; exit 1; }
  MB=$(git merge-base "$BASE" HEAD)
  SCOPE="branch"
  DIFF_ARGS=("$MB")
elif [[ -n "$UNCOMMITTED" ]]; then
  SCOPE="working-tree"
  if [[ $HAS_HEAD -eq 1 ]]; then DIFF_ARGS=(HEAD); else DIFF_ARGS=(--cached); fi
else
  DEFAULT=$(detect_default_branch)
  if [[ -z "$DEFAULT" ]]; then
    echo "Aucun changement non commité et aucune branche par défaut détectée. Utilisez --base <ref>." >&2
    exit 1
  fi
  BASE="$DEFAULT"
  MB=$(git merge-base "$BASE" HEAD)
  SCOPE="branch"
  DIFF_ARGS=("$MB")
fi

section "METADATA"
echo "repository: $REPO_NAME"
[[ -n "$REMOTE_URL" ]] && echo "remote: $REMOTE_URL"
echo "branch: ${BRANCH:-<detached>}"
echo "headCommit: $HEAD_SHA"
echo "diffScope: $SCOPE"
[[ -n "$BASE" ]] && echo "baseRef: $BASE"
[[ -n "${MB:-}" ]] && echo "mergeBase: $(git rev-parse --short "$MB")"
echo "generatedAt: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ "$SCOPE" == "branch" ]]; then
  section "COMMITS ($BASE..HEAD)"
  git log --no-merges --format='- %h %s%n%w(0,4,4)%b' "$MB..HEAD" | sed '/^\s*$/d' || true
fi

section "STATUS"
git status --short --untracked-files=all || true

section "FILES CHANGED (name-status)"
git diff "${DIFF_ARGS[@]}" --name-status -M || true
if [[ "$SCOPE" != "staged" ]]; then
  git ls-files --others --exclude-standard | sed 's/^/??\t/'
fi

section "DIFF STAT"
git diff "${DIFF_ARGS[@]}" --stat -M || true

section "DIFF"
git diff "${DIFF_ARGS[@]}" -M --unified=5 --no-color || true

if [[ "$SCOPE" != "staged" ]]; then
  UNTRACKED=$(git ls-files --others --exclude-standard)
  if [[ -n "$UNTRACKED" ]]; then
    section "UNTRACKED FILES CONTENT"
    while IFS= read -r f; do
      [[ -f "$f" ]] || continue
      if grep -Iq . "$f" 2>/dev/null || [[ ! -s "$f" ]]; then
        LINES=$(wc -l < "$f")
        echo "----- $f ($LINES lignes) -----"
        head -n "$MAX_UNTRACKED_LINES" "$f"
        [[ "$LINES" -gt "$MAX_UNTRACKED_LINES" ]] && echo "... [tronqué, lire le fichier complet]"
      else
        echo "----- $f (binaire, ignoré) -----"
      fi
    done <<< "$UNTRACKED"
  fi
fi

section "END"
