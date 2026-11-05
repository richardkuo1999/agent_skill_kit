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
    root = kitlib.kit_root()
    copied_any = False

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
        # rule / mcp install: ported in a later batch (bash still handles those)

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
