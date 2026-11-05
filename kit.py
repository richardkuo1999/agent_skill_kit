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
        # mcp install: ported in a later batch (bash still handles it)

    if copied_any:
        print("note: some skills were COPIED (no symlink privilege); "
              "after `git pull` updates the kit, re-run install to refresh them.")
    return 0


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

    args = p.parse_args(argv)
    if not getattr(args, "cmd", None):
        p.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
