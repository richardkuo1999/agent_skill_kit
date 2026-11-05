#!/usr/bin/env bash
# Pre-publish safety check. Run before every push, especially the first public
# one. Read-only: inspects git history and the worktree, writes nothing.
# Exit 0 = safe to push; non-zero = at least one check failed (see output).
# Usage: scripts/check-public.sh
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
ok()   { printf 'PASS  %s\n' "$1"; }
bad()  { printf 'FAIL  %s\n' "$1"; fail=1; }
warn() { printf 'WARN  %s\n' "$1"; }

# 1. secrets.env never committed
if [ "$(git log --all --format='%H' --name-only 2>/dev/null | grep -c '^config/secrets.env$')" = 0 ]; then
  ok "config/secrets.env never appears in history"
else
  bad "config/secrets.env IS in git history — scrub it before pushing"
fi

# 2. secrets.env is gitignored
if git check-ignore config/secrets.env >/dev/null 2>&1; then ok "config/secrets.env is gitignored"
else bad "config/secrets.env is NOT gitignored"; fi

# 3. example template tracked
if git ls-files --error-unmatch config/secrets.env.example >/dev/null 2>&1; then ok "config/secrets.env.example is tracked"
else warn "config/secrets.env.example not tracked (users have no template)"; fi

# 4. no token-shaped strings anywhere in history
hits=$(git log --all -p 2>/dev/null \
  | grep -iE 'sk-[a-z0-9]{10,}|ghp_[a-z0-9]{10,}|AKIA[A-Z0-9]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-[a-z0-9-]{10,}' \
  || true)
if [ -z "$hits" ]; then ok "no token-shaped strings in history"
else bad "token-shaped strings found in history:"; echo "$hits" | head -5 | sed 's/^/      /'; fi

# 5. no real assignment to a secret-looking key (excluding refs / examples)
leaks=$(git log --all -p 2>/dev/null \
  | grep -iE '^\+.*(TOKEN|SECRET|API_KEY|PASSWORD)[[:space:]]*[=:]' \
  | grep -viE 'KIT_SECRET|replace-me|secrets\.env|example|^\+#|placeholder' || true)
if [ -z "$leaks" ]; then ok "no real secret assignments in history"
else warn "possible secret assignments (review each):"; echo "$leaks" | head -5 | sed 's/^/      /'; fi

# 6. imported skills/rules carry no embedded credentials (worktree)
emb=$(grep -rliE 'sk-[a-z0-9]{10,}|ghp_[a-z0-9]{10,}|AKIA[A-Z0-9]{12,}' skills rules config/mcp 2>/dev/null || true)
if [ -z "$emb" ]; then ok "no embedded credentials in skills/ rules/ config/mcp/"
else bad "embedded credential-shaped strings in:"; echo "$emb" | sed 's/^/      /'; fi

# 7. single commit-author email (informational)
authors=$(git log --all --format='%ae' 2>/dev/null | sort -u)
n=$(printf '%s\n' "$authors" | grep -c .)
if [ "$n" -le 1 ]; then ok "single commit-author email: $authors"
else warn "multiple author emails (confirm all are intended to be public):"; echo "$authors" | sed 's/^/      /'; fi

echo
if [ "$fail" = 0 ]; then echo "RESULT: safe to push (review any WARN above)."; else echo "RESULT: DO NOT PUSH — fix the FAIL items first."; fi
exit $fail
