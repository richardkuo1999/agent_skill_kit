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
| install-mcp.sh | 93 | install.py (mcp) | jq, python-toml (use stdlib json; tomllib/tomli) |
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

- `tomllib` is 3.11+. If colleagues may have < 3.11, bundle a `tomli` fallback
  for reading too. Pin decisions in requirements.txt. State the floor in README.

## Migration strategy (the part that protects correctness)

1. Verify Windows tool paths first (no code).
2. Port one piece at a time, each diffed against its bash output for equivalence
   on Linux (same method as the earlier refactor): install-skill → install-rule →
   install-mcp → import → check-updates → diff → check-public → setup.
3. Keep the bash scripts in place until the Python set passes the smoke test on
   Linux AND a real run on Windows. Only then decide whether to delete bash or
   keep both.
4. Port smoke-test.sh to test_kit.py last; it is the equivalence gate.

## Open decisions (for your review)

- One `kit.py` with subcommands, or several small scripts mirroring today's
  files? (Leaning: one file — easiest to ship and run on Windows.)
- Per-OS paths: RESOLVED — not needed (pathlib handles `~`; see above).
- Minimum Python version to support (drives the TOML-read fallback).
- Delete bash after Python lands, or keep both? (Keeping both doubles
  maintenance; deleting loses the Linux-proven baseline.)
- Do colleagues actually need import/check-updates (self-serve), or only install?
  This was assumed yes; confirm, because "only install" roughly halves the work.
```
