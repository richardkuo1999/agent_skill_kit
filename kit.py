#!/usr/bin/env python3
"""agent_skill_kit — cross-platform installer/manager (Python 3.11+).

Single entry point with git-style subcommands: install / uninstall / list-skills /
import-skill / import-rule / import-mcp / check-updates / diff / manifest /
check-public / profiles / list / status / setup.

Usage:
  python kit.py install <tool>... [--workspace DIR] [--only skills|rules|mcp] [--copy] [--profile NAME]
    tool: any name in config/tools.tsv, or 'all'
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

import kitlib

COPY_MARK = ".kit-installed"  # written into every copied skill dir; uninstall only removes marked dirs


def _link_or_copy(src: Path, dest: Path, force_copy: bool) -> str:
    """Install one skill dir at dest. Returns 'link' or 'copy' (mode used).
    Default: try symlink, fall back to copy. --copy forces copy.
    An existing non-symlink dest is left alone (caller reports SKIP), unless it
    carries COPY_MARK (kit's own earlier copy) and --copy is given."""
    if dest.is_symlink() or dest.exists():
        if dest.is_symlink():
            dest.unlink()
        elif force_copy and (dest / COPY_MARK).is_file():
            shutil.rmtree(dest)
        else:
            return "skip"
    if not force_copy:
        try:
            os.symlink(src, dest, target_is_directory=True)
            return "link"
        except (OSError, NotImplementedError):
            pass  # no privilege (Windows) -> copy
    shutil.copytree(src, dest)
    (dest / COPY_MARK).write_text("installed by agent_skill_kit\n", encoding="utf-8")
    return "copy"


def _targets_tool(tgts: str, tool: str) -> bool:
    parts = [p.strip() for p in tgts.split(",")]
    return "all" in parts or tool in parts


def _install_rules(t, row, args, root, marker_line):
    # columns: name sg sp rule_class rule_global rule_project rule_fmt rule_ext doc_url
    rule_class = row[3]
    scope = row[5] if args.workspace else row[4]
    if scope == "-":
        print("SKIP {}: no rule support".format(t))
        return
    rule_srcs = sorted((root / "rules").glob("*.md"))
    rule_srcs = [s for s in rule_srcs if s.name != "README.md"]

    if rule_class == "A":
        fmt = kitlib.FMT[row[6]]
        ext = row[7] or "md"
        dest_dir = (Path(args.workspace) / scope) if args.workspace else kitlib.expand(scope)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src in rule_srcs:
            name = src.stem
            fm, body = kitlib.split_frontmatter(src.read_text(encoding="utf-8"))
            load = fm.get("kit_load", "always")
            tgts = fm.get("kit_targets", "all")
            if not _targets_tool(tgts, t):
                print("SKIP {}: {} (kit_targets={})".format(t, name, tgts)); continue
            title = fm.get("title", name)
            out = dest_dir / (name + "." + ext)
            if out.exists() and kitlib.KIT_MARKER not in out.read_text(encoding="utf-8"):
                print("SKIP {}: {} (hand-written, not overwriting)".format(t, name)); continue
            text, warn = fmt(marker_line, title, load, fm.get("description", ""),
                             fm.get("globs", ""), body)
            if warn:
                print("WARN {}: Kiro has no model_decision; installed as manual".format(warn),
                      file=sys.stderr)
            out.write_text(text, encoding="utf-8")
            print("OK   {}: {} ({})".format(t, name, load))

    elif rule_class == "B":
        dest = (Path(args.workspace) / scope) if args.workspace else kitlib.expand(scope)
        dest.parent.mkdir(parents=True, exist_ok=True)
        block_parts = []
        any_rule = 0
        for src in rule_srcs:
            name = src.stem
            fm, body = kitlib.split_frontmatter(src.read_text(encoding="utf-8"))
            load = fm.get("kit_load", "always")
            tgts = fm.get("kit_targets", "all")
            if not _targets_tool(tgts, t):
                print("SKIP {}: {} (kit_targets={})".format(t, name, tgts)); continue
            if load != "always":
                print("SKIP {}: {} (kit_load={}; single-file {} takes always only)"
                      .format(t, name, load, dest.name)); continue
            title = fm.get("title", name)
            block_parts.append("## [kit rule] {}\n\n{}\n".format(title, body.rstrip("\n")))
            any_rule += 1
            print("OK   {}: {} (merged)".format(t, name))
        if any_rule:
            kitlib.merge_single_file(dest, "\n".join(block_parts) + "\n")
        else:
            print("SKIP {}: no always-rules for this tool; {} untouched".format(t, dest.name))
    else:
        print("SKIP {}: unknown rule_class={}".format(t, rule_class))


def _install_mcp(targets, args, root):
    """Returns True on success, False if any server was skipped for a missing
    secret (so install can exit non-zero, per the README's 'errors out')."""
    import json
    mcp = kitlib.mcp_table()
    secrets = kitlib.load_secrets()
    srcs = sorted((root / "config" / "mcp").glob("*.json"))
    ok = True
    wrote_secret_to_project = False
    for t in dict.fromkeys(targets):
        if t not in mcp:
            continue  # tool has no MCP row; skip silently
        row = mcp[t]  # name mcp_global mcp_project fmt container doc_url
        fmt, container = row[3], row[4]
        if args.workspace:
            scope = row[2]
            if scope == "-":
                print("SKIP {}: no project MCP file".format(t)); continue
            dest = Path(args.workspace) / scope
        else:
            scope = row[1]
            if scope == "-":
                print("SKIP {}: no global MCP file".format(t)); continue
            dest = kitlib.expand(scope)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not srcs:
            print("SKIP {}: no servers in config/mcp/".format(t)); continue
        for src in srcs:
            name = src.stem
            defn = json.loads(src.read_text(encoding="utf-8"))
            tgts = defn.pop("targets", "all")
            # transport is kit metadata (see config/mcp/README.md), not a field
            # the tools' MCP config understands — strip it before writing.
            defn.pop("transport", None)
            if not _targets_tool(tgts, t):
                print("SKIP {}: {} (targets={})".format(t, name, tgts)); continue
            had_secret_ref = kitlib.has_secret_ref(defn)
            try:
                defn = kitlib.substitute_secrets(defn, secrets)
            except KeyError as e:
                print("ERROR {}: {} missing secret {} in config/secrets.env"
                      .format(t, name, e.args[0]), file=sys.stderr)
                ok = False
                continue  # skip only this server; the others do not need this secret
            if fmt == "json":
                kitlib.merge_mcp_json(dest, container, name, defn)
            else:
                kitlib.merge_mcp_toml(dest, container, name, defn)
            if had_secret_ref and args.workspace:
                wrote_secret_to_project = True
            print("OK   {}: {}".format(t, name))
    if wrote_secret_to_project:
        print("WARN: wrote real secret values into project-level MCP files. "
              "Do NOT commit them — add these paths to the project's .gitignore.",
              file=sys.stderr)
    return ok


def _missing_playbooks(root, playbook_lines):
    """Playbook files a profile routes to that do not exist under skills/pilot/."""
    missing = []
    for ln in playbook_lines:
        sep = " -> " if " -> " in ln else ("→" if "→" in ln else None)
        fname = (ln.split(sep, 1)[1] if sep else "").strip()
        if fname and not fname.startswith("playbooks/"):
            fname = "playbooks/" + fname
        if fname and not (root / "skills" / "pilot" / fname).is_file():
            missing.append(fname)
    return missing


def _warn_missing_playbooks(missing):
    if missing:
        print("WARN: profile routes to playbook file(s) that do not exist under "
              "skills/pilot/: {}".format(", ".join(missing)), file=sys.stderr)


def _fill_pilot(link, playbook_lines, copied):
    """Fill the installed pilot's routing table from the profile's playbooks.
    Only safe when pilot was COPIED: a symlink points back at the repo source,
    so writing through it would mutate the repo and make every install share one
    table. Under symlink, warn and leave the source table as-is."""
    target = link / "SKILL.md"
    is_symlink = link.is_symlink()
    if is_symlink:
        if playbook_lines:
            print("     note: pilot is a symlink; routing table not customized "
                  "per profile. Use --copy for a profile-specific pilot table.")
        return
    kitlib.fill_pilot_routes(target, playbook_lines)


def cmd_install(args: argparse.Namespace) -> int:
    tools = kitlib.tools_table()
    try:
        targets = []
        for w in args.target:
            targets += kitlib.resolve_targets(tools, w)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    only = set(args.only or [])
    want_skills = (not only) or ("skills" in only)
    want_rules = (not only) or ("rules" in only)
    want_mcp = (not only) or ("mcp" in only)
    root = kitlib.kit_root()
    copied_any = False
    marker_line = "# " + kitlib.KIT_MARKER

    # Profile decides which skills install and which playbooks pilot routes.
    # pilot itself always installs (it is the routing entry), even if a profile
    # omits it; its routing table is filled from the profile's [playbooks].
    profile = getattr(args, "profile", None) or "default"
    try:
        prof_skills, prof_playbooks = kitlib.load_profile(profile)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    install_skills = list(dict.fromkeys(prof_skills + ["pilot"]))
    if want_skills:
        _warn_missing_playbooks(_missing_playbooks(root, prof_playbooks))

    for t in dict.fromkeys(targets):  # de-dup, keep order
        row = tools[t]
        # columns: name skill_global skill_project rule_class rule_global rule_project rule_fmt rule_ext doc_url
        if want_skills:
            sg, sp = row[1], row[2]
            scope = sp if args.workspace else sg
            if scope == "-":
                print(f"SKIP {t}: no skill support")
            else:
                dest_dir = (Path(args.workspace) / scope) if args.workspace else kitlib.expand(scope)
                dest_dir.mkdir(parents=True, exist_ok=True)
                for name in install_skills:
                    s = root / "skills" / name
                    if not (s / "SKILL.md").is_file():
                        print(f"SKIP {t}: {name} (no skills/{name}/SKILL.md)")
                        continue
                    link = dest_dir / name
                    mode = _link_or_copy(s.resolve(), link, args.copy)
                    if mode == "skip":
                        print(f"SKIP {link} (exists, not a symlink)")
                    else:
                        if mode == "copy":
                            copied_any = True
                        print(f"OK   {t}: {name} ({mode})")
                        if name == "pilot":
                            _fill_pilot(link, prof_playbooks, args.copy)
        if want_rules:
            _install_rules(t, row, args, root, marker_line)

    mcp_ok = True
    if want_mcp:
        mcp_ok = _install_mcp(targets, args, root)

    if copied_any:
        if args.copy:
            print("note: skills were COPIED because you passed --copy; "
                  "after `git pull` updates the kit, re-run install to refresh them.")
        else:
            print("note: some skills were COPIED (no symlink privilege); "
                  "after `git pull` updates the kit, re-run install to refresh them.")
    return 0 if mcp_ok else 1


def _skill_dir(row, args):
    scope = row[2] if args.workspace else row[1]
    if scope == "-":
        return None
    return (Path(args.workspace) / scope) if args.workspace else kitlib.expand(scope)


def _uninstall_skills(t, row, args, root, install_skills, tools, targets):
    """Remove the skills the kit installed for this tool. Scans the skills dir;
    kit-owned = a symlink resolving into the kit's skills/, or a copied dir
    carrying COPY_MARK. Hand-made skills are never removed. install_skills, when
    given (--profile), limits removal to those names. If another tool outside
    this run shares the same skills dir, skip unless --force."""
    sg, sp = row[1], row[2]
    scope = sp if args.workspace else sg
    if scope == "-":
        print("SKIP {}: no skill support".format(t)); return
    dest_dir = (Path(args.workspace) / scope) if args.workspace else kitlib.expand(scope)
    sharers = [o for o, orow in tools.items()
               if o != t and o not in targets and _skill_dir(orow, args) == dest_dir]
    if sharers and not args.force:
        print("skip {}: {} is shared with {}. If {} does not use it, re-run with --force."
              .format(t, dest_dir, ", ".join(sharers), ", ".join(sharers)))
        return
    if not dest_dir.is_dir():
        print("skip {}: {} (not installed)".format(t, dest_dir)); return
    kit_skills = (root / "skills").resolve()
    removed = False
    for link in sorted(dest_dir.iterdir()):
        name = link.name
        if install_skills is not None and name not in install_skills:
            continue
        if link.is_symlink():
            try:
                link.resolve().relative_to(kit_skills)
            except ValueError:
                print("KEEP {}: {} (link points outside the kit)".format(t, name)); continue
            link.unlink()
            print("DEL  {}: {} (link)".format(t, name)); removed = True
        elif link.is_dir() and (link / COPY_MARK).is_file():
            shutil.rmtree(link)
            print("DEL  {}: {} (copy)".format(t, name)); removed = True
        elif link.is_dir() and install_skills is not None:
            print("KEEP {}: {} (no {} marker: hand-written or installed by an older kit)".format(
                t, name, COPY_MARK))
    if not removed:
        print("skip {}: no kit-installed skills in {}".format(t, dest_dir))


def _uninstall_rules(t, row, args, root):
    """Remove kit-installed rules for this tool. A-class: delete only files that
    carry the kit marker (hand-written rules are left). B-class: strip the kit
    block from the single file, preserving the user's own text."""
    rule_class = row[3]
    scope = row[5] if args.workspace else row[4]
    if scope == "-":
        print("SKIP {}: no rule support".format(t)); return
    rule_srcs = [s for s in sorted((root / "rules").glob("*.md")) if s.name != "README.md"]

    if rule_class == "A":
        ext = row[7] or "md"
        dest_dir = (Path(args.workspace) / scope) if args.workspace else kitlib.expand(scope)
        for src in rule_srcs:
            out = dest_dir / (src.stem + "." + ext)
            if not out.exists():
                continue
            if kitlib.KIT_MARKER in out.read_text(encoding="utf-8"):
                out.unlink()
                print("DEL  {}: {}".format(t, src.stem))
            else:
                print("skip {}: {} (hand-written)".format(t, src.stem))
    elif rule_class == "B":
        dest = (Path(args.workspace) / scope) if args.workspace else kitlib.expand(scope)
        if kitlib.remove_single_file_block(dest):
            print("DEL  {}: kit block removed from {}".format(t, dest.name))
        else:
            print("skip {}: no kit block in {}".format(t, dest.name))


def _uninstall_mcp(targets, args, root):
    mcp = kitlib.mcp_table()
    srcs = sorted((root / "config" / "mcp").glob("*.json"))
    names = [s.stem for s in srcs]
    for t in dict.fromkeys(targets):
        if t not in mcp:
            continue
        row = mcp[t]  # name mcp_global mcp_project fmt container doc_url
        fmt, container = row[3], row[4]
        scope = row[2] if args.workspace else row[1]
        if scope == "-":
            print("SKIP {}: no MCP file".format(t)); continue
        dest = (Path(args.workspace) / scope) if args.workspace else kitlib.expand(scope)
        for name in names:
            unmerge = kitlib.unmerge_mcp_json if fmt == "json" else kitlib.unmerge_mcp_toml
            if unmerge(dest, container, name):
                print("DEL  {}: {}".format(t, name))
            else:
                print("skip {}: {} (not in {})".format(t, name, dest.name))


def _rmdir_empty(targets, tools, args):
    """Remove dirs that uninstall left empty, walking up the scope's own path
    (.kiro/skills, then .kiro). Never removes the workspace root or HOME, and
    rmdir fails on a non-empty dir, so user content is never touched.
    ponytail: cannot tell a kit-created empty dir from a pre-existing empty
    one; both are removed."""
    mcp = kitlib.mcp_table()
    base = Path(args.workspace) if args.workspace else kitlib.expand("~")
    for t in dict.fromkeys(targets):
        row = tools[t]
        scopes = [row[2] if args.workspace else row[1],
                  row[5] if args.workspace else row[4]]
        if t in mcp:
            scopes.append(mcp[t][2] if args.workspace else mcp[t][1])
        for sc in scopes:
            if sc == "-":
                continue
            d = (Path(args.workspace) / sc) if args.workspace else kitlib.expand(sc)
            if d.suffix:  # a file path (e.g. CLAUDE.md, mcp.json): start at its parent
                d = d.parent
            while d != base and base in d.parents:
                try:
                    d.rmdir()
                except OSError:
                    break
                print("DEL  {}: empty dir {}".format(t, d))
                d = d.parent


def cmd_uninstall(args) -> int:
    """Reverse of install: remove the skills, rules and MCP servers install would
    place for the given tools/profile. Only removes what the kit owns; never
    touches hand-written content."""
    tools = kitlib.tools_table()
    try:
        targets = []
        for w in args.target:
            targets += kitlib.resolve_targets(tools, w)
    except ValueError as e:
        print(e, file=sys.stderr); return 1

    only = set(args.only or [])
    want_skills = (not only) or ("skills" in only)
    want_rules = (not only) or ("rules" in only)
    want_mcp = (not only) or ("mcp" in only)
    root = kitlib.kit_root()

    # No --profile: remove every kit-installed skill. With --profile: only that
    # profile's skills (plus pilot).
    install_skills = None
    if args.profile:
        try:
            prof_skills, _ = kitlib.load_profile(args.profile)
        except ValueError as e:
            print(e, file=sys.stderr); return 1
        install_skills = list(dict.fromkeys(prof_skills + ["pilot"]))

    for t in dict.fromkeys(targets):
        row = tools[t]
        if want_skills:
            _uninstall_skills(t, row, args, root, install_skills, tools, targets)
        if want_rules:
            _uninstall_rules(t, row, args, root)
    if want_mcp:
        _uninstall_mcp(targets, args, root)
    _rmdir_empty(targets, tools, args)
    return 0


def cmd_import_mcp(args) -> int:
    """Write config/mcp/<name>.json. Two input modes (AI picks whichever is
    cleaner): --json '<full object>' for anything (the args list, remote url,
    nested fields), or the convenience flags --command/--url/--env for a simple
    stdio/remote server. Validates shape; refuses to clobber unless --force.
    Why --json exists: argparse treats a bare '-y' in --arg as a flag, so a
    server whose args start with a dash is only expressible as JSON."""
    import json
    root = kitlib.kit_root()
    if args.json:
        try:
            defn = json.loads(args.json)
        except ValueError as e:
            print("bad --json: " + str(e), file=sys.stderr); return 1
        if not isinstance(defn, dict):
            print("--json must be a JSON object", file=sys.stderr); return 1
        if "command" not in defn and "url" not in defn:
            print("--json needs a 'command' (stdio) or 'url' (remote) key", file=sys.stderr)
            return 1
        defn.setdefault("transport", "http" if "url" in defn else "stdio")
        defn.setdefault("targets", args.targets)
    else:
        if not args.command and not args.url:
            print("need --json, or --command (stdio), or --url (remote)", file=sys.stderr)
            return 1
        if args.command and args.url:
            print("--command and --url are mutually exclusive", file=sys.stderr)
            return 1
        defn = {}
        if args.command:
            defn["command"] = args.command
            if args.arg:
                defn["args"] = args.arg
            defn["transport"] = "stdio"
        else:
            defn["url"] = args.url
            defn["transport"] = "http"
        if args.env:
            env = {}
            for pair in args.env:
                if "=" not in pair:
                    print("bad --env (want KEY=VALUE): " + pair, file=sys.stderr); return 1
                k, v = pair.split("=", 1)
                env[k.strip()] = v.strip()
            defn["env"] = env
        defn["targets"] = args.targets
    dest = root / "config" / "mcp" / (args.name + ".json")
    if dest.exists() and not args.force:
        print("exists: {} (use --force to overwrite)".format(dest), file=sys.stderr); return 1
    dest.write_text(json.dumps(defn, indent=2) + "\n", encoding="utf-8")
    secrets = [m for v in (defn.get("env") or {}).values()
               for m in kitlib._SECRET.findall(v)]
    print("wrote config/mcp/{}.json (targets={}, transport={})"
          .format(args.name, args.targets, defn["transport"]))
    if secrets:
        print("references secrets: {} — add them to config/secrets.env before install"
              .format(", ".join(sorted(set(secrets)))))
    print("next: `python kit.py install <tool>` to write it into a tool's config.")
    return 0


def cmd_profiles(args) -> int:
    """List skills/profiles/*.txt with their skill and playbook counts."""
    profs = kitlib.list_profiles()
    if not profs:
        print("no profiles in skills/profiles/")
        return 0
    print("{} profiles:".format(len(profs)))
    for name, nsk, npb in profs:
        print("  {:<16} {} skills, {} playbooks".format(name, nsk, npb))
    return 0


def cmd_list(args) -> int:
    """List what the kit has installed for one tool (or 'all'): skills (symlink
    or kit-owned copy), kit rules (A-class marked files / B-class block) and MCP
    servers. Read-only; inspects the tool's live install locations."""
    tools = kitlib.tools_table()
    mcp = kitlib.mcp_table()
    try:
        targets = kitlib.resolve_targets(tools, args.tool)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    root = kitlib.kit_root()
    for i, t in enumerate(targets):
        if i:
            print()
        _list_one(t, tools[t], mcp, args, root)
    return 0


def _list_one(t, row, mcp, args, root):
    scope = row[2] if args.workspace else row[1]
    print("== {} ({})".format(t, "project" if args.workspace else "global"))
    print("skills:")
    if scope == "-":
        print("  (no skill support)")
    else:
        sdir = (Path(args.workspace) / scope) if args.workspace else kitlib.expand(scope)
        found = False
        if sdir.is_dir():
            for d in sorted(sdir.iterdir()):
                if d.is_symlink():
                    print("  {:<24} link -> {}".format(d.name, os.readlink(str(d)))); found = True
                elif d.is_dir() and (d / COPY_MARK).is_file():
                    print("  {:<24} copy".format(d.name)); found = True
                elif d.is_dir() and (d / "SKILL.md").is_file():
                    print("  {:<24} unmanaged (no kit marker)".format(d.name)); found = True
        if not found:
            print("  (none)")

    print("rules:")
    rclass = row[3]
    rscope = row[5] if args.workspace else row[4]
    if rscope == "-":
        print("  (no rule support)")
    elif rclass == "A":
        ext = row[7] or "md"
        rdir = (Path(args.workspace) / rscope) if args.workspace else kitlib.expand(rscope)
        found = False
        if rdir.is_dir():
            for f in sorted(rdir.glob("*." + ext)):
                if kitlib.KIT_MARKER in f.read_text(encoding="utf-8", errors="ignore"):
                    print("  {}".format(f.name)); found = True
        if not found:
            print("  (none)")
    else:  # B-class
        rdest = (Path(args.workspace) / rscope) if args.workspace else kitlib.expand(rscope)
        has = rdest.exists() and kitlib.KIT_BLOCK_START in rdest.read_text(
            encoding="utf-8", errors="ignore")
        print("  {} ({})".format(rdest.name, "kit block present" if has else "no kit block"))

    print("mcp:")
    if t not in mcp:
        print("  (no MCP support)")
    else:
        mrow = mcp[t]
        mscope = mrow[2] if args.workspace else mrow[1]
        if mscope == "-":
            print("  (no MCP file for this scope)")
        else:
            mdest = (Path(args.workspace) / mscope) if args.workspace else kitlib.expand(mscope)
            container = mrow[4]
            servers = []
            if mdest.exists() and mdest.stat().st_size:
                if mrow[3] == "json":
                    import json
                    servers = list(json.loads(mdest.read_text(encoding="utf-8"))
                                   .get(container, {}))
                else:
                    servers = list(kitlib._load_toml(mdest).get(container, {}))
            kit_names = {s.stem for s in (root / "config" / "mcp").glob("*.json")}
            if servers:
                for s in sorted(servers):
                    print("  {}{}".format(s, "  (kit)" if s in kit_names else ""))
            else:
                print("  (none)")


def cmd_status(args) -> int:
    """One-screen overview of the kit itself: local skills/rules/MCP counts,
    registered upstream sources, imported items and available profiles."""
    root = kitlib.kit_root()
    skills = [d.name for d in sorted((root / "skills").iterdir())
              if d.is_dir() and (d / "SKILL.md").is_file()] if (root / "skills").is_dir() else []
    rules = [s.stem for s in sorted((root / "rules").glob("*.md")) if s.name != "README.md"]
    mcps = [s.stem for s in sorted((root / "config" / "mcp").glob("*.json"))]

    print("local content:")
    print("  skills ({}): {}".format(len(skills), ", ".join(skills) or "(none)"))
    print("  rules  ({}): {}".format(len(rules), ", ".join(rules) or "(none)"))
    print("  mcp    ({}): {}".format(len(mcps), ", ".join(mcps) or "(none)"))

    sk_src = _read_sources("skill-sources.tsv")
    ru_src = _read_sources("rule-sources.tsv")
    sk_sel = _read_sources("skill-selected.tsv")
    ru_sel = _read_sources("rule-selected.tsv")
    print("upstream sources:")
    print("  skill sources ({}): {}".format(
        len(sk_src), ", ".join(r[0] for r in sk_src) or "(none)"))
    print("  rule sources  ({}): {}".format(
        len(ru_src), ", ".join(r[0] for r in ru_src) or "(none)"))
    print("imported (tracked for updates):")
    print("  skills: {}".format(
        ", ".join("{}/{}".format(r[0], r[2]) for r in sk_sel if len(r) >= 3) or "(none)"))
    print("  rules:  {}".format(
        ", ".join("{}/{}".format(r[0], r[2]) for r in ru_sel if len(r) >= 3) or "(none)"))

    print("profiles:")
    for name, nsk, npb in kitlib.list_profiles():
        print("  {:<16} {} skills, {} playbooks".format(name, nsk, npb))
    return 0


def _read_sources(fname):
    """upstream/<fname> rows (skip comments), as lists."""
    rows = []
    f = kitlib.kit_root() / "upstream" / fname
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line and not line.lstrip().startswith("#"):
                rows.append(line.split("\t"))
    return rows


def cmd_manifest(args) -> int:
    """Emit a human-readable MANIFEST skeleton for a profile: tables of skills and
    rules (deterministic, from the profile and selected.tsv) plus a <!-- flow -->
    placeholder per playbook for the agent to fill with a Mermaid diagram. M2: the
    program produces the load-bearing tables; the agent only draws the flows."""
    root = kitlib.kit_root()
    profile = args.profile
    try:
        prof_skills, prof_playbooks = kitlib.load_profile(profile)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    # source lookup: local_name -> (source, sha) from skill-selected.tsv
    sk_src = {}
    for r in _read_sources("skill-selected.tsv"):
        if len(r) >= 4:
            sk_src[r[2]] = (r[0], r[3])
    rule_rows = [r for r in _read_sources("rule-selected.tsv") if len(r) >= 5]

    def desc_of(name):
        md = root / "skills" / name / "SKILL.md"
        if not md.is_file():
            return ""
        fm, _ = kitlib.split_frontmatter(md.read_text(encoding="utf-8"))
        return _clean_desc(fm.get("description", ""))

    out = []
    out.append("# 我的工作包 (profile: {})".format(profile))
    out.append("")
    with_tool = bool(args.tool)
    tool_cell = (" " + args.tool + " |") if with_tool else ""
    tool_hdr = " 裝到 |" if with_tool else ""
    tool_sep = "---|" if with_tool else ""

    out.append("## Playbooks（多步工作流）")
    missing_pb = _missing_playbooks(root, prof_playbooks)
    if prof_playbooks:
        for ln in prof_playbooks:
            sep = " -> " if " -> " in ln else ("→" if "→" in ln else None)
            when, fname = (ln.split(sep, 1) if sep else (ln, ""))
            fname = fname.strip()
            if fname and not fname.startswith("playbooks/"):
                fname = "playbooks/" + fname
            out.append("### {} — {}".format(fname.replace("playbooks/", "").replace(".md", ""),
                                             when.strip()))
            out.append("<!-- flow: 由 agent 補一個 Mermaid 流程圖，讀 skills/pilot/{} 的步驟 -->".format(fname))
            out.append("")
    else:
        out.append("（這個 profile 沒有 playbook）")
        out.append("")

    out.append("## 獨立 skill")
    out.append("| skill | 用途 | 來源 |" + tool_hdr)
    out.append("|---|---|---|" + tool_sep)
    for name in prof_skills:
        src = sk_src.get(name, ("自寫", ""))[0]
        out.append("| {} | {} | {} |".format(name, desc_of(name), src) + tool_cell)
    out.append("")

    out.append("## Rules")
    out.append("| rule | 載入模式 | 來源 |")
    out.append("|---|---|---|")
    for r in rule_rows:
        out.append("| {} | {} | {} |".format(r[2], r[3], r[0]))
    out.append("")

    dest = root / "skills" / "pilot" / "MANIFEST.md"
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("wrote {} (profile {}): {} playbooks, {} skills, {} rules"
          .format(dest, profile, len(prof_playbooks), len(prof_skills), len(rule_rows)))
    _warn_missing_playbooks(missing_pb)
    print("next: have the agent fill each <!-- flow --> with a Mermaid diagram.")
    return 0


def _clean_desc(desc):
    """Tidy a frontmatter description for one-line display. split_frontmatter is a
    minimal single-line YAML reader; when an upstream uses a block scalar (>-, >, |)
    its value is not on the key line, so flag it instead of printing the marker."""
    desc = desc.strip()
    if desc in (">", ">-", "|", "|-", "") or desc.startswith((">", "|")):
        return "(multi-line; see SKILL.md)"
    desc = desc.replace('\\"', '"').replace("\n", " ").strip()
    return desc[:97] + "..." if len(desc) > 100 else desc


def cmd_list_skills(args) -> int:
    """List every skill (a dir with SKILL.md) under a registered source's
    skills_dir, with its frontmatter description. Read-only; fetches the repo
    tarball once and reads locally, so it costs one API call, not one per skill."""
    import shutil, tempfile
    src = next((r for r in _read_sources("skill-sources.tsv") if r[0] == args.source), None)
    if not src:
        print("unknown source: " + args.source, file=sys.stderr)
        print("registered sources: " +
              ", ".join(r[0] for r in _read_sources("skill-sources.tsv")), file=sys.stderr)
        return 1
    _, repo, ref, skills_dir = src[0], src[1], src[2], src[3]
    sha = kitlib.gh_commit_sha(repo, ref)
    tmp = Path(tempfile.mkdtemp())
    try:
        r = kitlib.gh_extract(repo, sha, tmp)
        base = r / skills_dir
        if not base.is_dir():
            print("no skills_dir {} in {}@{}".format(skills_dir, repo, ref[:9]),
                  file=sys.stderr)
            return 1
        # Skills may sit one level deep (pstack: skills/unslop) or in category
        # subdirs (mattpocock: skills/engineering/tdd), so find every SKILL.md
        # at any depth. The name is its path relative to skills_dir — exactly
        # what `import-skill <source> <path>` takes.
        found = sorted(str(p.parent.relative_to(base)).replace(os.sep, "/")
                       for p in base.rglob("SKILL.md") if p.is_file())
        if not found:
            print("no skills (dirs with SKILL.md) under {}".format(skills_dir))
            return 0
        imported = {row[1] for row in _read_sources("skill-selected.tsv")
                    if row and row[0] == args.source}
        print("{} skills in {}/{} @ {}".format(len(found), repo, skills_dir, sha[:9]))
        for name in found:
            fm, _ = kitlib.split_frontmatter((base / name / "SKILL.md").read_text(encoding="utf-8"))
            desc = _clean_desc(fm.get("description", ""))
            mark = "*" if name in imported else " "
            print("  {} {:<28} {}".format(mark, name, desc))
        if imported:
            print("(* = already imported)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


def _copy_license(root, extracted_root, lic_path, source):
    """Copy an upstream LICENSE into upstream/licenses/<source>.LICENSE. The dir
    is not version-controlled (git drops empty dirs), so create it first. A
    license is a courtesy copy, never load-bearing: if the upstream path is
    missing or the copy fails, warn and carry on so the import still registers."""
    import shutil
    dest_dir = root / "upstream" / "licenses"
    dest_dir.mkdir(parents=True, exist_ok=True)
    licf = extracted_root / lic_path
    if not licf.is_file():
        print("WARN: no license at {} in upstream; import continues without it"
              .format(lic_path), file=sys.stderr)
        return
    try:
        shutil.copy(licf, dest_dir / (source + ".LICENSE"))
    except OSError as e:
        print("WARN: could not copy license ({}); import continues".format(e),
              file=sys.stderr)


def cmd_import_skill(args) -> int:
    import shutil, tempfile
    root = kitlib.kit_root()
    src = next((r for r in _read_sources("skill-sources.tsv") if r[0] == args.source), None)
    if not src:
        print("unknown source: " + args.source, file=sys.stderr); return 1
    _, repo, ref, skills_dir, lic = src[0], src[1], src[2], src[3], src[4]
    local = args.local_name or args.path
    sha = kitlib.gh_commit_sha(repo, ref)
    tmp = Path(tempfile.mkdtemp())
    try:
        r = kitlib.gh_extract(repo, sha, tmp)
        srcdir = r / skills_dir / args.path
        if not (srcdir / "SKILL.md").is_file():
            print("no SKILL.md at {}/{}".format(skills_dir, args.path), file=sys.stderr); return 1
        dest = root / "skills" / local
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(srcdir, dest)
        _copy_license(root, r, lic, args.source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _upsert_selected("skill-selected.tsv", args.source, args.path, local, sha, key_cols=2)
    print("imported {}/{} -> skills/{} @ {}".format(args.source, args.path, local, sha[:9]))
    return 0


def cmd_import_rule(args) -> int:
    import shutil, tempfile
    root = kitlib.kit_root()
    src = next((r for r in _read_sources("rule-sources.tsv") if r[0] == args.source), None)
    if not src:
        print("unknown rule source: " + args.source, file=sys.stderr); return 1
    _, repo, ref, lic = src[0], src[1], src[2], src[3]
    load = args.kit_load
    sha = kitlib.gh_commit_sha(repo, ref)
    tmp = Path(tempfile.mkdtemp())
    try:
        r = kitlib.gh_extract(repo, sha, tmp)
        up = r / args.file
        if not up.is_file():
            print("no file at " + args.file, file=sys.stderr); return 1
        fm, body = kitlib.split_frontmatter(up.read_text(encoding="utf-8"))
        desc = fm.get("description", "")
        out = ["---", "kit_load: " + load, "kit_targets: all",
               "title: " + args.local_name]
        if desc:
            out.append("description: " + desc)
        out.append("kit_source: {}:{}".format(args.source, args.file))
        out.append("---")
        text = "\n".join(out) + "\n\n" + body.rstrip("\n") + "\n"
        (root / "rules" / (args.local_name + ".md")).write_text(text, encoding="utf-8")
        _copy_license(root, r, lic, args.source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _upsert_selected("rule-selected.tsv", args.source, args.file, args.local_name, sha,
                     key_cols=2, extra=load)
    print("imported rule {}/{} -> rules/{}.md ({}) @ {}"
          .format(args.source, args.file, args.local_name, load, sha[:9]))
    print("NOTE: review rules/{}.md — upstream text may name tools (subagents, "
          "/commands) needing a rewrite.".format(args.local_name))
    return 0


def cmd_check_updates(args) -> int:
    root = kitlib.kit_root()

    def rows(fname):
        return _read_sources(fname)

    print("##### SKILLS")
    # skill-reviewed.txt is space-separated "<source> <path>", not tab
    reviewed = {}
    f = root / "upstream" / "skill-reviewed.txt"
    if f.exists():
        for ln in f.read_text(encoding="utf-8").splitlines():
            if ln and not ln.lstrip().startswith("#"):
                parts = ln.split()
                if len(parts) >= 2:
                    reviewed.setdefault(parts[0], set()).add(parts[1])
    selected = {}
    for r in rows("skill-selected.tsv"):
        selected.setdefault(r[0], []).append(r)  # source path local sha
    for src in rows("skill-sources.tsv"):
        name, repo, ref, sdir = src[0], src[1], src[2], src[3]
        head = kitlib.gh_commit_sha(repo, ref)
        print("== {} ({}@{}) head={}".format(name, repo, ref, head[:9]))
        tree = kitlib.gh_tree(repo, ref)
        upstream_skills = sorted({p[len(sdir)+1:-len("/SKILL.md")]
                                  for p in tree
                                  if p.startswith(sdir + "/") and p.endswith("/SKILL.md")})
        known = set(x[1] for x in selected.get(name, [])) | reviewed.get(name, set())
        for row in selected.get(name, []):
            p, sha = row[1], row[3]
            if p not in upstream_skills:
                print("   REMOVED/RENAMED upstream: " + p); continue
            if sha == head:
                print("   same    " + p); continue
            # did any file under the skill dir change between sha and head?
            changed = _skill_changed(repo, sha, head, sdir, p)
            print(("   CHANGED " if changed else "   same    ") + p)
        print("   new upstream skills (not in skill-reviewed.txt):")
        for p in upstream_skills:
            if p not in known:
                print("     + " + p)

    print("##### RULES")
    rsel = {}
    for r in rows("rule-selected.tsv"):
        rsel.setdefault(r[0], []).append(r)  # source file local load sha
    for src in rows("rule-sources.tsv"):
        name, repo, ref = src[0], src[1], src[2]
        if name not in rsel:
            continue
        head = kitlib.gh_commit_sha(repo, ref)
        print("== {} ({}@{}) head={}".format(name, repo, ref, head[:9]))
        for row in rsel[name]:
            fpath, local, sha = row[1], row[2], row[4]
            if sha == head:
                print("   same    {} ({})".format(local, fpath)); continue
            a = kitlib.gh_blob_sha(repo, sha, fpath)
            b = kitlib.gh_blob_sha(repo, head, fpath)
            print(("   same    " if a == b else "   CHANGED ") + "{} ({})".format(local, fpath))
    return 0


def _tree_blobs(repo, ref, prefix):
    """{path: blob_sha} for every file under prefix in repo@ref, via one tree
    read. Independent of the compare API's 300-file page limit."""
    out = {}
    for e in kitlib._gh_tree_entries(repo, ref):
        if e.get("type") == "blob" and e["path"].startswith(prefix):
            out[e["path"]] = e["sha"]
    return out


def _skill_changed(repo, base, head, sdir, path):
    """True if any file under <sdir>/<path>/ differs between base and head.
    Prefer the compare API (one call), but its file list is capped at 300, so a
    full (non-truncated) list is only trustworthy when it is a NEGATIVE: if no
    listed file touches our prefix AND the list was not truncated, nothing
    changed. Otherwise (our prefix appears, or the list hit the cap and might
    hide our prefix) fall back to comparing the skill dir's blob shas by tree."""
    import json, urllib.error
    prefix = "{}/{}/".format(sdir, path)
    try:
        d = json.load(kitlib._gh_get("{}/repos/{}/compare/{}...{}".format(kitlib._GH, repo, base, head)))
        files = [f["filename"] for f in (d.get("files") or [])]
        if any(fn.startswith(prefix) for fn in files):
            return True
        # no match: trust it only if the list was complete (< 300 cap)
        if len(files) < 300:
            return False
    except urllib.error.HTTPError:
        pass
    # truncated list or compare failed: compare the skill dir by tree blob shas
    return _tree_blobs(repo, base, prefix) != _tree_blobs(repo, head, prefix)


def cmd_check_public(args) -> int:
    import re as _re
    import subprocess
    root = kitlib.kit_root()
    fail = [0]
    def ok(m): print("PASS  " + m)
    def bad(m): print("FAIL  " + m); fail[0] = 1
    def warn(m): print("WARN  " + m)

    def git(*a):
        r = subprocess.run(["git", "-C", str(root)] + list(a),
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return r.stdout.decode("utf-8", "ignore")

    # 1. secrets.env never committed (appears as its own path line in history)
    names = git("log", "--all", "--format=%H", "--name-only")
    if any(ln.strip() == "config/secrets.env" for ln in names.splitlines()):
        bad("config/secrets.env IS in git history — scrub it before pushing")
    else:
        ok("config/secrets.env never appears in history")

    # 2. gitignored
    r = subprocess.run(["git", "-C", str(root), "check-ignore", "config/secrets.env"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok("config/secrets.env is gitignored") if r.returncode == 0 else bad("config/secrets.env is NOT gitignored")

    # 3. example tracked
    r = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch",
                        "config/secrets.env.example"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    ok("config/secrets.env.example is tracked") if r.returncode == 0 else warn("example template not tracked")

    # 4. token-shaped strings anywhere in history
    allp = git("log", "--all", "-p")
    tokpat = _re.compile(r"sk-[a-z0-9]{10,}|ghp_[a-z0-9]{10,}|AKIA[A-Z0-9]{12,}|"
                         r"-----BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-[a-z0-9-]{10,}", _re.I)
    hits = [ln for ln in allp.splitlines() if tokpat.search(ln)]
    if hits:
        bad("token-shaped strings found in history:")
        for h in hits[:5]:
            print("      " + h)
    else:
        ok("no token-shaped strings in history")

    # 5. real secret assignments (excluding refs/examples)
    asg = _re.compile(r"^\+.*(TOKEN|SECRET|API_KEY|PASSWORD)[ \t]*[=:]", _re.I)
    skip = _re.compile(r"KIT_SECRET|replace-me|secrets\.env|example|^\+#|placeholder", _re.I)
    leaks = [ln for ln in allp.splitlines() if asg.search(ln) and not skip.search(ln)]
    if leaks:
        warn("possible secret assignments (review each):")
        for h in leaks[:5]:
            print("      " + h)
    else:
        ok("no real secret assignments in history")

    # 6. embedded credentials in worktree skills/rules/mcp
    emb = []
    for d in ("skills", "rules", "config/mcp"):
        base = root / d
        if base.exists():
            for f in base.rglob("*"):
                if f.is_file() and tokpat.search(f.read_text(encoding="utf-8", errors="ignore")):
                    emb.append(str(f.relative_to(root)))
    if emb:
        bad("embedded credential-shaped strings in:")
        for e in emb:
            print("      " + e)
    else:
        ok("no embedded credentials in skills/ rules/ config/mcp/")

    # 7. single author email (info)
    authors = sorted(set(a for a in git("log", "--all", "--format=%ae").split() if a))
    if len(authors) <= 1:
        ok("single commit-author email: " + (authors[0] if authors else "(none)"))
    else:
        warn("multiple author emails (confirm all are intended to be public):")
        for a in authors:
            print("      " + a)

    print()
    print("RESULT: safe to push (review any WARN above)." if not fail[0]
          else "RESULT: DO NOT PUSH — fix the FAIL items first.")
    return fail[0]


def _udiff(a_path, b_path, a_label, b_label):
    """unified diff text between two files (missing file -> empty side)."""
    import difflib
    def read(p):
        return p.read_text(encoding="utf-8").splitlines(keepends=True) if p.exists() else []
    return "".join(difflib.unified_diff(read(a_path), read(b_path),
                                        fromfile=a_label, tofile=b_label))


def _changed_lines(diff_text):
    """Count +/- content lines in a unified diff (not the +++/--- headers).
    A rough change-size indicator for the agent, not a byte contract; GNU diff and
    difflib can differ by a line or two on how they group a hunk."""
    n = 0
    for ln in diff_text.splitlines():
        if ln[:3] in ("+++", "---"):
            continue
        if ln[:1] in "+-":
            n += 1
    return n


def _git_merge_file(merged, base, theirs):
    """Run `git merge-file merged base theirs`. Returns True if clean, False on
    conflict (which leaves <<<<<<< markers in `merged`)."""
    import subprocess
    r = subprocess.run(["git", "merge-file", str(merged), str(base), str(theirs)])
    return r.returncode == 0


def _strip_frontmatter(text):
    _, body = kitlib.split_frontmatter(text)
    return body


def cmd_diff(args) -> int:
    import shutil, tempfile, os as _os
    root = kitlib.kit_root()
    scratch = _os.environ.get("KIROCREW_SCRATCH") or tempfile.gettempdir()

    if args.rule:
        name = args.name
        row = next((r for r in _read_sources("rule-selected.tsv") if r[2] == name), None)
        if not row:
            print("not an imported rule: " + name, file=sys.stderr); return 1
        src, fpath, base = row[0], row[1], row[4]
        s = next((r for r in _read_sources("rule-sources.tsv") if r[0] == src), None)
        repo, ref = s[1], s[2]
        head = kitlib.gh_commit_sha(repo, ref)
        out = Path(args.outdir or (Path(scratch) / ("diffrule-" + name)))
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)

        def upbody(sha, dst):
            tmp = Path(tempfile.mkdtemp())
            r = kitlib.gh_extract(repo, sha, tmp)
            dst.write_text(_strip_frontmatter((r / fpath).read_text(encoding="utf-8")),
                           encoding="utf-8")
            shutil.rmtree(tmp, ignore_errors=True)

        upbody(base, out / "base.md")
        upbody(head, out / "theirs.md")
        (out / "mine.md").write_text(
            _strip_frontmatter((root / "rules" / (name + ".md")).read_text(encoding="utf-8")),
            encoding="utf-8")
        mvb = _udiff(out / "base.md", out / "mine.md", "base.md", "mine.md")
        tvb = _udiff(out / "base.md", out / "theirs.md", "base.md", "theirs.md")
        (out / "mine-vs-base.diff").write_text(mvb, encoding="utf-8")
        (out / "theirs-vs-base.diff").write_text(tvb, encoding="utf-8")
        shutil.copy(out / "mine.md", out / "merged-body.md")
        clean = _git_merge_file(out / "merged-body.md", out / "base.md", out / "theirs.md")
        if not clean:
            print("CONFLICT in body")
        (out / "head.sha").write_text(head + "\n", encoding="utf-8")
        print("base={} head={} conflicts={}".format(base[:9], head[:9], 0 if clean else 1))
        print("mine-vs-base: {} changed body lines (your edits)".format(_changed_lines(mvb)))
        print("theirs-vs-base: {} changed body lines (official edits)".format(_changed_lines(tvb)))
        print("merged body (reapply your kit frontmatter on top): {}/merged-body.md".format(out))
        print("output: " + str(out))
        return 0

    # skill mode
    name = args.name
    row = next((r for r in _read_sources("skill-selected.tsv") if r[2] == name), None)
    if not row:
        print("not imported: " + name, file=sys.stderr); return 1
    src, path, base = row[0], row[1], row[3]
    s = next((r for r in _read_sources("skill-sources.tsv") if r[0] == src), None)
    repo, ref, sdir = s[1], s[2], s[3]
    head = kitlib.gh_commit_sha(repo, ref)
    out = Path(args.outdir or (Path(scratch) / ("diff-" + name)))
    if out.exists():
        shutil.rmtree(out)
    for d in ("base", "theirs", "merged"):
        (out / d).mkdir(parents=True)

    def fetch(sha, dst):
        tmp = Path(tempfile.mkdtemp())
        r = kitlib.gh_extract(repo, sha, tmp)
        srcdir = r / sdir / path
        if srcdir.is_dir():
            for f in srcdir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(srcdir)
                    (dst / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(f, dst / rel)
        shutil.rmtree(tmp, ignore_errors=True)

    fetch(base, out / "base")
    fetch(head, out / "theirs")
    mine = root / "skills" / name
    (out / "mine-vs-base.diff").write_text(
        _tree_diff(out / "base", mine, "base", "mine"), encoding="utf-8")
    (out / "theirs-vs-base.diff").write_text(
        _tree_diff(out / "base", out / "theirs", "base", "theirs"), encoding="utf-8")

    files = set()
    for d in (out / "base", out / "theirs", mine):
        if d.exists():
            files |= {f.relative_to(d) for f in d.rglob("*") if f.is_file()}
    conflicts = 0
    for rel in sorted(files, key=str):
        b, t, m = out / "base" / rel, out / "theirs" / rel, mine / rel
        md = out / "merged" / rel
        md.parent.mkdir(parents=True, exist_ok=True)
        if b.is_file() and t.is_file() and m.is_file():
            shutil.copy(m, md)
            if not _git_merge_file(md, b, t):
                print("CONFLICT  {}".format(rel)); conflicts += 1
        elif m.is_file() and not t.is_file() and b.is_file():
            print("DELETED UPSTREAM  {}".format(rel))
        elif t.is_file() and not b.is_file() and not m.is_file():
            print("NEW UPSTREAM      {}".format(rel)); shutil.copy(t, md)
        elif m.is_file():
            shutil.copy(m, md)
    (out / "head.sha").write_text(head + "\n", encoding="utf-8")
    mvb = (out / "mine-vs-base.diff").read_text(encoding="utf-8")
    tvb = (out / "theirs-vs-base.diff").read_text(encoding="utf-8")
    print("base={} head={} conflicts={}".format(base[:9], head[:9], conflicts))
    print("mine-vs-base: {} changed lines (your edits)".format(_changed_lines(mvb)))
    print("theirs-vs-base: {} changed lines (official edits)".format(_changed_lines(tvb)))
    print("output: " + str(out))
    return 0


def _tree_diff(a_dir, b_dir, a_label, b_label):
    """Recursive unified diff of two dirs (like diff -ruN), stable file order."""
    files = set()
    for d in (a_dir, b_dir):
        if d.exists():
            files |= {f.relative_to(d) for f in d.rglob("*") if f.is_file()}
    chunks = []
    for rel in sorted(files, key=str):
        chunks.append(_udiff(a_dir / rel, b_dir / rel,
                             "{}/{}".format(a_label, rel), "{}/{}".format(b_label, rel)))
    return "".join(chunks)


def _upsert_selected(fname, source, path, local, sha, key_cols, extra=None):
    """Replace any row matching (source, path) in upstream/<fname>, then append.
    key_cols=2 means the first two columns identify the row. extra (rule load)
    is inserted before sha when given, matching rule-selected.tsv's columns."""
    f = kitlib.kit_root() / "upstream" / fname
    lines = f.read_text(encoding="utf-8").splitlines() if f.exists() else []
    kept = []
    for ln in lines:
        c = ln.split("\t")
        if not ln.lstrip().startswith("#") and len(c) >= 2 and c[0] == source and c[1] == path:
            continue  # drop old row for this item
        kept.append(ln)
    if extra is not None:
        kept.append("\t".join([source, path, local, extra, sha]))
    else:
        kept.append("\t".join([source, path, local, sha]))
    f.write_text("\n".join(kept) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="kit.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    pi = sub.add_parser("install", help="install skills, rules and MCP into a tool")
    pi.add_argument("target", nargs="+", help="tool name(s) from config/tools.tsv, or 'all'")
    pi.add_argument("--workspace", help="install into DIR's project-level folders")
    pi.add_argument("--only", action="append", choices=["skills", "rules", "mcp"],
                    help="run just one installer (repeatable)")
    pi.add_argument("--copy", action="store_true", help="force copy instead of symlink")
    pi.add_argument("--profile", default="default",
                    help="skills/profiles/<name>.txt: which skills install + pilot playbooks")
    pi.set_defaults(func=cmd_install)

    pu = sub.add_parser("uninstall", help="remove kit-installed skills/rules/mcp")
    pu.add_argument("target", nargs="+", help="tool name(s) from config/tools.tsv, or 'all'")
    pu.add_argument("--workspace", help="remove from DIR's project-level folders")
    pu.add_argument("--only", action="append", choices=["skills", "rules", "mcp"],
                    help="uninstall just one kind (repeatable)")
    pu.add_argument("--profile", default=None,
                    help="remove only this profile's skills (default: every kit-installed skill)")
    pu.add_argument("--force", action="store_true",
                    help="remove skills even if another tool shares the same skills dir")
    pu.set_defaults(func=cmd_uninstall)

    pls = sub.add_parser("list-skills", help="list a source's skills + descriptions")
    pls.add_argument("source", help="a name registered in upstream/skill-sources.tsv")
    pls.set_defaults(func=cmd_list_skills)

    ps = sub.add_parser("import-skill", help="import one upstream skill")
    ps.add_argument("source"); ps.add_argument("path")
    ps.add_argument("local_name", nargs="?", default=None)
    ps.set_defaults(func=cmd_import_skill)

    pr = sub.add_parser("import-rule", help="import one upstream file as a rule")
    pr.add_argument("source"); pr.add_argument("file"); pr.add_argument("local_name")
    pr.add_argument("kit_load", nargs="?", default="always",
                    choices=["always", "glob", "manual", "model"])
    pr.set_defaults(func=cmd_import_rule)

    pim = sub.add_parser("import-mcp", help="write a config/mcp/<name>.json definition")
    pim.add_argument("name", help="server name (file becomes config/mcp/<name>.json)")
    pim.add_argument("--json", help="full server object as JSON (use when args start with '-')")
    pim.add_argument("--command", help="stdio server command (e.g. npx)")
    pim.add_argument("--arg", action="append",
                     help="one command arg; repeat for each (use --json if an arg starts with '-')")
    pim.add_argument("--url", help="remote server URL (instead of --command)")
    pim.add_argument("--env", action="append",
                     help="KEY=VALUE env var; value may be ${KIT_SECRET:NAME} (repeatable)")
    pim.add_argument("--targets", default="all",
                     help="'all' or a comma list of tool names (default all)")
    pim.add_argument("--force", action="store_true", help="overwrite an existing definition")
    pim.set_defaults(func=cmd_import_mcp)

    pc = sub.add_parser("check-updates", help="list upstream changes (read-only)")
    pc.set_defaults(func=cmd_check_updates)

    pd = sub.add_parser("diff", help="three-way compare an imported skill or rule")
    pd.add_argument("name")
    pd.add_argument("outdir", nargs="?", default=None)
    pd.add_argument("--rule", action="store_true", help="rule mode (single file, body only)")
    pd.set_defaults(func=cmd_diff)

    pcp = sub.add_parser("check-public", help="pre-push safety scan (read-only)")
    pcp.set_defaults(func=cmd_check_public)

    pm = sub.add_parser("manifest", help="write pilot/MANIFEST.md skeleton for a profile")
    pm.add_argument("--profile", default="default")
    pm.add_argument("--tool", default=None, help="annotate the install-target column")
    pm.set_defaults(func=cmd_manifest)

    pp = sub.add_parser("profiles", help="list available profiles + counts")
    pp.set_defaults(func=cmd_profiles)

    pl = sub.add_parser("list", help="list what the kit installed for one tool")
    pl.add_argument("tool", help="tool name from config/tools.tsv")
    pl.add_argument("--workspace", help="inspect DIR's project-level folders")
    pl.set_defaults(func=cmd_list)

    pst = sub.add_parser("status", help="overview of local content, sources, profiles")
    pst.set_defaults(func=cmd_status)

    # setup = install (skills+rules+mcp in one run); kept as a familiar alias
    psetup = sub.add_parser("setup", help="install everything (alias of install)")
    psetup.add_argument("target", nargs="+")
    psetup.add_argument("--workspace")
    psetup.add_argument("--only", action="append", choices=["skills", "rules", "mcp"])
    psetup.add_argument("--copy", action="store_true")
    psetup.add_argument("--profile", default="default")
    psetup.set_defaults(func=cmd_install)

    args = p.parse_args(argv)
    if not getattr(args, "cmd", None):
        p.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
