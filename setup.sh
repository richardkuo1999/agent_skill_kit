#!/usr/bin/env bash
# One entry point: install everything this kit manages (skills, rules, and
# whatever gets added later) for one or more AI tools, in one run.
#
# Usage: ./setup.sh <target>... [--workspace DIR] [--only skills|rules]
#   targets:      any name in config/tools.tsv, or 'all' (global scope by default)
#   --workspace:  install into DIR's project-level folders instead of global
#   --only:       run just one installer (repeatable); default runs all
#
# Examples:
#   ./setup.sh antigravity                 # home: skills + rules, global
#   ./setup.sh kiro                        # work:  skills + rules, global
#   ./setup.sh all --workspace ~/proj      # both tools, project scope
#   ./setup.sh kiro --only rules           # just rules
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/scripts/lib/tools.sh"

# Each installer: "<label> <script> <relative glob it needs>".
# Add a line here when the kit grows a new managed thing (e.g. mcp, hooks);
# nothing else changes.
installers=(
  "skills scripts/install-skill.sh skills/*/"
  "rules  scripts/install-rule.sh  rules/*.md"
  "mcp    scripts/install-mcp.sh   config/mcp/*.json"
)

args=(); only=()
while [ $# -gt 0 ]; do
  case $1 in
    --only) only+=("$2"); shift 2 ;;
    *) args+=("$1"); shift ;;
  esac
done
# need at least one valid target (a name in tools.tsv, or all) in the args
have_target=0
for a in "${args[@]}"; do
  if [ "$a" = all ] || resolve_target "$a" >/dev/null 2>&1; then have_target=1; break; fi
done
[ "$have_target" = 1 ] || { sed -n '2,13p' "$0"; exit 2; }

run_one() { # label script glob
  local label=$1 script=$2 glob=$3
  # skip cleanly when that section has no content yet (e.g. empty rules/)
  compgen -G "$here/$glob" >/dev/null 2>&1 || { echo "== $label: nothing to install (empty), skipping"; return 0; }
  echo "== $label"
  "$here/$script" "${args[@]}"
}

for spec in "${installers[@]}"; do
  read -r label script glob <<<"$spec"
  if [ ${#only[@]} -gt 0 ]; then
    case " ${only[*]} " in *" $label "*) ;; *) continue ;; esac
  fi
  run_one "$label" "$script" "$glob"
done
