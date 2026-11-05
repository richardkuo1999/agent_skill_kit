#!/usr/bin/env bash
# Convert each rules/<name>.md into the target tool's rule format and install it.
# Usage: install-rule.sh <target>... [--workspace DIR]
#   targets: any name in config/tools.tsv, or 'all'   (global scope by default)
# Only overwrites installed files carrying the generated-by marker (anywhere in
# the file); a hand-written rule of the same name is left alone and reported.
set -euo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
. "$kit/scripts/lib/tools.sh"
marker="# $KIT_MARKER"   # full first-line comment for Kiro/Antigravity; grep matches the substring
targets=(); ws=""
while [ $# -gt 0 ]; do
  case $1 in
    --workspace) ws=$2; shift 2 ;;
    -*) echo "unknown arg: $1" >&2; exit 2 ;;
    *) targets+=($(resolve_target "$1")); shift ;;
  esac
done
[ ${#targets[@]} -gt 0 ] || { sed -n '2,6p' "$0"; exit 2; }

# read one frontmatter key from a source file
fm() { awk -v k="$2" '/^---/{c++;next} c==1 && $0 ~ "^"k":"{sub("^"k":[ \t]*","");gsub(/^"|"$/,"");print;exit}' "$1"; }
body_of() { awk '/^---/{c++;next} c>=2' "$1"; }

# does this rule target this tool? (kit_targets: all, or a comma list with $t)
targets_tool() { case ",$1," in *,all,*|*",$2,"*) return 0 ;; *) return 1 ;; esac; }

for t in "${targets[@]}"; do
  class=$(tool_field "$t" 4)
  dest=$(install_dir "$t" rule "$ws") || { echo "SKIP $t: no rule support"; continue; }

  if [ "$class" = A ]; then
    fmt=$(tool_field "$t" 7)
    ext=$(tool_field "$t" 8); ext=${ext:-md}
    mkdir -p "$dest"
    for src in "$kit"/rules/*.md; do
      n=$(basename "$src" .md); [ "$n" = README ] && continue
      load=$(fm "$src" kit_load); load=${load:-always}
      tgts=$(fm "$src" kit_targets); tgts=${tgts:-all}
      targets_tool "$tgts" "$t" || { echo "SKIP $t: $n (kit_targets=$tgts)"; continue; }
      title=$(fm "$src" title); title=${title:-$n}
      desc=$(fm "$src" description); globs=$(fm "$src" globs)
      out="$dest/$n.$ext"
      if [ -e "$out" ] && ! grep -qF "$KIT_MARKER" "$out"; then echo "SKIP $t: $n (hand-written, not overwriting)"; continue; fi
      bodyf=$(mktemp); body_of "$src" > "$bodyf"
      "$fmt" "$marker" "$title" "$load" "$desc" "$globs" "$bodyf" > "$out"
      rm -f "$bodyf"
      echo "OK   $t: $n ($load)"
    done

  elif [ "$class" = B ]; then
    # Strategy 3: merge only `always` rules into the single file; skip the rest.
    # dest is a FILE path here (e.g. CLAUDE.md), not a directory.
    mkdir -p "$(dirname "$dest")"
    block=$(mktemp); any=0
    for src in "$kit"/rules/*.md; do
      n=$(basename "$src" .md); [ "$n" = README ] && continue
      load=$(fm "$src" kit_load); load=${load:-always}
      tgts=$(fm "$src" kit_targets); tgts=${tgts:-all}
      targets_tool "$tgts" "$t" || { echo "SKIP $t: $n (kit_targets=$tgts)"; continue; }
      if [ "$load" != always ]; then echo "SKIP $t: $n (kit_load=$load; single-file $(basename "$dest") takes always only)"; continue; fi
      title=$(fm "$src" title); title=${title:-$n}
      { echo "## [kit rule] $title"; echo; body_of "$src"; echo; } >> "$block"
      any=$((any+1)); echo "OK   $t: $n (merged)"
    done
    if [ "$any" -gt 0 ]; then
      merge_single_file "$dest" "$block"
    else
      echo "SKIP $t: no always-rules for this tool; $(basename "$dest") untouched"
    fi
    rm -f "$block"

  else
    echo "SKIP $t: unknown rule_class=$class"; continue
  fi
done
