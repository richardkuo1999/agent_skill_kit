#!/usr/bin/env bash
# Three-way compare for one imported skill OR rule. Read-only for skills/ and rules/.
#   base   = upstream at the sha recorded in *-selected.tsv
#   mine   = skills/<local_name>/  (skill)  or  rules/<local_name>.md body (rule)
#   theirs = upstream at current HEAD of the tracked ref
# Output dir (printed at the end): mine-vs-base.diff, theirs-vs-base.diff, and a
# merged result; conflicts keep <<<<<<< markers.
# Usage: diff-upstream.sh <local_name> [outdir]            # skill (folder)
#        diff-upstream.sh --rule <local_name> [outdir]     # rule (single file, body only)
# Rule mode: diff-upstream.sh --rule <local_name> [outdir]
#   Single file. Compares only the Markdown BODY (kit and upstream frontmatter
#   differ by design, so frontmatter is stripped before diffing).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${1:-}" = --rule ]; then
  name=$2; out=${3:-${KIROCREW_SCRATCH:-$(mktemp -d)}/diffrule-$name}
  IFS=$'\t' read -r src fpath _ln _load base < <(awk -F'\t' -v n="$name" '$3==n' upstream/rule-selected.tsv)
  [ -n "${src:-}" ] || { echo "not an imported rule: $name" >&2; exit 1; }
  IFS=$'\t' read -r _ repo ref _lic < <(grep -v '^#' upstream/rule-sources.tsv | awk -F'\t' -v s="$src" '$1==s')
  head=$(gh api "repos/$repo/commits/$ref" --jq .sha)
  rm -rf "$out"; mkdir -p "$out"
  strip_fm() { awk 'NR==1 && $0=="---"{f=1;next} f && $0=="---"{f=0;next} !f' "$1"; }  # drop a leading frontmatter block
  upbody() { local t; t=$(mktemp -d); gh api "repos/$repo/tarball/$1" | tar -xz -C "$t" --strip-components=1; strip_fm "$t/$fpath" > "$2"; rm -rf "$t"; }
  upbody "$base" "$out/base.md"; upbody "$head" "$out/theirs.md"
  strip_fm "rules/$name.md" > "$out/mine.md"
  diff -u "$out/base.md" "$out/mine.md"   > "$out/mine-vs-base.diff"   || true
  diff -u "$out/base.md" "$out/theirs.md" > "$out/theirs-vs-base.diff" || true
  cp "$out/mine.md" "$out/merged-body.md"
  if git merge-file "$out/merged-body.md" "$out/base.md" "$out/theirs.md"; then conflicts=0; else conflicts=1; echo "CONFLICT in body"; fi
  echo "$head" > "$out/head.sha"
  echo "base=${base:0:9} head=${head:0:9} conflicts=$conflicts"
  echo "mine-vs-base: $(grep -c '^[+-][^+-]' "$out/mine-vs-base.diff" || true) changed body lines (your edits)"
  echo "theirs-vs-base: $(grep -c '^[+-][^+-]' "$out/theirs-vs-base.diff" || true) changed body lines (official edits)"
  echo "merged body (reapply your kit frontmatter on top): $out/merged-body.md"
  echo "output: $out"
  exit 0
fi

name=$1; out=${2:-${KIROCREW_SCRATCH:-$(mktemp -d)}/diff-$name}
IFS=$'\t' read -r src path _ base < <(awk -F'\t' -v n="$name" '$3==n' upstream/skill-selected.tsv)
[ -n "${src:-}" ] || { echo "not imported: $name" >&2; exit 1; }
IFS=$'\t' read -r _ repo ref dir _lic < <(awk -F'\t' -v s="$src" '$1==s' upstream/skill-sources.tsv)
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
