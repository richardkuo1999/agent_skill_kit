#!/usr/bin/env python3
"""End-to-end smoke test for kit.py. Runs the full install flow in a throwaway
sandbox with fake skill/rule/MCP content, asserts each of the seven tools got
the right output, checks idempotence and project scope, cleans up. Tests the
MECHANISM, not real content. Pure Python; no bash.

Run:  python test_kit.py   (exit 0 = all passed)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent
PY = sys.executable
_pass = [0]
_fail = [0]


def ok(m):
    _pass[0] += 1
    print("ok   " + m)


def no(m):
    _fail[0] += 1
    print("FAIL " + m)


def check(cond, m):
    ok(m) if cond else no(m)


def run(sandbox, home, *args, workspace=None):
    env = dict(os.environ, HOME=str(home))
    cmd = [PY, str(sandbox / "kit.py")] + list(args)
    if workspace:
        cmd += ["--workspace", str(workspace)]
    subprocess.run(cmd, cwd=str(sandbox), env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    work = Path(tempfile.mkdtemp())
    try:
        sb = work / "kit"
        shutil.copytree(KIT, sb, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        # fake content
        (sb / "skills" / "smoke-skill").mkdir(parents=True)
        (sb / "skills" / "smoke-skill" / "SKILL.md").write_text("# smoke\n")
        (sb / "rules" / "smoke-always.md").write_text(
            "---\nkit_load: always\ntitle: Smoke Always\ndescription: d\n---\nalways body\n")
        (sb / "rules" / "smoke-glob.md").write_text(
            '---\nkit_load: glob\nglobs: "*.ts"\ndescription: d\n---\nglob body\n')
        (sb / "config" / "mcp").mkdir(parents=True, exist_ok=True)
        (sb / "config" / "mcp" / "smoke.json").write_text(
            '{"command":"npx","args":["-y","smoke"],'
            '"env":{"T":"${KIT_SECRET:SMOKE_TOKEN}"},"targets":"all"}\n')
        (sb / "config" / "secrets.env").write_text("SMOKE_TOKEN=smoke-secret-value\n")

        home = work / "home"
        run(sb, home, "install", "all")

        # skills: every tool with a skill dir
        for rel in (".kiro/skills/smoke-skill", ".gemini/config/skills/smoke-skill",
                    ".cursor/skills/smoke-skill", ".claude/skills/smoke-skill",
                    ".codex/skills/smoke-skill", ".kiro/crew/skills/smoke-skill"):
            p = home / rel
            check(p.exists() or p.is_symlink(), "skill present: " + rel)

        # rules A-class frontmatter
        check("inclusion: always" in (home / ".kiro/steering/smoke-always.md").read_text(),
              "kiro rule inclusion")
        check("trigger: always_on" in (home / ".gemini/config/rules/smoke-always.md").read_text(),
              "antigravity rule trigger")

        # rules B-class merge: always in, glob out
        claude = (home / ".claude/CLAUDE.md").read_text()
        check("kit:start" in claude, "claude merged block")
        check("Smoke Always" in claude, "claude always rule")
        check("glob body" not in claude, "claude excluded glob rule")
        check("kit:start" in (home / ".codex/AGENTS.md").read_text(), "codex merged block")

        # MCP: JSON merge + secret substitution; TOML merge
        kiro_mcp = (home / ".kiro/settings/mcp.json").read_text()
        check('"smoke"' in kiro_mcp, "kiro mcp server")
        check("smoke-secret-value" in kiro_mcp, "kiro mcp secret substituted")
        check(json.loads(kiro_mcp).get("mcpServers", {}).get("smoke") is not None,
              "kiro mcp valid json")
        check("mcp_servers.smoke" in (home / ".codex/config.toml").read_text(),
              "codex mcp toml")

        # idempotence: reinstall, counts must not grow
        before = (home / ".claude/CLAUDE.md").read_text().count("kit:start")
        run(sb, home, "install", "all")
        after = (home / ".claude/CLAUDE.md").read_text().count("kit:start")
        check(before == 1 and after == 1, "claude block idempotent")
        servers = json.loads((home / ".kiro/settings/mcp.json").read_text()).get("mcpServers", {})
        check(list(servers).count("smoke") == 1 and len(servers) == 1, "kiro mcp idempotent")

        # project scope
        proj = work / "proj"
        run(sb, home, "install", "cursor", workspace=proj)
        check((proj / ".cursor/rules/smoke-always.mdc").exists(), "cursor project rule")

        # no secret leaked into tracked dirs
        leaked = any("smoke-secret-value" in f.read_text(errors="ignore")
                     for d in ("skills", "rules")
                     for f in (sb / d).rglob("*") if f.is_file())
        check(not leaked, "no secret leaked into tracked dirs")

        # _clean_desc: list-skills description tidying
        sys.path.insert(0, str(sb))
        import kit as _kit
        cd = _kit._clean_desc
        check(cd(">-") == "(multi-line; see SKILL.md)", "clean_desc flags block scalar")
        check(cd('say \\"hi\\"') == 'say "hi"', "clean_desc unescapes quotes")
        check(cd("a" * 200).endswith("..."), "clean_desc truncates long")
        check(cd("plain one-liner") == "plain one-liner", "clean_desc keeps plain")

    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    print("SMOKE: {} passed, {} failed".format(_pass[0], _fail[0]))
    return 1 if _fail[0] else 0


if __name__ == "__main__":
    raise SystemExit(main())
