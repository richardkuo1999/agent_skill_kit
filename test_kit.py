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


def _rc(sandbox, home, *args):
    """Run and return the exit code (for asserting a command refuses something)."""
    env = dict(os.environ, HOME=str(home))
    return subprocess.run([PY, str(sandbox / "kit.py")] + list(args),
                          cwd=str(sandbox), env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def _out(sandbox, home, *args):
    """Run and return stdout (for asserting on a report's text)."""
    env = dict(os.environ, HOME=str(home))
    return subprocess.run([PY, str(sandbox / "kit.py")] + list(args),
                          cwd=str(sandbox), env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL).stdout.decode("utf-8", "ignore")


def main():
    try:
        import toml  # noqa: F401  (the Codex MCP checks write TOML)
    except ImportError:
        print("test_kit.py needs the 'toml' package for the Codex MCP checks: pip install toml")
        return 2
    work = Path(tempfile.mkdtemp())
    try:
        sb = work / "kit"
        def _ignore(d, names):  # keep the user's own MCP defs/secrets out of the sandbox
            skip = {".git", "__pycache__"}
            if Path(d) == KIT / "config":
                skip |= {"mcp", "secrets.env"}
            return [n for n in names if n in skip]
        shutil.copytree(KIT, sb, ignore=_ignore)
        # fake content
        (sb / "skills" / "smoke-skill").mkdir(parents=True)
        (sb / "skills" / "smoke-skill" / "SKILL.md").write_text("# smoke\n")
        # test profile: installs smoke-skill and routes the example playbook
        (sb / "skills" / "profiles" / "smoke.txt").write_text(
            "[skills]\nsmoke-skill\n[playbooks]\n修缺陷 -> fix-bug.md\n")
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
        run(sb, home, "install", "all", "--profile", "smoke")

        # skills: every tool with a skill dir
        for rel in (".kiro/skills/smoke-skill", ".gemini/config/skills/smoke-skill",
                    ".cursor/skills/smoke-skill", ".claude/skills/smoke-skill",
                    ".codex/skills/smoke-skill", ".kiro/crew/skills/smoke-skill"):
            p = home / rel
            check(p.exists() or p.is_symlink(), "skill present: " + rel)

        # rules A-class frontmatter. Front-matter must be line 1 (a leading
        # marker comment makes Kiro/Antigravity ignore it and default to always).
        kiro_rule = (home / ".kiro/steering/smoke-always.md").read_text()
        ag_rule = (home / ".gemini/config/rules/smoke-always.md").read_text()
        check("inclusion: always" in kiro_rule, "kiro rule inclusion")
        check("trigger: always_on" in ag_rule, "antigravity rule trigger")
        check(kiro_rule.startswith("---"), "kiro rule frontmatter at line 1")
        check(ag_rule.startswith("---"), "antigravity rule frontmatter at line 1")

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
        run(sb, home, "install", "all", "--profile", "smoke")
        after = (home / ".claude/CLAUDE.md").read_text().count("kit:start")
        check(before == 1 and after == 1, "claude block idempotent")
        servers = json.loads((home / ".kiro/settings/mcp.json").read_text()).get("mcpServers", {})
        check(list(servers).count("smoke") == 1 and len(servers) == 1, "kiro mcp idempotent")

        # project scope
        proj = work / "proj"
        run(sb, home, "install", "cursor", "--profile", "smoke", workspace=proj)
        check((proj / ".cursor/rules/smoke-always.mdc").exists(), "cursor project rule")

        # no secret leaked into tracked dirs
        leaked = any("smoke-secret-value" in f.read_text(errors="ignore")
                     for d in ("skills", "rules")
                     for f in (sb / d).rglob("*") if f.is_file())
        check(not leaked, "no secret leaked into tracked dirs")

        # profile: pilot always installs even though smoke.txt omits it
        check((home / ".kiro/skills/pilot/SKILL.md").exists(), "pilot always installed")
        # profile: a mechanism skill NOT in the profile is NOT installed
        check(not (home / ".kiro/skills/kitpilot").exists() and
              not (home / ".kiro/skills/curate").exists(),
              "mechanism skills excluded")
        # profile + --copy: pilot routing table filled from [playbooks]
        home2 = work / "home2"
        run(sb, home2, "install", "kiro", "--profile", "smoke", "--copy")
        pilot_md = (home2 / ".kiro/skills/pilot/SKILL.md").read_text()
        between = pilot_md.split("pilot:start", 1)[1].split("pilot:end", 1)[0]
        check("playbooks/fix-bug.md" in between, "pilot routes filled (copy mode)")

        # manifest: skeleton with deterministic tables + flow placeholder
        run(sb, home2, "manifest", "--profile", "smoke")
        mani = (sb / "skills/pilot/MANIFEST.md").read_text()
        check("fix-bug" in mani and "<!-- flow:" in mani, "manifest playbook + flow placeholder")
        check("smoke-skill" in mani, "manifest lists profile skill")

        # _clean_desc: list-skills description tidying
        sys.path.insert(0, str(sb))
        import kit as _kit
        cd = _kit._clean_desc
        check(cd(">-") == "(multi-line; see SKILL.md)", "clean_desc flags block scalar")
        check(cd('say \\"hi\\"') == 'say "hi"', "clean_desc unescapes quotes")
        check(cd("a" * 200).endswith("..."), "clean_desc truncates long")
        check(cd("plain one-liner") == "plain one-liner", "clean_desc keeps plain")

        # import-mcp: write a definition (--json mode, args start with '-'),
        # then confirm install picks it up
        run(sb, home, "import-mcp", "fromcli", "--json",
            '{"command":"npx","args":["-y","fromcli-server"],'
            '"env":{"T":"${KIT_SECRET:SMOKE_TOKEN}"}}')
        imp = json.loads((sb / "config/mcp/fromcli.json").read_text())
        check(imp.get("command") == "npx" and imp.get("transport") == "stdio",
              "import-mcp wrote stdio server")
        check(imp.get("env", {}).get("T") == "${KIT_SECRET:SMOKE_TOKEN}",
              "import-mcp kept secret ref")
        run(sb, home, "install", "kiro", "--profile", "smoke", "--only", "mcp")
        km = json.loads((home / ".kiro/settings/mcp.json").read_text()).get("mcpServers", {})
        check("fromcli" in km, "import-mcp server installs")
        # import-mcp refuses clobber without --force
        rc = _rc(sb, home, "import-mcp", "fromcli", "--url", "https://x")
        check(rc != 0, "import-mcp refuses existing without --force")

        # uninstall: reverse of install for one tool
        run(sb, home, "uninstall", "kiro", "--profile", "smoke")
        check(not (home / ".kiro/skills/smoke-skill").exists()
              and not (home / ".kiro/skills/smoke-skill").is_symlink(),
              "uninstall removed skill")
        check(not (home / ".kiro/skills/pilot").exists()
              and not (home / ".kiro/skills/pilot").is_symlink(),
              "uninstall removed pilot")
        check(not (home / ".kiro/steering/smoke-always.md").exists(),
              "uninstall removed A-class rule")
        mp = home / ".kiro/settings/mcp.json"
        km2 = json.loads(mp.read_text()).get("mcpServers", {}) if mp.exists() else {}
        check("smoke" not in km2 and "fromcli" not in km2, "uninstall removed mcp servers")
        check(not mp.exists() and not (home / ".kiro/steering").exists()
              and not (home / ".kiro/skills").exists(),
              "uninstall removed emptied mcp file and empty dirs")
        # a non-empty file/dir is kept
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps({"mcpServers": {"mine": {"command": "x"}}, "other": 1}))
        run(sb, home, "install", "kiro", "--profile", "smoke", "--only", "mcp")
        run(sb, home, "uninstall", "kiro", "--profile", "smoke", "--only", "mcp")
        kept = json.loads(mp.read_text())
        check(kept.get("other") == 1 and "mine" in kept.get("mcpServers", {}),
              "uninstall keeps user's own servers and fields")
        # other tools untouched by a single-tool uninstall
        check((home / ".cursor/skills/smoke-skill").exists()
              or (home / ".cursor/skills/smoke-skill").is_symlink(),
              "uninstall left other tool alone")

        # U4/U8/U9: copy marker + shared dir
        proj = sb / "proj"; proj.mkdir()
        hw = proj / ".agents/skills/smoke-skill"; hw.mkdir(parents=True)
        (hw / "SKILL.md").write_text("hand")
        run(sb, home, "install", "codex", "--workspace", str(proj), "--profile", "smoke", "--only", "skills", "--copy")
        check((hw / "SKILL.md").read_text() == "hand" and not (hw / ".kit-installed").exists(),
              "--copy does not overwrite hand-written skill")
        run(sb, home, "install", "codex", "--workspace", str(proj), "--profile", "smoke", "--only", "skills", "--copy")
        check((proj / ".agents/skills/pilot/.kit-installed").is_file(), "copy writes marker")
        run(sb, home, "uninstall", "codex", "antigravity", "--workspace", str(proj), "--profile", "smoke", "--only", "skills")
        check((hw / "SKILL.md").exists(), "uninstall keeps unmarked hand-written skill")
        check(not (proj / ".agents/skills/pilot").exists(), "uninstall removed marked copy")
        run(sb, home, "install", "codex", "--workspace", str(proj), "--profile", "smoke", "--only", "skills", "--copy")
        run(sb, home, "uninstall", "codex", "--workspace", str(proj), "--profile", "smoke", "--only", "skills")
        check((proj / ".agents/skills/pilot").exists(), "uninstall skips dir shared with antigravity")
        run(sb, home, "uninstall", "codex", "--workspace", str(proj), "--profile", "smoke", "--only", "skills", "--force")
        check(not (proj / ".agents/skills/pilot").exists(), "--force removes shared dir")

        # N2/U18: uninstall never removes the workspace root; cleans parents it emptied
        pw = sb / "projN2"; pw.mkdir()
        run(sb, home, "install", "codex", "--workspace", str(pw), "--profile", "smoke", "--only", "skills")
        run(sb, home, "uninstall", "codex", "antigravity", "--workspace", str(pw), "--only", "skills")
        check(pw.is_dir() and not (pw / ".agents").exists(),
              "uninstall keeps workspace root, removes emptied .agents")
        # missing 'toml' package: clear error, rc != 0, no traceback
        env_nt = dict(os.environ, HOME=str(home))
        r_nt = subprocess.run(
            [PY, "-c", "import sys; sys.modules['toml']=None; sys.modules['tomllib']=None; "
             "import kit; sys.exit(kit.main(['install','codex','--only','mcp','--profile','smoke']))"],
            cwd=str(sb), env=env_nt, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out_nt = r_nt.stdout.decode("utf-8", "ignore")
        check(r_nt.returncode != 0 and "pip install toml" in out_nt and "Traceback" not in out_nt,
              "missing toml package gives a clear error")
        # M1/M2: without the toml package, uninstall exits non-zero and list prints no traceback
        pt = sb / "projM1"; pt.mkdir()
        run(sb, home, "install", "codex", "--workspace", str(pt), "--profile", "smoke", "--only", "mcp")
        def _no_toml(*argv):
            r = subprocess.run(
                [PY, "-c", "import sys; sys.modules['toml']=None; sys.modules['tomllib']=None; "
                 "import kit; sys.exit(kit.main(%r))" % (list(argv),)],
                cwd=str(sb), env=dict(os.environ, HOME=str(home)),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            return r.returncode, r.stdout.decode("utf-8", "ignore")
        rc_u, out_u = _no_toml("uninstall", "codex", "--workspace", str(pt), "--only", "mcp")
        check(rc_u != 0 and "pip install toml" in out_u, "uninstall without toml exits non-zero (M1)")
        rc_l, out_l = _no_toml("list", "codex", "--workspace", str(pt))
        check("Traceback" not in out_l and "pip install toml" in out_l, "list without toml has no traceback (M2)")
        # M4/M5/M6: link ownership in list, KEEP summary, pilot kept while other kit skills remain
        p6 = sb / "proj6"; sd6 = p6 / ".cursor/skills"; sd6.mkdir(parents=True)
        (sb / "skills/other-skill").mkdir(); (sb / "skills/other-skill/SKILL.md").write_text("o")
        (sd6 / "mine").mkdir(); (sd6 / "mine/SKILL.md").write_text("hand")
        outside6 = sb / "outside6"; outside6.mkdir()
        (sd6 / "foreign").symlink_to(outside6, target_is_directory=True)
        run(sb, home, "install", "cursor", "--workspace", str(p6), "--profile", "smoke", "--only", "skills")
        (sd6 / "other-skill").symlink_to(sb / "skills/other-skill", target_is_directory=True)
        lst = _out(sb, home, "list", "cursor", "--workspace", str(p6))
        check("foreign" in lst and "unmanaged (link points outside the kit)" in lst,
              "list marks a link outside the kit as unmanaged (M4)")
        run(sb, home, "uninstall", "cursor", "--workspace", str(p6), "--profile", "smoke", "--only", "skills")
        check(not (sd6 / "smoke-skill").is_symlink() and (sd6 / "pilot").is_symlink()
              and (sd6 / "other-skill").is_symlink(),
              "--profile keeps pilot while other kit skills remain (M6)")
        out6 = _out(sb, home, "uninstall", "cursor", "--workspace", str(p6), "--only", "skills")
        check(not (sd6 / "pilot").is_symlink() and not (sd6 / "other-skill").is_symlink()
              and "mine" in out6 and "KEEP" in out6,
              "no --profile removes all kit skills and reports kept ones (M5)")
        shutil.rmtree(sb / "skills/other-skill")
        # N6: a server with a missing secret is skipped; the others still install
        nosec = sb / "config/mcp/aaa-nosecret.json"
        nosec.write_text(json.dumps({"command": "x", "env": {"T": "${KIT_SECRET:NOPE_X}"}}))
        pm = sb / "projN6"; pm.mkdir()
        rc6 = _rc(sb, home, "install", "kiro", "--workspace", str(pm), "--profile", "smoke", "--only", "mcp")
        srv6 = json.loads((pm / ".kiro/settings/mcp.json").read_text()).get("mcpServers", {})
        nosec.unlink()
        check(rc6 != 0 and "smoke" in srv6 and "aaa-nosecret" not in srv6,
              "missing secret skips only that server, rc!=0")
        # N5: list marks an unmarked dir as unmanaged
        pl = sb / "projN5"; (pl / ".cursor/skills/hand").mkdir(parents=True)
        (pl / ".cursor/skills/hand/SKILL.md").write_text("x")
        check("unmanaged" in _out(sb, home, "list", "cursor", "--workspace", str(pl)),
              "list marks hand-written skill as unmanaged")
        # N7: install warns about a playbook file that does not exist
        (sb / "skills/profiles/n7.txt").write_text("[skills]\n\n[playbooks]\nx -> nope.md\n")
        r7 = subprocess.run([PY, str(sb / "kit.py"), "install", "cursor", "--workspace", str(pl),
                             "--profile", "n7", "--only", "skills"], cwd=str(sb),
                            env=dict(os.environ, HOME=str(home)), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
        check("nope.md" in r7.stdout.decode("utf-8", "ignore"),
              "install warns on missing playbook file")

        # U9: no --profile -> scan; removes every kit skill, keeps hand-written + foreign links
        p9 = sb / "proj9"; sd = p9 / ".cursor/skills"; sd.mkdir(parents=True)
        (sd / "mine").mkdir(); (sd / "mine/SKILL.md").write_text("hand")
        outside = sb / "outside"; outside.mkdir()
        (sd / "foreign").symlink_to(outside, target_is_directory=True)
        run(sb, home, "install", "cursor", "--workspace", str(p9), "--profile", "smoke", "--only", "skills")
        check((sd / "smoke-skill").is_symlink() and (sd / "pilot").is_symlink(), "U9 setup installed")
        run(sb, home, "uninstall", "cursor", "--workspace", str(p9), "--only", "skills")
        check(not (sd / "smoke-skill").is_symlink() and not (sd / "pilot").is_symlink(),
              "uninstall without --profile removed all kit skills")
        check((sd / "mine/SKILL.md").exists() and (sd / "foreign").is_symlink(),
              "uninstall kept hand-written skill and foreign symlink")

        # uninstall B-class: strips kit block, keeps user text
        claude_p = home / ".claude/CLAUDE.md"
        claude_p.write_text("my notes\n\n" + claude_p.read_text(), encoding="utf-8")
        run(sb, home, "uninstall", "claude", "--profile", "smoke", "--only", "rules")
        after_un = claude_p.read_text()
        check("kit:start" not in after_un and "my notes" in after_un,
              "uninstall stripped claude block, kept user text")

        # uninstall leaves hand-written rules alone
        hand = home / ".kiro/steering/hand.md"
        hand.parent.mkdir(parents=True, exist_ok=True)
        hand.write_text("hand-written, no marker\n")
        run(sb, home, "install", "kiro", "--profile", "smoke", "--only", "rules")
        run(sb, home, "uninstall", "kiro", "--profile", "smoke", "--only", "rules")
        check(hand.exists(), "uninstall kept hand-written rule")

        # profiles / list / status run and report
        check("smoke" in _out(sb, home, "profiles"), "profiles lists smoke")
        st = _out(sb, home, "status")
        check("smoke-skill" in st and "smoke" in st, "status shows local content")

    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    print("SMOKE: {} passed, {} failed".format(_pass[0], _fail[0]))
    return 1 if _fail[0] else 0


if __name__ == "__main__":
    raise SystemExit(main())
