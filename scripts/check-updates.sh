#!/usr/bin/env bash
# Read-only: for each imported skill, report upstream changes since the sha it
# was imported at, plus upstream skills never reviewed. Writes nothing.
# Usage: check-updates.sh   (needs `gh` logged in)
set -euo pipefail
cd "$(dirname "$0")/../upstream"
while IFS=$'\t' read -r name repo ref dir _lic; do
  case $name in ''|\#*) continue ;; esac
  head=$(gh api "repos/$repo/commits/$ref" --jq .sha)
  echo "== $name ($repo@$ref) head=${head:0:9}"
  tree=$(gh api "repos/$repo/git/trees/$ref?recursive=1" --jq '.tree[].path')
  upstream_skills=$(echo "$tree" | grep -E "^$dir/.*SKILL\.md$" | sed "s#^$dir/##;s#/SKILL\.md\$##")
  # known = imported + already shown to the user in CATALOG.md (reviewed.txt: "<source> <path>")
  known=$( (awk -F'\t' -v s="$name" '$1==s{print $2}' selected.tsv; awk -v s="$name" '$1==s{print $2}' reviewed.txt) | sort -u)
  while IFS=$'\t' read -r s p _ln sha; do
    [ "$s" = "$name" ] || continue
    if ! echo "$upstream_skills" | grep -qxF "$p"; then echo "   REMOVED/RENAMED upstream: $p"; continue; fi
    [ "$sha" = "$head" ] && { echo "   same    $p"; continue; }
    files=$(gh api "repos/$repo/compare/$sha...$head" --paginate --jq '.files[].filename' | grep -F "$dir/$p/" || true)
    if [ -n "$files" ]; then echo "   CHANGED $p"; echo "$files" | sed 's/^/     /'; else echo "   same    $p"; fi
  done < <(grep -v '^#' selected.tsv)
  echo "   new upstream skills (not in reviewed.txt):"
  echo "$upstream_skills" | grep -vxF "$known" | sed 's/^/     + /' || true
done < <(grep -v '^#' sources.tsv)
