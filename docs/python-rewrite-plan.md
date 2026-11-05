# Python rewrite plan (for review — not yet implemented)

## Why

Most colleagues are on Windows, and they want to import their own upstream repos,
not just consume a maintained kit. The bash scripts cannot serve that:

- bash itself is not native on Windows (needs WSL or Git Bash).
- skill install uses `ln -sfn`; Windows symlinks need admin/developer mode, and
  Git Bash turns `ln -s` into a copy.
- paths are hardcoded Unix (`~`, `/`); tool config dirs differ on Windows.
- external deps: `jq`, `gh`, `tar`, plus `python+toml`.

Python fixes all of this with the standard library and reduces external deps to
just **Python + git**.

## Scope: rewrite the whole script layer, keep the two skills

| current (bash) | lines | Python target | external deps removed |
|----------------|-------|---------------|-----------------------|
| install-skill.sh | 27 | install.py (skill) | — (symlink→copy fallback on Windows) |
| install-rule.sh | 76 | install.py (rule) | — |
| install-mcp.sh | 93 | install.py (mcp) | jq (use stdlib json + tomllib read; toml write pkg) |
| lib/tools.sh | — | kitlib.py | jq |
| import-skill.sh | 22 | kit.py import-skill | gh, tar (use urllib + tarfile) |
| import-rule.sh | 40 | kit.py import-rule | gh, tar |
| check-updates.sh | 46 | kit.py check-updates | gh (use urllib → GitHub API) |
| diff-upstream.sh | 69 | kit.py diff-upstream | diff (keep `git merge-file`) |
| check-public.sh | 55 | kit.py check-public | — (git only) |
| smoke-test.sh | 74 | test_kit.py | — |
| setup.sh | 56 | setup.py (or kit.py install) | — |

`skills/upstream-sync`, `skills/tools-sync`: unchanged. They are agent-run
markdown; they just call the new `kit.py` subcommands instead of the `.sh` ones.

## Proposed shape

One entry point, subcommands (keeps it one file to ship, easy on Windows):

```
python kit.py install <tool>... [--workspace DIR] [--only skills|rules|mcp]
python kit.py import-skill <source> <path> [name]
python kit.py import-rule  <source> <file> <name> [load]
python kit.py check-updates
python kit.py diff <name> [--rule]
python kit.py check-public
```

- `kitlib.py`: shared helpers (read tools.tsv / mcp-targets.tsv, path expansion,
  frontmatter parse, secret substitution, the rule converters).
- stdlib only: `pathlib`, `json`, `csv`, `urllib.request`, `tarfile`, `difflib`,
  `re`, `subprocess` (for git). TOML: `tomllib` (3.11+) to read; for write, try
  `tomli_w`, else `toml`, else fail loud — documented in requirements.txt.

## Cross-platform specifics

