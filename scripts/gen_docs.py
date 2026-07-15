#!/usr/bin/env python3
"""Generate docs/COMMANDS.md — a complete reference of every command and option,
by introspecting the actual Typer/Click app so the docs never drift.

Usage:  python scripts/gen_docs.py
"""

from __future__ import annotations

import io
from pathlib import Path

import typer

from opcli.cli import app

OUT = Path(__file__).resolve().parent.parent / "docs" / "COMMANDS.md"


def _is_argument(p) -> bool:
    return getattr(p, "param_type_name", "") == "argument"


def _param_row(p) -> str | None:
    if _is_argument(p):
        return None
    opts = ", ".join(f"`{o}`" for o in list(p.opts) + list(p.secondary_opts))
    help_text = (getattr(p, "help", "") or "").replace("\n", " ").replace("|", "\\|")
    req = " **(required)**" if p.required else ""
    return f"| {opts} | {help_text}{req} |"


def _arguments(cmd) -> list[str]:
    out = []
    for p in cmd.params:
        if _is_argument(p):
            out.append(f"`{p.name}` ({'required' if p.required else 'optional'})")
    return out


def _emit_command(buf: io.StringIO, path: str, cmd) -> None:
    buf.write(f"### `openproject {path}`\n\n")
    help_text = (cmd.help or getattr(cmd, "short_help", "") or "").strip()
    if help_text:
        buf.write(help_text + "\n\n")
    args = _arguments(cmd)
    if args:
        buf.write("**Arguments:** " + ", ".join(args) + "\n\n")
    rows = [r for r in (_param_row(p) for p in cmd.params) if r]
    if rows:
        buf.write("| Option | Description |\n| --- | --- |\n")
        buf.write("\n".join(rows) + "\n\n")


def main() -> None:
    root = typer.main.get_command(app)
    buf = io.StringIO()
    buf.write("# Command reference\n\n")
    buf.write(
        "_Auto-generated from the CLI (`python scripts/gen_docs.py`). Every command "
        "also accepts the global `--output/-o` (json\\|table\\|markdown), `--format/-f`, "
        "`--fields`, `--profile/-p` and `--no-color` options, usable anywhere on the line._\n\n"
    )

    groups = sorted(root.commands.items())
    buf.write("## Groups\n\n")
    for name, grp in groups:
        desc = (grp.help or getattr(grp, "short_help", "") or "").strip().split("\n")[0]
        buf.write(f"- [`{name}`](#{name}) — {desc}\n")
    buf.write("\n")

    for name, grp in groups:
        buf.write(f"## `{name}`\n\n")
        if hasattr(grp, "commands"):
            for sub_name, sub in sorted(grp.commands.items()):
                _emit_command(buf, f"{name} {sub_name}", sub)
        else:
            _emit_command(buf, name, grp)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(buf.getvalue())
    n_cmds = sum(len(g.commands) if hasattr(g, "commands") else 1 for _, g in groups)
    print(f"wrote {OUT} ({len(groups)} groups, {n_cmds} commands)")


if __name__ == "__main__":
    main()
