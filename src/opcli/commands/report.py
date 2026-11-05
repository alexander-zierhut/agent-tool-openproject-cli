"""`report` — where and how to file an issue against this tool, offline.

There is no README or AGENTS.md beside an installed binary, so the tool has to
carry its own "report a problem" answer. This command reaches no network, reads
no config and needs no token: it prints this tool's repo and a pre-filled GitHub
``issues/new`` link (opening the form needs no account), plus a ``gh`` one-liner.
Like ``guide``, it must be impossible to fail on config or auth — keep it inert.
"""

from __future__ import annotations

import dataclasses

import typer

from agentcli import build_report

from .. import __version__
from ..spec import SPEC
from ._shared import ctx_obj


def report(ctx: typer.Context) -> None:
    """How to report a bug or missing feature in this tool — offline.

    Prints the repository, a pre-filled issue link (no account needed to open the
    form) and a ``gh issue create`` one-liner. Use it when a task was painful,
    needed too many steps, or was impossible: run it, then file what it shows.
    """
    # SPEC.name ("op-cli") is the config-dir / keyring-service name and must stay
    # that way, or existing logins vanish. The report, though, has to name the
    # command a user actually types (`openproject --version`, `openproject report`).
    ctx_obj(ctx).emitter.emit(build_report(dataclasses.replace(SPEC, name="openproject"), __version__))
