#!/usr/bin/env bash
# End-to-end smoke test: run the whole install flow in a throwaway sandbox with
# fake skill/rule/MCP content, assert each tool got the right output, check
# idempotence, and clean up. Tests the MECHANISM, not real content.
# Usage: scripts/smoke-test.sh   (needs jq; python 'toml' for the Codex check)
# Exit 0 = all assertions passed.
set -uo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d); home="$work/home"; proj="$work/proj"
trap 'rm -rf "$work"' EXIT
pass=0; fail=0
ok()  { pass=$((pass+1)); printf 'ok   %s\n' "$1"; }
no()  { fail=$((fail+1)); printf 'FAIL %s\n' "$1"; }
has() { if [ -e "$2" ] || [ -L "$2" ]; then ok "$1"; else no "$1 (missing $2)"; fi; }
grep_ok() { if grep -qF "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1"; fi; }

# --- build a sandbox copy of the kit with fake content ---
sb="$work/kit"; cp -r "$kit" "$sb"; rm -rf "$sb/.git"
mkdir -p "$sb/skills/smoke-skill"; echo "# smoke" > "$sb/skills/smoke-skill/SKILL.md"
printf -- '---\nkit_load: always\ntitle: Smoke Always\ndescription: d\n---\nalways body\n' > "$sb/rules/smoke-always.md"
printf -- '---\nkit_load: glob\nglobs: "*.ts"\ndescription: d\n---\nglob body\n'            > "$sb/rules/smoke-glob.md"
mkdir -p "$sb/config/mcp"
printf '{"command":"npx","args":["-y","smoke-mcp"],"env":{"T":"${KIT_SECRET:SMOKE_TOKEN}"},"targets":"all"}\n' > "$sb/config/mcp/smoke.json"
printf 'SMOKE_TOKEN=smoke-secret-value\n' > "$sb/config/secrets.env"

echo "== setup all (global) =="
HOME="$home" "$sb/setup.sh" all >/dev/null 2>&1 || true
HOME="$home" "$sb/scripts/install-mcp.sh" all >/dev/null 2>&1 || true

# --- skills: every tool with a skill dir got the symlink ---
has "kiro skill"        "$home/.kiro/skills/smoke-skill"
has "antigravity skill" "$home/.gemini/config/skills/smoke-skill"
has "cursor skill"      "$home/.cursor/skills/smoke-skill"
has "claude skill"      "$home/.claude/skills/smoke-skill"
has "codex skill"       "$home/.codex/skills/smoke-skill"
has "kirocrew skill"    "$home/.kiro/crew/skills/smoke-skill"

# --- rules: A-class tools got the always-rule, with correct frontmatter ---
grep_ok "kiro rule inclusion"      "inclusion: always"  "$home/.kiro/steering/smoke-always.md"
grep_ok "antigravity rule trigger" "trigger: always_on" "$home/.gemini/config/rules/smoke-always.md"
# B-class: CLAUDE.md / AGENTS.md got the merged block with the always rule only
grep_ok "claude merged block" "kit:start" "$home/.claude/CLAUDE.md"
grep_ok "claude always rule"  "Smoke Always" "$home/.claude/CLAUDE.md"
if grep -qF "glob body" "$home/.claude/CLAUDE.md" 2>/dev/null; then no "claude excluded glob rule"; else ok "claude excluded glob rule"; fi
grep_ok "codex merged block"  "kit:start" "$home/.codex/AGENTS.md"

# --- MCP: JSON merge + secret substitution; TOML merge ---
grep_ok "kiro mcp server"    '"smoke"'            "$home/.kiro/settings/mcp.json"
grep_ok "kiro mcp secret"    "smoke-secret-value" "$home/.kiro/settings/mcp.json"
grep_ok "codex mcp toml"     "mcp_servers.smoke"  "$home/.codex/config.toml"
if command -v jq >/dev/null; then
  jq -e '.mcpServers.smoke' "$home/.cursor/mcp.json" >/dev/null 2>&1 && ok "cursor mcp valid json" || no "cursor mcp valid json"
fi

# --- idempotence: reinstall, counts must not grow ---
before=$(grep -c 'kit:start' "$home/.claude/CLAUDE.md")
HOME="$home" "$sb/setup.sh" all >/dev/null 2>&1 || true
HOME="$home" "$sb/scripts/install-mcp.sh" all >/dev/null 2>&1 || true
after=$(grep -c 'kit:start' "$home/.claude/CLAUDE.md")
[ "$before" = 1 ] && [ "$after" = 1 ] && ok "claude block idempotent" || no "claude block idempotent ($before->$after)"
n=$(grep -c '"smoke"' "$home/.kiro/settings/mcp.json")
[ "$n" = 1 ] && ok "kiro mcp idempotent" || no "kiro mcp idempotent (x$n)"

# --- project scope ---
HOME="$home" "$sb/setup.sh" cursor --workspace "$proj" >/dev/null 2>&1 || true
has "cursor project rule" "$proj/.cursor/rules/smoke-always.mdc"

# --- check-public passes on the fake kit (it has secrets.env, gitignored) ---
# (run against the sandbox's own git-less tree: just the worktree-embedded check)
if grep -rqiE 'smoke-secret-value' "$sb/skills" "$sb/rules" 2>/dev/null; then no "no secret leaked into tracked dirs"; else ok "no secret leaked into tracked dirs"; fi

echo
echo "SMOKE: $pass passed, $fail failed"
[ "$fail" = 0 ]
