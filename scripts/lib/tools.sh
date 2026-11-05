#!/usr/bin/env bash
# Shared helpers for reading config/tools.tsv and converting rule frontmatter.
# Sourced by install-skill.sh and install-rule.sh. Not executable on its own.

# kit root = parent of scripts/
_kit_root() { cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd; }
TOOLS_TSV="$(_kit_root)/config/tools.tsv"

# expand a leading ~/ to $HOME/
_expand() { case $1 in '~/'*) printf '%s\n' "$HOME/${1#'~/'}" ;; *) printf '%s\n' "$1" ;; esac; }

# resolve_target <name|all> -> echoes validated tool names, one per line.
# "all" expands to every row in tools.tsv. Unknown name exits non-zero.
resolve_target() {
  local want=$1 names; names=$(grep -v '^#' "$TOOLS_TSV" | awk -F'\t' 'NF{print $1}')
  if [ "$want" = all ]; then printf '%s\n' $names; return 0; fi
  if printf '%s\n' $names | grep -qxF "$want"; then printf '%s\n' "$want"; return 0; fi
  echo "unknown tool: $want (known: $(echo $names | tr '\n' ' '))" >&2; return 1
}

# tool_field <name> <column-number 2..8> -> echoes the field, '~' expanded for paths.
tool_field() {
  local v; v=$(grep -v '^#' "$TOOLS_TSV" | awk -F'\t' -v n="$1" -v c="$2" '$1==n{print $c}')
  case $2 in 2|3|5|6) _expand "$v" ;; *) printf '%s\n' "$v" ;; esac
}

# install dir for a kind: install_dir <name> <skill|rule> <workspace-or-empty>
install_dir() {
  local name=$1 kind=$2 ws=$3 g p
  case $kind in
    skill) g=$(tool_field "$name" 2); p=$(tool_field "$name" 3) ;;
    rule)  g=$(tool_field "$name" 5); p=$(tool_field "$name" 6) ;;
  esac
  [ "$g" = - ] && return 1          # tool does not support this kind
  if [ -n "$ws" ]; then printf '%s\n' "$ws/$p"; else printf '%s\n' "$g"; fi
}

# ---- rule frontmatter converters (A class). stdin: kit frontmatter values via args.
# Each prints the full installed file (marker + frontmatter + body) to stdout.
# args: <marker> <title> <load> <desc> <globs> <bodyfile>
fmt_kiro() {
  local marker=$1 title=$2 load=$3 _desc=$4 globs=$5 body=$6 incl
  case $load in
    always) incl=always ;; glob) incl=fileMatch ;; manual) incl=manual ;;
    model) incl=manual; echo "WARN $title: Kiro has no model_decision; installed as manual" >&2 ;;
  esac
  echo "$marker"; echo "---"; echo "title: $title"; echo "inclusion: $incl"
  [ "$incl" = fileMatch ] && echo "fileMatchPattern: $globs"
  echo "---"; cat "$body"
}
fmt_antigravity() {
  local marker=$1 title=$2 load=$3 desc=$4 globs=$5 body=$6 tr
  case $load in
    always) tr=always_on ;; glob) tr=glob ;; manual) tr=manual ;; model) tr=model_decision ;;
  esac
  echo "$marker"; echo "---"; echo "trigger: $tr"
  [ -n "$desc" ] && echo "description: \"$desc\""
  [ "$tr" = glob ] && echo "globs: \"$globs\""
  echo "---"; cat "$body"
}
