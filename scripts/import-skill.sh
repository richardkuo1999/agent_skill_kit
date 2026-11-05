#!/usr/bin/env bash
# Copy one selected upstream skill into skills/<local_name>/ and record the
# upstream sha it came from. Run only after the user approved it.
# Usage: import-skill.sh <source> <upstream_path> [local_name]
set -euo pipefail
cd "$(dirname "$0")/.."
src=$1; path=$2; local_name=${3:-$2}
IFS=$'\t' read -r _ repo ref dir lic < <(awk -F'\t' -v s="$src" '$1==s' upstream/skill-sources.tsv)
[ -n "${repo:-}" ] || { echo "unknown source: $src" >&2; exit 1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
# tarball of an exact sha (works even where git is too old for a sparse clone)
sha=$(gh api "repos/$repo/commits/$ref" --jq .sha)
mkdir "$tmp/r"; gh api "repos/$repo/tarball/$sha" > "$tmp/t.tgz"
tar -xzf "$tmp/t.tgz" -C "$tmp/r" --strip-components=1
[ -f "$tmp/r/$dir/$path/SKILL.md" ] || { echo "no SKILL.md at $dir/$path" >&2; exit 1; }
rm -rf "skills/$local_name"; cp -r "$tmp/r/$dir/$path" "skills/$local_name"
[ -f "$tmp/r/$lic" ] && cp "$tmp/r/$lic" "upstream/licenses/$src.LICENSE"
# replace any previous row for this skill, then append the new one
grep -vP "^$src\t$path\t" upstream/skill-selected.tsv > "$tmp/sel" || true
printf '%s\t%s\t%s\t%s\n' "$src" "$path" "$local_name" "$sha" >> "$tmp/sel"
cp "$tmp/sel" upstream/skill-selected.tsv
echo "imported $src/$path -> skills/$local_name @ ${sha:0:9}"
