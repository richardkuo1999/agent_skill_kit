#!/usr/bin/env bash
# Link every skills/<name>/ into the skill directory of one or more AI tools.
# Usage: install.sh <target>... [--workspace DIR]
#   targets: kiro | antigravity | all      (global scope by default)
#   --workspace DIR: install into DIR's project-level skill folder instead
# Symlinks are used so `git pull` in this kit updates every tool at once.
set -euo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
targets=(); ws=""
while [ $# -gt 0 ]; do
  case $1 in
    --workspace) ws=$2; shift 2 ;;
    kiro|antigravity) targets+=("$1"); shift ;;
    all) targets+=(kiro antigravity); shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[ ${#targets[@]} -gt 0 ] || { sed -n '2,6p' "$0"; exit 2; }
for t in "${targets[@]}"; do
  case $t in
    kiro)        dest=${ws:+$ws/.kiro/skills};        dest=${dest:-$HOME/.kiro/skills} ;;
    antigravity) dest=${ws:+$ws/.agents/skills};      dest=${dest:-$HOME/.gemini/config/skills} ;;
  esac
  mkdir -p "$dest"
  for s in "$kit"/skills/*/; do
    n=$(basename "$s"); l="$dest/$n"
    if [ -e "$l" ] && [ ! -L "$l" ]; then echo "SKIP $l (exists, not a symlink)"; continue; fi
    ln -sfn "${s%/}" "$l"; echo "OK   $t: $n"
  done
done
