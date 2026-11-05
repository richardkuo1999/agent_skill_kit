# MCP support (step 5) and making the repo public

Design notes. IMPLEMENTED — see install-mcp.sh, config/mcp-targets.tsv,
config/mcp/. Two linked goals, both done:
1. Install one MCP-server definition across all five tools.
2. Keep secrets out of the repo so it can be published publicly.

Implementation summary: `config/mcp/<name>.json` holds one tool-agnostic server
(command/args/env/url, plus kit metadata `targets`). `install-mcp.sh` resolves
`${KIT_SECRET:NAME}` from `config/secrets.env` (fail-loud on a missing key),
strips kit metadata, and merges the server under each tool's container key via
`merge_mcp_json` (jq, for Kiro/Antigravity/Claude/Cursor) or `merge_mcp_toml`
(python `toml`, for Codex) — preserving every other key in the user's config.
Idempotent on reinstall; TOML path skips with a notice if the `toml` package is
absent. Wired into setup.sh as a third installer.

## MCP config locations (verified 2026-11)

MCP servers are configured per tool, in different files, formats and keys.

| tool | user/global file | project file | format | top-level key |
|------|------------------|--------------|--------|---------------|
| Kiro | `~/.kiro/settings/mcp.json` | `.kiro/settings/mcp.json` | JSON | `mcpServers` |
| Antigravity | `~/.gemini/config/mcp_config.json` (also seen `~/.gemini/antigravity/mcp_config.json`) | (app-managed) | JSON | `mcpServers` |
| Claude Code | `~/.claude.json` (user) | `.mcp.json` (project) | JSON | `mcpServers` |
| Cursor | `~/.cursor/mcp.json` | `.cursor/mcp.json` | JSON | `mcpServers` |
| Codex | `~/.codex/config.toml` | `.codex/config.toml` | TOML | `[mcp_servers.<name>]` |

Confidence: JSON `mcpServers` for Kiro/Cursor/Claude/Antigravity is high (official or
multiple sources). Codex TOML is high (official). Antigravity's exact global path
has two reported variants — verify on a real install before writing there.

Why MCP is harder than skills/rules:
- Four tools use JSON, one uses TOML — two serializers, different key shape.
- The file is NOT MCP-only: `~/.claude.json` and Codex `config.toml` hold other
  settings too. The kit must MERGE its servers into the file's `mcpServers` /
  `[mcp_servers.*]` key and preserve everything else — not overwrite the file.
- Remote-server fields differ (Cursor bare `url`; Claude `"type":"http"`).
- Servers carry secrets (API tokens in `env`). That drives the secrets design below.

## Kit MCP source format (planned)

One server per entry in a kit-owned table/dir, tool-agnostic, e.g.
`config/mcp/<name>.json`:

```json
{
  "command": "npx",
  "args": ["-y", "some-mcp-server"],
  "env": { "API_TOKEN": "${KIT_SECRET:SOME_TOKEN}" },
  "targets": "all",
  "transport": "stdio"
}
```

`install-mcp.sh` would, per tool: read these entries, convert to the tool's shape
(JSON `mcpServers` or TOML `[mcp_servers.*]`), resolve `${KIT_SECRET:NAME}` from
the secrets file (below), and MERGE into the tool's config file under its own
managed span/key, preserving the user's other servers and settings.

JSON merge needs a real parser (jq), TOML needs a TOML tool. Availability on the
build server must be checked before committing to this. If a parser is missing,
step 5 is blocked, not hacked with sed.

## Secrets design — make the repo publishable

Rule: nothing secret is ever committed. The repo holds only references; real
values live in one gitignored file the scripts READ at install time.

### Layout

```
config/
  secrets.env            # REAL values. gitignored. never committed.
  secrets.env.example    # committed. same keys, placeholder values. a template.
```

- `secrets.env` is `KEY=value` lines (e.g. `SOME_TOKEN=sk-real-...`).
- Any kit source file references a secret as `${KIT_SECRET:SOME_TOKEN}`, never the
  value. install-mcp.sh substitutes from `secrets.env` at install time.
- A missing key: install fails loudly naming the key, and does NOT write a broken
  config. It never falls back to writing the literal `${KIT_SECRET:...}`.

### .gitignore

Add:
```
config/secrets.env
```
Keep `config/secrets.env.example` tracked as the template. Also scan the whole
repo once before going public (see checklist) — a secret could hide in a rule
body or an imported upstream file, not just in MCP env.

### Scope of the secrets file

It is not MCP-only. Any current or future kit content that needs a secret uses the
same `${KIT_SECRET:NAME}` + `secrets.env` mechanism. This is the one place secrets
enter the kit, which is what makes "publish the repo" safe to reason about.

## Going-public checklist (before the first public push)

- `config/secrets.env` is gitignored and was never committed (check `git log`).
- No secret in any committed file: grep the history, not just the worktree, for
  token-shaped strings and known key names.
- Imported upstream rules/skills carry no embedded credentials.
- Commit author email is the one you want public (already set to the GitHub one).
- A fresh clone + `./setup.sh <tool>` works with only `secrets.env.example`
  copied to `secrets.env` and filled in — i.e. the public repo is usable by
  someone who supplies their own secrets.

## Open decisions

- Is `jq` (and a TOML writer) available on the target machines? RESOLVED on the
  build server: jq 1.5 (JSON) and the Python `toml` 0.10.2 package (TOML, pinned
  in requirements.txt) are present; Python 3.6.9 has no stdlib tomllib, hence the
  third-party package. Caveat: jq 1.5 is old — install-mcp.sh must avoid 1.6+
  syntax. The `toml` package is NOT guaranteed on the user's OTHER machines (e.g.
  the home Antigravity box); Codex MCP install must detect `python3 -c 'import
  toml'` and fail loudly asking for `pip install -r requirements.txt` rather than
  hand-building TOML with sed.
- Antigravity global MCP path variant (`config/` vs `antigravity/`) — verify live.
- Whether MCP server definitions themselves (not just their secrets) are
  per-machine enough that some belong only in a gitignored overlay, not the repo.
- Should `tools.tsv` gain mcp_global / mcp_project / mcp_format columns, or does
  MCP get its own table? (Leaning: own table, because format is JSON-vs-TOML and
  the merge key differs — more than a path.)
- Naming pass deferred: once the MCP table shape is decided, review all config/
  and upstream/ file names together for consistency (sources/selected use a
  hyphen; tools.tsv is singular). `tools.tsv` stays as-is until then; do not
  rename it in isolation.
