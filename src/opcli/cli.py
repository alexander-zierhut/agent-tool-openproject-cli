"""Top-level Typer application wiring together every command group."""

from __future__ import annotations

import os
import sys

import typer

from . import __version__
from .context import AppContext
from .errors import DryRun, OpError
from .output import OutputFormat, print_error


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()

app = typer.Typer(
    name="openproject",
    help=(
        "Agent-friendly CLI for OpenProject (work packages, projects, time, search, invoicing).\n\n"
        "Output is JSON on stdout by default (errors are JSON on stderr with a non-zero exit code); "
        "add `-o table` or `-o markdown`, or trim with `--fields id,subject`. Pass names not ids "
        "(`--assignee jane.doe`, `--status \"In progress\"`, `me`).\n\n"
        "New here / no context? Run `openproject guide` for the full playbook, or "
        "`openproject search fields` to discover what you can filter on."
    ),
    epilog=(
        "Learn more:  `openproject guide`  ·  `openproject guide <topic>`  ·  "
        "`openproject <group> --help`  ·  discover filters with `openproject search fields`."
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)

# Remembered so the central error handler in main() can render errors in the
# same format the user selected, even for failures raised before a command runs.
_ERROR_FORMAT = OutputFormat.json


@app.callback()
def _root(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(
        None, "--output", "-o",
        help="Output format: json (default), table, or markdown. Also available as --format/-f anywhere on the line.",
    ),
    fields: str = typer.Option(
        None, "--fields", "--columns",
        help="Comma-separated fields to return/show, e.g. 'id,subject,status,assignee.name'. Works anywhere on the line.",
    ),
    profile: str = typer.Option(
        None, "--profile", "-p", help="Configuration profile (overrides the active one)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Mutating commands: print the request that would be sent and exit without sending."
    ),
    stream: bool = typer.Option(
        False, "--stream", help="Stream list/search results as NDJSON (one JSON object per line)."
    ),
    no_context: bool = typer.Option(
        False, "--no-context", help="Ignore the saved session context (`openproject context`) for this command."
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable coloured output."),
    version: bool = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    if profile:
        os.environ["OPCLI_PROFILE"] = profile
    # Don't prompt for a default format for meta commands (settings/guide).
    interactive = ctx.invoked_subcommand not in ("settings", "guide") and sys.stdin.isatty() and sys.stdout.isatty()
    ctx.obj = AppContext(output=output, color=not no_color, interactive=interactive)
    global _ERROR_FORMAT
    _ERROR_FORMAT = ctx.obj.emitter.fmt

    # Sticky context: inject saved defaults as Click default_map (explicit flags
    # still win). --no-context / meta groups opt out.
    if os.environ.get("OPCLI_NO_CONTEXT") != "1":
        active = ctx.obj.config.context
        if active:
            dm = _context_default_map(ctx.command, active, skip={"context", "settings", "guide"})
            ctx.default_map = {**(ctx.default_map or {}), **dm}


def _context_default_map(group, values: dict, skip: set) -> dict:
    """Build a Click default_map from the active context: for every command that
    has an option whose name is a context key, set that key's value as the default."""
    dmap: dict = {}
    for name, cmd in getattr(group, "commands", {}).items():
        if name in skip:
            continue
        if hasattr(cmd, "commands"):
            sub = _context_default_map(cmd, values, skip)
            if sub:
                dmap[name] = sub
        else:
            opt_names = {p.name for p in cmd.params if getattr(p, "param_type_name", "") == "option"}
            matched = {k: v for k, v in values.items() if k in opt_names}
            if matched:
                dmap[name] = matched
    return dmap


_FORMAT_FLAGS = ("--format", "-f", "--output", "-o")
_FIELDS_FLAGS = ("--fields", "--columns")
_BOOL_FLAGS = ("--dry-run", "--stream", "--no-context")  # value-less globals


def _pop_globals(argv: list[str]) -> tuple[str | None, str | None, set[str], list[str]]:
    """Extract global flags (output format, --fields, and the boolean globals
    --dry-run/--stream/--no-context) from anywhere on the command line, so they
    work *after* a subcommand too. Honours ``--`` to stop parsing."""
    out: list[str] = []
    fmt: str | None = None
    fields: str | None = None
    bools: set[str] = set()
    i, stop = 0, False

    def take_value(idx: int) -> tuple[str | None, int]:
        return (argv[idx + 1], idx + 1) if idx + 1 < len(argv) else (None, idx)

    while i < len(argv):
        a = argv[i]
        if not stop and a == "--":
            stop = True
            out.append(a)
        elif not stop and a in _FORMAT_FLAGS:
            fmt, i = take_value(i)
        elif not stop and a in _FIELDS_FLAGS:
            fields, i = take_value(i)
        elif not stop and a in _BOOL_FLAGS:
            bools.add(a.lstrip("-"))
        elif not stop and (a.startswith("--format=") or a.startswith("--output=") or a.startswith("-f=") or a.startswith("-o=")):
            fmt = a.split("=", 1)[1]
        elif not stop and (a.startswith("--fields=") or a.startswith("--columns=")):
            fields = a.split("=", 1)[1]
        else:
            out.append(a)
        i += 1
    return fmt, fields, bools, out


# ---- command groups (registered below to avoid circular imports) ----
from .commands import (  # noqa: E402
    attachments,
    auth,
    comments,
    context as context_cmd,
    costs,
    custom_fields,
    filelinks,
    guide,
    memberships,
    notifications,
    projects,
    raw,
    search,
    settings,
    time_entries,
    users,
    wiki,
    workpackages,
)

app.command("guide", help="Built-in operating guide — how to use this CLI without external docs.")(guide.guide)

app.add_typer(auth.app, name="auth", help="Log in, log out, inspect credentials.")
app.add_typer(projects.app, name="project", help="Create, list, archive projects.")
app.add_typer(workpackages.app, name="wp", help="Work packages: CRUD, move, assign, watch.")
app.add_typer(search.app, name="search", help="Powerful work-package (and global) search.")
app.add_typer(comments.app, name="comment", help="Add, edit, list work-package comments.")
app.add_typer(time_entries.app, name="time", help="Log, edit, list time entries + reports.")
app.add_typer(users.app, name="user", help="Users, groups, memberships, assignable people.")
app.add_typer(memberships.app, name="member", help="Project memberships & roles.")
app.add_typer(custom_fields.app, name="cf", help="Inspect custom fields / resource schemas.")
app.add_typer(notifications.app, name="notify", help="In-app notifications.")
app.add_typer(wiki.app, name="wiki", help="Wiki pages (read + write where supported).")
app.add_typer(attachments.app, name="attach", help="Attachments / file uploads on work packages.")
app.add_typer(filelinks.app, name="filelink", help="Nextcloud/file-storage links on work packages.")
app.add_typer(costs.app, name="cost", help="Time & cost reporting per person/project (invoicing).")
app.add_typer(raw.app, name="raw", help="Escape hatch: call any API endpoint directly.")
app.add_typer(settings.app, name="settings", help="View & change CLI settings (default output format).")
app.add_typer(context_cmd.app, name="context", help="Sticky session defaults (project/user/filters) reused across commands.")


def main() -> None:
    import json as _json

    fmt, fields, bools, argv = _pop_globals(sys.argv[1:])
    if fmt is not None:
        os.environ["OPCLI_CLI_FORMAT"] = fmt
    if fields is not None:
        os.environ["OPCLI_CLI_FIELDS"] = fields
    if "dry-run" in bools:
        os.environ["OPCLI_DRY_RUN"] = "1"
    if "stream" in bools:
        os.environ["OPCLI_STREAM"] = "1"
    if "no-context" in bools:
        os.environ["OPCLI_NO_CONTEXT"] = "1"
    try:
        app(args=argv)
    except DryRun as dr:
        # --dry-run: print the request that would have been sent, exit 0.
        sys.stdout.write(_json.dumps({"dryRun": True, "request": dr.request}, indent=2, default=str) + "\n")
        sys.exit(0)
    except OpError as exc:
        print_error(exc, _ERROR_FORMAT)
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:  # pragma: no cover
        print_error(OpError("interrupted"), _ERROR_FORMAT)
        sys.exit(130)


if __name__ == "__main__":  # pragma: no cover
    main()
