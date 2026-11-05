#!/usr/bin/env bash
# Import one upstream Markdown file as a kit rule: strip its upstream frontmatter,
# wrap the body in this kit's rule frontmatter, and write rules/<local_name>.md.
# Records the source file path and sha so check-updates.sh / diff-upstream.sh
# can track it later. Run only after the user approved it.
# Usage: import-rule.sh <source> <upstream_file_path> <local_name> [kit_load]
#   kit_load: always (default) | glob | manual | model
set -euo pipefail
cd "$(dirname "$0")/.."
src=$1; fpath=$2; local_name=$3; load=${4:-always}
IFS=$'\t' read -r _ repo ref lic < <(grep -v '^#' upstream/rule-sources.tsv | awk -F'\t' -v s="$src" '$1==s')
[ -n "${repo:-}" ] || { echo "unknown rule source: $src" >&2; exit 1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
sha=$(gh api "repos/$repo/commits/$ref" --jq .sha)
mkdir "$tmp/r"; gh api "repos/$repo/tarball/$sha" > "$tmp/t.tgz"
tar -xzf "$tmp/t.tgz" -C "$tmp/r" --strip-components=1
up="$tmp/r/$fpath"
[ -f "$up" ] || { echo "no file at $fpath" >&2; exit 1; }
# pull a description out of the upstream frontmatter if present (for model/glob)
desc=$(awk '/^---/{c++;next} c==1 && /^description:/{sub(/^description:[ \t]*/,"");gsub(/^"|"$/,"");print;exit}' "$up")
# body = everything after upstream frontmatter (or whole file if none)
has_fm=$(head -1 "$up" | grep -qx -- '---' && echo 1 || echo 0)
if [ "$has_fm" = 1 ]; then body=$(awk '/^---/{c++;next} c>=2' "$up"); else body=$(cat "$up"); fi
{
  echo "---"
  echo "kit_load: $load"
  echo "kit_targets: all"
  echo "title: $local_name"
  [ -n "$desc" ] && echo "description: $desc"
  echo "kit_source: $src:$fpath"
  echo "---"
  echo
  printf '%s\n' "$body"
} > "rules/$local_name.md"
[ -f "$tmp/r/$lic" ] && cp "$tmp/r/$lic" "upstream/licenses/$src.LICENSE"
grep -vP "^$src\t$(printf '%s' "$fpath" | sed 's/[.[\*^$]/\\&/g')\t" upstream/rule-selected.tsv > "$tmp/sel" || true
printf '%s\t%s\t%s\t%s\t%s\n' "$src" "$fpath" "$local_name" "$load" "$sha" >> "$tmp/sel"
cp "$tmp/sel" upstream/rule-selected.tsv
echo "imported rule $src/$fpath -> rules/$local_name.md ($load) @ ${sha:0:9}"
echo "NOTE: review rules/$local_name.md — the upstream text may name tools (subagents, /commands) that need rewriting for Kiro/Antigravity."
