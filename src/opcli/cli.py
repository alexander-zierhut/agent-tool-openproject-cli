"""Top-level Typer application wiring together every command group."""

from __future__ import annotations

import os
import sys

import typer

from .context import AppContext
from .errors import OpError
from .output import OutputFormat, print_error

app = typer.Typer(
    name="openproject",
    help="Agent-friendly CLI for OpenProject. JSON output by default; use `-o table` for humans.",
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
    no_color: bool = typer.Option(False, "--no-color", help="Disable coloured output."),
) -> None:
    if profile:
        os.environ["OPCLI_PROFILE"] = profile
    # Don't prompt for a default format when the user is managing settings.
    interactive = ctx.invoked_subcommand != "settings" and sys.stdin.isatty() and sys.stdout.isatty()
    ctx.obj = AppContext(output=output, color=not no_color, interactive=interactive)
    global _ERROR_FORMAT
    _ERROR_FORMAT = ctx.obj.emitter.fmt


_FORMAT_FLAGS = ("--format", "-f", "--output", "-o")
_FIELDS_FLAGS = ("--fields", "--columns")


def _pop_globals(argv: list[str]) -> tuple[str | None, str | None, list[str]]:
    """Extract the output-format and --fields flags (with values) from anywhere on
    the command line, so they work *after* a subcommand too — e.g.
    ``openproject wp list -f markdown --fields id,subject``. Honours ``--``."""
    out: list[str] = []
    fmt: str | None = None
    fields: str | None = None
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
        elif not stop and (a.startswith("--format=") or a.startswith("--output=") or a.startswith("-f=") or a.startswith("-o=")):
            fmt = a.split("=", 1)[1]
        elif not stop and (a.startswith("--fields=") or a.startswith("--columns=")):
            fields = a.split("=", 1)[1]
        else:
            out.append(a)
        i += 1
    return fmt, fields, out


# ---- command groups (registered below to avoid circular imports) ----
from .commands import (  # noqa: E402
    attachments,
    auth,
    comments,
    costs,
    custom_fields,
    filelinks,
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


def main() -> None:
    fmt, fields, argv = _pop_globals(sys.argv[1:])
    if fmt is not None:
        os.environ["OPCLI_CLI_FORMAT"] = fmt
    if fields is not None:
        os.environ["OPCLI_CLI_FIELDS"] = fields
    try:
        app(args=argv)
    except OpError as exc:
        print_error(exc, _ERROR_FORMAT)
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:  # pragma: no cover
        print_error(OpError("interrupted"), _ERROR_FORMAT)
        sys.exit(130)


if __name__ == "__main__":  # pragma: no cover
    main()