- **Paths**: RESOLVED — no per-OS table needed. Verified (2026-11) that on
  Windows `~` = `%USERPROFILE%` for all five tools (Claude's docs state it
  explicitly; Kiro/Antigravity/Codex/Cursor confirmed by their docs/community),
  and the path structure is otherwise identical. So `tools.tsv` keeps its `~/...`
  values and Python resolves them with `pathlib.Path.home()`, which expands
  correctly per OS. Project-scope paths (`.kiro/`, `.cursor/`, `.agents/`, …) are
  relative and identical across OSes. Full Windows path table is in
  docs/windows-paths.md. Two items still need a live check: Antigravity's Windows
  MCP path (`config\` vs `antigravity\`) and Cursor's `~/.cursor/skills` global
  skill dir (inferred, medium confidence).
- **Symlink**: default is try `os.symlink`; on failure (Windows without admin or
  developer mode) fall back to copytree and print that `git pull` then needs a
  re-run to update. A `--copy` flag forces copy mode without attempting a symlink
  (for users who prefer it or know they lack privilege). Record which mode was
  used. Admin mode is NOT required — do not tell colleagues to run as admin.
- **Secrets / public**: unchanged design (`config/secrets.env`, `${KIT_SECRET}`),
  just implemented in Python.

## Minimum Python version

- Floor is **3.11**, so `tomllib` (stdlib) reads TOML with no fallback. TOML
  write still needs a package (`tomli_w` or `toml`) in requirements.txt. State
  the 3.11 floor in README.

## Migration strategy (the part that protects correctness)

1. Verify Windows tool paths first (no code).
2. Port one piece at a time, each diffed against its bash output for equivalence
   on Linux (same method as the earlier refactor): install-skill → install-rule →
   install-mcp → import → check-updates → diff → check-public → setup.
   PROGRESS: kitlib.py (table read, ~ expand, frontmatter, secrets) + kit.py
   `install` SKILLS done — symlink tree matches install-skill.sh exactly (18
   links across 6 tools), --copy and --workspace verified, unknown tool exits 1.
   Written 3.11-targeted but kept runnable on this host's 3.6 so the diff works
   (no `from __future__ annotations`, no PEP 585 generics, no required=True
   subparsers).
   install RULES done too — A-class (fmt_kiro/antigravity/cursor) and B-class
   single-file merge all byte-match install-rule.sh across the five tools, incl.
   hand-written protection and reinstall idempotence. Found and fixed a latent
   bug in BOTH versions while porting: merge_single_file accumulated a blank line
   on every reinstall; trailing blank lines in the kept (user) text are now
   normalized to one.
   install MCP done — json via stdlib, toml via tomllib-read/toml-write,
   KIT_SECRET substitution, existing-server preservation; byte-matches
   install-mcp.sh. import-skill/import-rule done — anonymous GitHub via
   urllib+tarfile (no gh/tar), byte-matching bash incl. selected rows and
   license. check-updates done — git/trees + contents-blob comparison replace
   gh/compare; SKILLS and RULES sections match bash. _gh_get honors an optional
   GITHUB_TOKEN/GH_TOKEN to lift the 60/hr anonymous limit.
   diff done — skill (folder three-way) and rule (body-only) modes. base/head,
   conflict detection, DELETED/NEW UPSTREAM, and the merged tree all match
   diff-upstream.sh; git merge-file is kept for the merge. One intentional
   non-equivalence: the "changed lines" COUNT can differ by a line or two
   because Python's difflib groups hunks differently from GNU diff — the diff
   CONTENT (what the agent actually reads) is the same, and the count is only a
   size hint, so this is acceptable and noted. Next: check-public, setup,
   smoke-test, then delete bash.
3. Keep the bash scripts in place until the Python set passes the smoke test on
   Linux AND a real run on Windows. Only then decide whether to delete bash or
   keep both.
4. Port smoke-test.sh to test_kit.py last; it is the equivalence gate.

## Decisions (settled)

- **One `kit.py` with subcommands** + `kitlib.py` for shared logic. Single entry
  point, git-style (`python kit.py install kiro`, `... import-skill ...`,
  `... check-updates`, `... check-public`). Easiest for Windows colleagues.
- **Per-OS paths: not needed** — pathlib resolves `~` per OS (see above).
- **Minimum Python 3.11.** TOML read uses stdlib `tomllib` (3.11+), so no `tomli`
  fallback is needed — simpler. TOML write still needs a package (`tomli_w` or
  `toml`), declared in requirements.txt. README must state the 3.11 floor.
  (This repo's own machine is 3.6 — use the bash version there; Python targets
  colleagues, not this host.)
- **Colleagues self-serve**: they need install AND import/check-updates/diff, so
  the whole script layer is ported, not just install.
- **Delete bash after Python lands** (no long-term coexistence — avoids drift).
  Deletion is the LAST step, only after the Python set passes the Linux smoke
  test and at least one real Windows run. Until then bash stays as the safety net.

## Still to verify on a live Windows install (not blocking the port)

- Antigravity Windows MCP path (`config\` vs `antigravity\`).
- Cursor `~/.cursor/skills` global skill dir (inferred, medium confidence).
```
