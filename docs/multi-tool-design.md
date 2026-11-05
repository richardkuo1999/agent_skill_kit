# Multi-tool support design

Design notes for extending the kit beyond Kiro and Antigravity. This records
decisions and verified paths; it is the spec the tool-table refactor will follow.
No code implements the new tools yet.

## Tool support matrix

Verified against each tool's official docs (2026-11). "Confidence" flags anything
taken from secondary sources.

### Skills

All supported tools use the `<name>/SKILL.md` Agent Skills standard, so skills
install by symlink; only the path differs.

| tool | global skill dir | project skill dir | confidence |
|------|------------------|-------------------|------------|
| Kiro | `~/.kiro/skills` | `.kiro/skills` | shipped |
| KiroCrew | `~/.kiro/crew/skills` | (none) | shipped (skill only; rules share Kiro's ~/.kiro/steering) |
| Antigravity | `~/.gemini/config/skills` | `.agents/skills` | shipped |
| Claude Code | `~/.claude/skills` | `.claude/skills` | shipped |
| Codex | `~/.codex/skills` | `.agents/skills` | shipped |
| Cursor | `~/.cursor/skills` | `.cursor/skills` | shipped |
| Copilot | — | — | no skill concept |

`.agents/skills/` is shared by Antigravity, Codex and Cursor. A project-level
install there is read by all three; the refactor must not install it once per tool.
Cursor also reads `.claude/skills` and `.codex/skills` for compatibility.

### Rules — two classes

**A class: one folder, many files, per-file frontmatter** (same model the kit
already uses). Installs by format conversion, one file per rule.

| tool | global rule dir | project rule dir | frontmatter |
|------|-----------------|------------------|-------------|
| Kiro | `~/.kiro/steering` | `.kiro/steering` | `inclusion` |
| Antigravity | `~/.gemini/config/rules` | `.agents/rules` | `trigger` |
| Cursor | (no file-based global; User Rules live in the UI) | `.cursor/rules/*.mdc` | `alwaysApply` / `globs` / `description` | shipped |

Cursor global rules are intentionally not supported (decided 2026-11):
- Cursor's global "User Rules" live in `globalStorage/state.vscdb` (SQLite) and
  sync to the Cursor account. There is no official file interface; writing the DB
  is undocumented, sync-conflicting, and the file can be hundreds of GB — out of
  bounds for this kit's "official interfaces only, no hacks" rule.
- `~/.cursor/rules/` as a global location appears only in community posts; the
  official docs define `.cursor/rules` as project-scoped only. Not relied on.
- A home-dir `AGENTS.md` is not documented as global either.
So Cursor installs project rules (`.cursor/rules/*.mdc`) only; a global Cursor
rule is set by the user by hand in Settings → Rules → User Rules. A possible
"pseudo-global via per-project AGENTS.md" is noted under the B-class merge work,
not built.

**B class: a single file, no per-rule frontmatter.** Needs the merge strategy below.

| tool | global file | project file |
|------|-------------|--------------|
| Claude Code | `~/.claude/CLAUDE.md` | `./CLAUDE.md` |
| Codex | `~/.codex/AGENTS.md` | `./AGENTS.md` (root→cwd) |
| Copilot | — | `.github/copilot-instructions.md` (+ `.github/instructions/*.instructions.md` with `applyTo`) |

## kit_load mapping across tools

| kit_load | Kiro | Antigravity | Cursor .mdc | Claude/Codex single file | Copilot |
|----------|------|-------------|-------------|--------------------------|---------|
| always | always | always_on | `alwaysApply: true` | merged into the file | merged into copilot-instructions.md |
| glob | fileMatch | glob | `globs:` | skipped (report) | `.github/instructions/*.instructions.md` with `applyTo:` |
| manual | manual | manual | both empty (manual @) | skipped (report) | skipped (report) |
| model | manual (warn) | model_decision | `description:` only | skipped (report) | skipped (report) |

## B-class rule merge strategy (decided: strategy 3, "split")

For a single-file tool, route each rule by its `kit_load`:

- `always` → append the rule body into the tool's single file (CLAUDE.md / AGENTS.md / copilot-instructions.md).
- `glob` → Copilot only: write `.github/instructions/<name>.instructions.md` with `applyTo:` from the rule's globs. Claude/Codex have nowhere for it → skip.
- `manual` / `model` → skip (a single file cannot load selectively).
- Every skipped rule is reported per tool: which rule, which tool, why.

Only rules whose `kit_targets` include the tool are considered.

### Three mechanics for the merged file

1. **Block markers per rule.** Each merged rule body is preceded by a heading
   that names its source, e.g. `## [kit rule] ponytail`, so the file stays
   readable and traceable.
2. **Hand-written content protection.** The user often writes their own content
   in CLAUDE.md etc. The kit manages only its own span, wrapped in a matched
   pair, e.g. `<!-- kit:start -->` … `<!-- kit:end -->`. A reinstall replaces
   only what is between the markers; anything the user wrote outside is left
   untouched. If the file exists and has no kit markers, append the kit block at
   the end rather than overwriting.
3. **Stable order.** Merge rules in a fixed order (by file name) so a reinstall
   produces a minimal diff.

## Tool-table refactor plan

Goal: the tool name and its paths are hardcoded in three scripts today
(`install-skill.sh`, `install-rule.sh`, `setup.sh`). Adding a tool means editing
three `case` blocks. The refactor moves every tool definition into one table so
adding a tool is one new row, not three edits.

### `config/tools.tsv` (new; the single list of install targets)

| column | meaning | example |
|--------|---------|---------|
| name | tool name used as the CLI target | `kiro` |
| skill_global | global skill dir (empty if the tool has no skills) | `~/.kiro/skills` |
| skill_project | project skill dir | `.kiro/skills` |
| rule_class | `A` (folder of files) or `B` (single file) | `A` |
| rule_global | A: global rule dir; B: global single file | `~/.kiro/steering` |
| rule_project | A: project rule dir; B: project single file | `.kiro/steering` |
| rule_fmt | name of the rule frontmatter converter in lib | `fmt_kiro` |
| doc_url | official doc page (the human-verification entry point) | https://… |

Direction note: `*-sources.tsv` / `*-selected.tsv` describe where content comes
FROM (upstream). `tools.tsv` describes where it installs TO (downstream). That is
why it lives in `config/`, not `upstream/`.

### `scripts/lib/tools.sh` (new; shared functions)

- `resolve_target <name>`: read `tools.tsv`, expand `all`, validate the name —
  replaces the three `case` blocks.
- `tool_field <name> <col>`: look up one column.
- Rule converters: `fmt_kiro`, `fmt_antigravity`, `fmt_cursor` (A class, one file
  per rule), and `merge_single_file` (B class: strategy-3 split, block markers,
  hand-written protection).

Adding an A-class tool = one `tools.tsv` row + one `fmt_*`. Adding a B-class tool
= one row, reusing `merge_single_file`.

### Scripts after the refactor

- `install-skill.sh`: paths come from `tool_field`; symlink logic unchanged.
- `install-rule.sh`: branch on `rule_class` — A calls its `fmt_*` one file per
  rule (current behavior); B calls `merge_single_file`.
- `setup.sh`: the arg check asks `tools.tsv` whether a name exists.
- `check-updates.sh`, `diff-upstream.sh`, `import-*.sh`: unchanged (they handle
  upstream, not the install target).

### Landing order (each step independently testable)

1. Refactor only; behavior unchanged (still kiro + antigravity). Run existing
   tests to confirm equivalence.
2. Add Cursor (A class, same model as current tools — lowest risk). DONE. Needed
   two generalizations: marker moved from "line 1" to "anywhere, grep-matched"
   (Cursor .mdc must start with ---, so its marker is an HTML comment after the
   frontmatter), and `install_dir` now checks the scope actually in use (Cursor
   has project rules but no file-based global rules). A `rule_ext` column lets
   Cursor write .mdc while others write .md.
3. Add Claude Code and Codex skills (symlink, nearly free). DONE. Two tools.tsv
   rows; both are rule_class B, so their rules SKIP until step 4. Codex project
   skills share `.agents/skills` with Antigravity — `setup all --workspace` links
   it twice (idempotent `ln -sfn`, harmless; a dedupe is a possible optimization).
4. Add B-class rule merge (`merge_single_file`) last; test it in isolation. DONE.
   install-rule.sh branches on rule_class: A keeps the per-file loop; B collects
   every `always` rule for the tool, wraps each in `## [kit rule] <title>`, and
   merges the lot into the single file (CLAUDE.md / AGENTS.md) between
   `<!-- kit:start ... -->` and `<!-- kit:end -->`. glob/manual/model are skipped
   with a reason. The kit block always sits at the end of the file; a reinstall
   removes the old block (markers inclusive) with sed, keeps all other text (the
   user's), and re-appends a fresh block — so user content is never lost, though
   content that was after the old block moves to before the new one. Verified:
   fresh file, reinstall (no block growth), hand-written text before and after
   the block preserved, glob/manual/model and kit_targets filtering, Codex
   AGENTS.md, and setup all across five tools.

### Refactor risks

- `merge_single_file` hand-written protection is the error-prone part: an existing
  CLAUDE.md with the user's own text must have only the `<!-- kit:start -->` …
  `<!-- kit:end -->` span replaced. Needs its own test (seed a file with hand text,
  install twice, assert only the marked span changed).
- `~` expansion: paths stored as `~/.kiro/skills` must expand to `$HOME` and still
  honor `--workspace`.
- Shared `.agents/` path (Antigravity/Codex/Cursor project scope): installing `all`
  into one workspace would link the same dir several times. Dedupe by real path.
- Build server bash is old; avoid associative arrays, keep the tsv + awk style.

## Execution model: script does the deterministic, agent does the judgment

This kit is run by an AI agent that executes the scripts, not by a human at a raw
shell. That splits the work cleanly, and the split is a design rule:

- **Scripts are the deterministic skeleton.** Mechanical, repeatable, no-judgment
  work only: copy files, symlink, apply a frontmatter template, read a table.
  Scripts must be testable, runnable offline, and produce the same result every
  run. Installation is destructive (symlinks, overwriting rule files), so it must
  not depend on a fresh agent judgment each time.
- **The agent does the judgment, guided by a skill.** Reading a vendor doc to find
  a path, deciding whether an upstream change should be adopted, resolving a merge
  conflict by intent, converting an unseen frontmatter format — these need
  understanding, so a skill (like `upstream-sync`) walks the agent through them.

Rule of thumb: if a step has one correct output given its input, it belongs in a
script. If it needs reading, understanding, or a choice, it belongs in a skill the
agent follows. The agent's value is judgment, not moving files; a script that
reliably moves files is safer than the agent doing `ln -s` by hand.

## Keeping tools.tsv current when vendors change paths

`tools.tsv` paths come from each vendor's docs — prose on web pages, not a
structured, versioned, queryable API. A pure script can only scrape-and-guess,
which is fragile and a wrong path is worse than a stale one. But under the
execution model above, the agent reads the docs and judges, so this is a skill,
not a scraper.

### `tools-sync` skill (IMPLEMENTED — skills/tools-sync/SKILL.md)

Reads the `doc_url` column of both config/tools.tsv and config/mcp-targets.tsv
(a doc_url column was added to mcp-targets.tsv for this), fetches each vendor
page, compares documented paths with the tables, and edits one cell per
confirmed change after the user approves. Unreachable or JS-only pages are
reported UNVERIFIED, never guessed.

Symmetric with `upstream-sync`, but for the install-target table:

1. For each row in `config/tools.tsv`, the agent fetches `doc_url` with its own
   web tool and reads the current skill/rule paths out of the prose.
2. It compares what the doc says now against the paths recorded in `tools.tsv`.
3. For any path that changed, it tells the user which tool, old vs new path, and
   the doc section it came from, then waits for the user's decision.
4. On approval it updates that row. It never edits paths silently.

This beats a `doc_hash` diff: the agent judges whether a path actually moved
instead of flagging every unrelated page edit. No `check-tools.sh` scraper is
built. `tools.tsv` still carries a `doc_url` column as the skill's entry point.

The same principle already governs skills/rules: `check-updates.sh` (script) finds
what changed; `upstream-sync` (skill) has the agent judge whether to adopt it.

## Open decisions (not yet made)

- Which tools to support first (all six, or a subset).
- Whether to deduplicate the shared `.agents/` path across Antigravity/Codex/Cursor
  at project scope, or let the user pick one owner.
- Codex global skill path `~/.codex/skills` is from secondary docs; verify on a
  real Codex install before relying on it.

(Resolved: tools.tsv updates are handled by the `tools-sync` skill with the agent
reading the docs, not a `check-tools.sh` hash scraper. See the execution-model
section.)
