#!/usr/bin/env bash
# Read-only: report upstream changes for imported skills AND imported rules since
# the sha each was imported at, plus upstream skills never reviewed. Writes nothing.
# Usage: check-updates.sh   (needs `gh` logged in)
set -euo pipefail
cd "$(dirname "$0")/../upstream"

echo "##### SKILLS"
while IFS=$'\t' read -r name repo ref dir _lic; do
  case $name in ''|\#*) continue ;; esac
  head=$(gh api "repos/$repo/commits/$ref" --jq .sha)
  echo "== $name ($repo@$ref) head=${head:0:9}"
  tree=$(gh api "repos/$repo/git/trees/$ref?recursive=1" --jq '.tree[].path')
  upstream_skills=$(echo "$tree" | grep -E "^$dir/.*SKILL\.md$" | sed "s#^$dir/##;s#/SKILL\.md\$##")
  # known = imported + already shown to the user in CATALOG.md (skill-reviewed.txt: "<source> <path>")
  known=$( (awk -F'\t' -v s="$name" '$1==s{print $2}' skill-selected.tsv; awk -v s="$name" '$1==s{print $2}' skill-reviewed.txt) | sort -u)
  while IFS=$'\t' read -r s p _ln sha; do
    [ "$s" = "$name" ] || continue
    if ! echo "$upstream_skills" | grep -qxF "$p"; then echo "   REMOVED/RENAMED upstream: $p"; continue; fi
    [ "$sha" = "$head" ] && { echo "   same    $p"; continue; }
    files=$(gh api "repos/$repo/compare/$sha...$head" --paginate --jq '.files[].filename' | grep -F "$dir/$p/" || true)
    if [ -n "$files" ]; then echo "   CHANGED $p"; echo "$files" | sed 's/^/     /'; else echo "   same    $p"; fi
  done < <(grep -v '^#' skill-selected.tsv)
  echo "   new upstream skills (not in skill-reviewed.txt):"
  echo "$upstream_skills" | grep -vxF "$known" | sed 's/^/     + /' || true
done < <(grep -v '^#' skill-sources.tsv)

echo "##### RULES"
# Rules track a single upstream file each; there is no "scan repo for new rules"
# step, since any .md could be a rule. Report only changes to imported rules.
while IFS=$'\t' read -r name repo ref _lic; do
  case $name in ''|\#*) continue ;; esac
  head=$(gh api "repos/$repo/commits/$ref" --jq .sha)
  any=$(awk -F'\t' -v s="$name" '$1==s' rule-selected.tsv)
  [ -n "$any" ] || continue
  echo "== $name ($repo@$ref) head=${head:0:9}"
  # compare across a wide commit range can paginate/return null .files; comparing
  # the file's own blob sha at each commit is exact and range-size independent.
  blob() { gh api "repos/$repo/contents/$2?ref=$1" --jq .sha 2>/dev/null; }
  while IFS=$'\t' read -r s fpath ln _load sha; do
    [ "$s" = "$name" ] || continue
    [ "$sha" = "$head" ] && { echo "   same    $ln ($fpath)"; continue; }
    if [ "$(blob "$sha" "$fpath")" = "$(blob "$head" "$fpath")" ]; then echo "   same    $ln ($fpath)"
    else echo "   CHANGED $ln ($fpath)"; fi
  done < <(grep -v '^#' rule-selected.tsv)
done < <(grep -v '^#' rule-sources.tsv)
