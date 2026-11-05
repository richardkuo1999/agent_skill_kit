#!/usr/bin/env bash
# Three-way compare for one imported skill. Read-only for skills/.
#   base   = upstream at the sha recorded in selected.tsv
#   mine   = skills/<local_name>/
#   theirs = upstream at current HEAD of the tracked ref
# Output dir (printed at the end): mine-vs-base.diff, theirs-vs-base.diff, merged/
# merged/ holds a `git merge-file` result per file; conflicts keep <<<<<<< markers.
# Usage: diff-upstream.sh <local_name> [outdir]
set -euo pipefail
cd "$(dirname "$0")/.."
name=$1; out=${2:-${KIROCREW_SCRATCH:-$(mktemp -d)}/diff-$name}
IFS=$'\t' read -r src path _ base < <(awk -F'\t' -v n="$name" '$3==n' upstream/selected.tsv)
[ -n "${src:-}" ] || { echo "not imported: $name" >&2; exit 1; }
IFS=$'\t' read -r _ repo ref dir _lic < <(awk -F'\t' -v s="$src" '$1==s' upstream/sources.tsv)
head=$(gh api "repos/$repo/commits/$ref" --jq .sha)
rm -rf "$out"; mkdir -p "$out/base" "$out/theirs" "$out/merged"
fetch() { # sha dest
  local t; t=$(mktemp -d); gh api "repos/$repo/tarball/$1" | tar -xz -C "$t" --strip-components=1
  [ -d "$t/$dir/$path" ] && cp -r "$t/$dir/$path/." "$2/"; rm -rf "$t"
}
fetch "$base" "$out/base"; fetch "$head" "$out/theirs"
diff -ruN "$out/base" "skills/$name" > "$out/mine-vs-base.diff" || true
diff -ruN "$out/base" "$out/theirs" > "$out/theirs-vs-base.diff" || true
conflicts=0
kit=$(pwd)
all_files=$( { (cd "$out/base" 2>/dev/null && find . -type f); (cd "$out/theirs" 2>/dev/null && find . -type f); (cd "$kit/skills/$name" 2>/dev/null && find . -type f); } | sort -u)
for f in $all_files; do
  b="$out/base/$f"; t="$out/theirs/$f"; m="skills/$name/$f"; mkdir -p "$out/merged/$(dirname "$f")"
  if [ -f "$b" ] && [ -f "$t" ] && [ -f "$m" ]; then
    cp "$m" "$out/merged/$f"
    git merge-file "$out/merged/$f" "$b" "$t" || { echo "CONFLICT  $f"; conflicts=$((conflicts+1)); }
  elif [ -f "$m" ] && [ ! -f "$t" ] && [ -f "$b" ]; then echo "DELETED UPSTREAM  $f"
  elif [ -f "$t" ] && [ ! -f "$b" ] && [ ! -f "$m" ]; then echo "NEW UPSTREAM      $f"; cp "$t" "$out/merged/$f"
  elif [ -f "$m" ]; then cp "$m" "$out/merged/$f"; fi
done
echo "$head" > "$out/head.sha"
echo "base=${base:0:9} head=${head:0:9} conflicts=$conflicts"
echo "mine-vs-base: $(grep -c '^[+-][^+-]' "$out/mine-vs-base.diff" || true) changed lines (your edits)"
echo "theirs-vs-base: $(grep -c '^[+-][^+-]' "$out/theirs-vs-base.diff" || true) changed lines (official edits)"
echo "output: $out"
