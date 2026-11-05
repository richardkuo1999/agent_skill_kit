#!/usr/bin/env bash
# Link every skills/<name>/ into the skill directory of one or more AI tools.
# Usage: install-skill.sh <target>... [--workspace DIR]
#   targets: any name in config/tools.tsv, or 'all'   (global scope by default)
#   --workspace DIR: install into DIR's project-level skill folder instead
# Symlinks are used so `git pull` in this kit updates every tool at once.
set -euo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
. "$kit/scripts/lib/tools.sh"
targets=(); ws=""
while [ $# -gt 0 ]; do
  case $1 in
    --workspace) ws=$2; shift 2 ;;
    -*) echo "unknown arg: $1" >&2; exit 2 ;;
    *) targets+=($(resolve_target "$1")); shift ;;
  esac
done
[ ${#targets[@]} -gt 0 ] || { sed -n '2,6p' "$0"; exit 2; }
for t in "${targets[@]}"; do
  dest=$(install_dir "$t" skill "$ws") || { echo "SKIP $t: no skill support"; continue; }
  mkdir -p "$dest"
  for s in "$kit"/skills/*/; do
    n=$(basename "$s"); l="$dest/$n"
    if [ -e "$l" ] && [ ! -L "$l" ]; then echo "SKIP $l (exists, not a symlink)"; continue; fi
    ln -sfn "${s%/}" "$l"; echo "OK   $t: $n"
  done
done
