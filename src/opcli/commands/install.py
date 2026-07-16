"""`openproject install claude` — register this CLI with Claude Code.

The idiomatic way to make a CLI discoverable to Claude Code is a **Skill**: a
`SKILL.md` whose ``description`` tells Claude when to use the tool. This command
drops that skill into ``~/.claude/skills/openproject/`` (or the project's
``.claude/skills/``), and can optionally add a one-line hint to the user's
``~/.claude/CLAUDE.md`` memory. Everything is reversible with ``--uninstall``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from .. import __version__
from agentcli.errors import OpError
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)

SKILL_NAME = "openproject"
_MEM_START = "<!-- openproject-cli:start -->"
_MEM_END = "<!-- openproject-cli:end -->"

SKILL_MD = f"""\
---
name: openproject
description: >-
  Work with OpenProject via the `openproject` CLI — projects, work packages
  (tasks/bugs), time entries, comments, powerful search, notifications,
  attachments, and per-person cost/invoicing reports. Use this whenever the user
  mentions OpenProject, work packages, tickets/tasks in OpenProject, logging
  time, or wants to query or update their OpenProject instance.
---

# OpenProject CLI (agent-tool-openproject-cli v{__version__})

The `openproject` command-line tool is installed on this machine and talks to
the user's OpenProject instance over the REST API v3.

## Learn the tool from the tool
- `openproject guide` — full operating manual (output contract, auth, filter
  discovery, gotchas). `openproject guide <topic>` for search/wp/time/costs/context/…
- `openproject <group> --help` for any command.

## Output contract
- Default output is JSON on stdout — parse it. Errors are JSON on stderr with a
  non-zero exit code (`{{"error": ..., "status": 404}}`).
- Trim with `--fields id,subject,status,assignee.name`; export with `-o csv`;
  stream large sets with `--stream`.

## Auth
Uses `OPCLI_BASE_URL` + `OPCLI_TOKEN` env vars, or a stored profile
(`openproject auth status`). If not configured, ask the user to run
`openproject auth login --url <URL> --token <TOKEN>`.

## Make changes safely
Preview ANY write with `--dry-run` (prints the exact request, sends nothing).
Confirm destructive actions (delete/archive) with the user before running for real.

## Common commands
- Find work: `openproject search wp --mine --overdue` ·
  `openproject search wp --where "status = open" --where "updated > 7d"`
- Discover filters (don't hardcode JSON): `openproject search fields` ·
  `openproject search operators` · `openproject search values status`
- Read/update: `openproject wp get <id>` ·
  `openproject wp update <id> --status "In progress" --assignee jane.doe`
- Time & invoicing: `openproject time add 2.5 -w <id> --activity Development` ·
  `openproject cost report --month 2026-07 --rates rates.json --detailed -o csv`

Pass names, not ids (`--assignee jane.doe`, `--status "In progress"`, `me`).
Anything not wrapped: `openproject raw <method> <path>`.
"""

_MEMORY_HINT = (
    f"{_MEM_START}\n"
    "The `openproject` CLI (package agent-tool-openproject-cli) is installed. It is an "
    "agent-ready OpenProject client with JSON output — run `openproject guide` to learn it.\n"
    f"{_MEM_END}\n"
)


def claude_available() -> bool:
    """Best-effort: is Claude Code installed on this machine?"""
    if shutil.which("claude"):
        return True
    home = Path.home()
    return (home / ".claude").is_dir() or (home / ".local" / "bin" / "claude").exists()


def _skill_dir(project: bool) -> Path:
    base = Path.cwd() if project else Path.home()
    return base / ".claude" / "skills" / SKILL_NAME


def skill_installed(project: bool = False) -> bool:
    return (_skill_dir(project) / "SKILL.md").exists()


def write_skill(project: bool = False) -> Path:
    d = _skill_dir(project)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "SKILL.md"
    path.write_text(SKILL_MD)
    return path


def _memory_file() -> Path:
    return Path.home() / ".claude" / "CLAUDE.md"


def write_memory_hint() -> Path:
    path = _memory_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.exists() else ""
    if _MEM_START in existing:
        return path  # already present
    sep = "" if existing.endswith("\n") or not existing else "\n"
    path.write_text(existing + sep + "\n" + _MEMORY_HINT)
    return path


def _remove_memory_hint() -> bool:
    path = _memory_file()
    if not path.exists():
        return False
    text = path.read_text()
    if _MEM_START not in text or _MEM_END not in text:
        return False
    before, _, rest = text.partition(_MEM_START)
    _, _, after = rest.partition(_MEM_END)
    path.write_text((before.rstrip("\n") + "\n" + after.lstrip("\n")).strip("\n") + "\n")
    return True


@app.command()
def claude(
    ctx: typer.Context,
    project: bool = typer.Option(False, "--project", help="Install into ./.claude (this repo) instead of ~/.claude."),
    memory: bool = typer.Option(False, "--memory", help="Also add a one-line hint to ~/.claude/CLAUDE.md."),
    force: bool = typer.Option(False, "--force", help="Install even if Claude Code isn't detected."),
    uninstall: bool = typer.Option(False, "--uninstall", help="Remove the skill (and memory hint)."),
    print_: bool = typer.Option(False, "--print", help="Print the SKILL.md that would be written and exit."),
) -> None:
    """Register this CLI with Claude Code as a Skill so Claude auto-uses it.

    Writes ~/.claude/skills/openproject/SKILL.md (idiomatic discovery). Claude
    then invokes it whenever you mention OpenProject. Reversible with --uninstall.
    """
    obj = ctx_obj(ctx)

    if print_:
        typer.echo(SKILL_MD)
        return

    if uninstall:
        d = _skill_dir(project)
        removed = []
        if (d / "SKILL.md").exists():
            (d / "SKILL.md").unlink()
            try:
                d.rmdir()
            except OSError:
                pass
            removed.append(str(d))
        if _remove_memory_hint():
            removed.append(str(_memory_file()) + " (hint)")
        obj.emitter.emit({"status": "uninstalled", "removed": removed})
        return

    if not force and not claude_available():
        raise OpError(
            "Claude Code was not detected on this machine. Install it from "
            "https://claude.com/claude-code, or re-run with --force to install the skill anyway."
        )

    skill_path = write_skill(project)
    result = {
        "status": "installed",
        "skill": str(skill_path),
        "scope": "project" if project else "user",
        "note": "Claude Code will use the `openproject` CLI automatically when you mention OpenProject. Start a new session to pick it up.",
    }
    if memory:
        result["memoryHint"] = str(write_memory_hint())
    obj.emitter.emit(result)
