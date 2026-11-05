# config/mcp/

One MCP server per `<name>.json`, tool-agnostic. `python kit.py install` converts each
into the target tool's shape (JSON `mcpServers` or TOML `[mcp_servers.*]`) and
merges it into that tool's config file, preserving the user's other servers.

Empty of real servers by default. Add your own `<name>.json`.

## Source format

```json
{
  "command": "npx",
  "args": ["-y", "some-mcp-server"],
  "env": { "API_TOKEN": "${KIT_SECRET:SOME_TOKEN}" },
  "targets": "all",
  "transport": "stdio"
}
```

- `command` / `args` / `env`: standard stdio-server fields.
- `url` (instead of command/args): a remote server. `transport` then `http`.
- `env` values may reference secrets as `${KIT_SECRET:NAME}`; the real value
  comes from `config/secrets.env` at install time (never committed). A missing
  key makes install fail loudly.
- `targets`: `all`, or a comma list of tool names (e.g. `kiro,cursor`).
- `transport`: `stdio` (default) or `http`. Kept kit-side; not every tool writes
  it the same way.

The `targets` and `transport` keys are kit metadata and are stripped before the
definition is written into a tool's config.
