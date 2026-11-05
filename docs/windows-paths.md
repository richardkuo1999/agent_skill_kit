# Windows tool paths (verified 2026-11)

Core rule: on Windows `~` = `%USERPROFILE%` and `/` = `\`. For all five tools the
path STRUCTURE is the same as Unix, so Python's `pathlib.Path.home()` resolves the
`~/...` values in tools.tsv / mcp-targets.tsv correctly without a per-OS table.
Sources: each tool's official docs or community-verified posts.

## Global paths

| tool | skill | rule | MCP |
|------|-------|------|-----|
| Kiro | `%USERPROFILE%\.kiro\skills` | `%USERPROFILE%\.kiro\steering` | `%USERPROFILE%\.kiro\settings\mcp.json` |
| Antigravity | `%USERPROFILE%\.gemini\config\skills` | `%USERPROFILE%\.gemini\config\rules` | `%USERPROFILE%\.gemini\config\mcp_config.json` |
| Cursor | `%USERPROFILE%\.cursor\skills` | (no file-based global) | `%USERPROFILE%\.cursor\mcp.json` |
| Claude Code | `%USERPROFILE%\.claude\skills` | `%USERPROFILE%\.claude\CLAUDE.md` | `%USERPROFILE%\.claude.json` |
| Codex | `%USERPROFILE%\.codex\skills` | `%USERPROFILE%\.codex\AGENTS.md` | `%USERPROFILE%\.codex\config.toml` |

## Project paths

Identical to Unix (relative to the project root): `.kiro\...`, `.cursor\...`,
`.agents\...`, `.claude\...`, `CLAUDE.md`, `AGENTS.md`, `.mcp.json`,
`.codex\config.toml`. No OS difference.

## Symlink note

Path resolution is not the hard part; creating symlinks is. A regular Windows
user cannot create a symlink without admin or Developer Mode. install.py tries a
symlink and falls back to copying (with a notice), and `--copy` forces copy mode.
In copy mode a `git pull` that updates the kit requires re-running install.

## Still to verify on a live Windows install

- Antigravity MCP path: `config\mcp_config.json` vs an `antigravity\` variant.
- Cursor global skill dir `%USERPROFILE%\.cursor\skills` (inferred from the
  documented `.cursor` home dir; no Windows-specific doc names the skills subdir).

Source confidence: Claude Code states `~/.claude` → `%USERPROFILE%\.claude`
explicitly in its docs; the others are from vendor docs plus community posts.
Content was rephrased for compliance with licensing restrictions.
