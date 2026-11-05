#!/usr/bin/env python3
"""agent_skill_kit — cross-platform installer/manager (Python 3.11+).

Single entry point with git-style subcommands. This is the Python port of the
bash scripts; being ported one piece at a time. Done so far: install (skills).

Usage:
  python kit.py install <tool>... [--workspace DIR] [--only skills] [--copy]
    tool: any name in config/tools.tsv, or 'all'
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

import kitlib


def _link_or_copy(src: Path, dest: Path, force_copy: bool) -> str:
    """Install one skill dir at dest. Returns 'link' or 'copy' (mode used).
    Default: try symlink, fall back to copy. --copy forces copy.
    An existing non-symlink dest is left alone (caller reports SKIP)."""
    if dest.is_symlink() or dest.exists():
        if dest.is_symlink():
            dest.unlink()
        elif force_copy:
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
    import json
    mcp = kitlib.mcp_table()
    secrets = kitlib.load_secrets()
    srcs = sorted((root / "config" / "mcp").glob("*.json"))
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
            if not _targets_tool(tgts, t):
                print("SKIP {}: {} (targets={})".format(t, name, tgts)); continue
            try:
                defn = kitlib.substitute_secrets(defn, secrets)
            except KeyError as e:
                print("ERROR {}: {} missing secret {} in config/secrets.env"
                      .format(t, name, e.args[0]), file=sys.stderr)
                return
            if fmt == "json":
                kitlib.merge_mcp_json(dest, container, name, defn)
            else:
                kitlib.merge_mcp_toml(dest, container, name, defn)
            print("OK   {}: {}".format(t, name))


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
                for s in sorted((root / "skills").glob("*/")):
                    if not s.is_dir():
                        continue
                    name = s.name
                    link = dest_dir / name
                    mode = _link_or_copy(s.resolve(), link, args.copy)
                    if mode == "skip":
                        print(f"SKIP {link} (exists, not a symlink)")
                    else:
                        if mode == "copy":
                            copied_any = True
                        print(f"OK   {t}: {name} ({mode})")
        if want_rules:
            _install_rules(t, row, args, root, marker_line)

    if want_mcp:
        _install_mcp(targets, args, root)

    if copied_any:
        print("note: some skills were COPIED (no symlink privilege); "
              "after `git pull` updates the kit, re-run install to refresh them.")
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
        licf = r / lic
        if licf.is_file():
            shutil.copy(licf, root / "upstream" / "licenses" / (args.source + ".LICENSE"))
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
        licf = r / lic
        if licf.is_file():
            shutil.copy(licf, root / "upstream" / "licenses" / (args.source + ".LICENSE"))
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


def _skill_changed(repo, base, head, sdir, path):
    """True if any file under <sdir>/<path>/ differs between base and head.
    Uses the compare API; on its pagination/limits, falls back to comparing the
    SKILL.md blob sha (a change there is the common case)."""
    import json, urllib.error
    prefix = "{}/{}/".format(sdir, path)
    try:
        d = json.load(kitlib._gh_get("{}/repos/{}/compare/{}...{}".format(kitlib._GH, repo, base, head)))
        files = [f["filename"] for f in (d.get("files") or [])]
        if files:
            return any(fn.startswith(prefix) for fn in files)
    except urllib.error.HTTPError:
        pass
    a = kitlib.gh_blob_sha(repo, base, prefix + "SKILL.md")
    b = kitlib.gh_blob_sha(repo, head, prefix + "SKILL.md")
    return a != b


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

    pi = sub.add_parser("install", help="install skills (rules/mcp: later batch)")
    pi.add_argument("target", nargs="+", help="tool name(s) from config/tools.tsv, or 'all'")
    pi.add_argument("--workspace", help="install into DIR's project-level folders")
    pi.add_argument("--only", action="append", choices=["skills", "rules", "mcp"],
                    help="run just one installer (repeatable)")
    pi.add_argument("--copy", action="store_true", help="force copy instead of symlink")
    pi.set_defaults(func=cmd_install)

    ps = sub.add_parser("import-skill", help="import one upstream skill")
    ps.add_argument("source"); ps.add_argument("path")
    ps.add_argument("local_name", nargs="?", default=None)
    ps.set_defaults(func=cmd_import_skill)

    pr = sub.add_parser("import-rule", help="import one upstream file as a rule")
    pr.add_argument("source"); pr.add_argument("file"); pr.add_argument("local_name")
    pr.add_argument("kit_load", nargs="?", default="always",
                    choices=["always", "glob", "manual", "model"])
    pr.set_defaults(func=cmd_import_rule)

    pc = sub.add_parser("check-updates", help="list upstream changes (read-only)")
    pc.set_defaults(func=cmd_check_updates)

    args = p.parse_args(argv)
    if not getattr(args, "cmd", None):
        p.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
