"""Project membership commands: list, add, update roles, remove.

A membership links a principal (user/group) to a project with a set of roles.
The ``roles`` link is an ARRAY that *replaces* the whole role set on write.
"""

from __future__ import annotations

import json

import typer

from .. import hal, resolve, serialize
from ..errors import OpError
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ID", "id"),
    ("Principal", lambda r: (r.get("principal") or {}).get("name")),
    ("Project", lambda r: (r.get("project") or {}).get("name")),
    ("Roles", "roles"),
]


@app.command("list")
def list_members(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P", help="Filter by project."),
    user: str = typer.Option(None, "--user", "-u", help="Filter by principal (login/name/id)."),
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum rows (0 = all)."),
) -> None:
    """List memberships."""
    obj = ctx_obj(ctx)
    client = obj.client()
    filters = []
    if project:
        filters.append({"project": {"operator": "=", "values": [str(resolve.project_id(client, project))]}})
    if user:
        href = resolve.user(client, user, project_ref=project)
        filters.append({"principal": {"operator": "=", "values": [str(hal.id_from_href(href))]}})
    params = {"filters": json.dumps(filters)} if filters else {}
    rows = [serialize.membership(m) for m in client.collect("memberships", params=params, limit=limit or None)]
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no memberships)")


def _role_hrefs(client, roles: list[str]) -> list[dict]:
    return [{"href": resolve.role(client, r)} for r in roles]


@app.command()
def add(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project", "-P", help="Project id/identifier."),
    user: str = typer.Option(..., "--user", "-u", help="Principal (login/name/id or 'me')."),
    role: list[str] = typer.Option(..., "--role", "-r", help="Role name (repeatable)."),
) -> None:
    """Add a member to a project with one or more roles.

    Do this before assigning work packages — only project members can be assignees.
    Example: openproject member add --project webshop --user jane.doe --role Member
    """
    obj = ctx_obj(ctx)
    client = obj.client()
    pid = resolve.project_id(client, project)
    principal = resolve.user(client, user, project_ref=project)
    body = {
        "_links": {
            "project": {"href": f"/api/v3/projects/{pid}"},
            "principal": {"href": principal},
            "roles": _role_hrefs(client, role),
        }
    }
    obj.emitter.emit(serialize.membership(client.post("memberships", json=body)))


@app.command()
def update(
    ctx: typer.Context,
    membership_id: int = typer.Argument(..., help="Membership id."),
    role: list[str] = typer.Option(..., "--role", "-r", help="New role set (repeatable; replaces all)."),
) -> None:
    """Replace a membership's roles."""
    obj = ctx_obj(ctx)
    client = obj.client()
    body = {"_links": {"roles": _role_hrefs(client, role)}}
    obj.emitter.emit(serialize.membership(client.patch(f"memberships/{membership_id}", json=body)))


@app.command()
def remove(
    ctx: typer.Context,
    membership_id: int = typer.Argument(..., help="Membership id."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Remove a membership."""
    obj = ctx_obj(ctx)
    if not yes:
        typer.confirm(f"Remove membership {membership_id}?", abort=True)
    obj.client().delete(f"memberships/{membership_id}")
    obj.emitter.emit({"status": "removed", "membership": membership_id})


@app.command()
def roles(ctx: typer.Context) -> None:
    """List available roles."""
    obj = ctx_obj(ctx)
    rows = [{"id": r.get("id"), "name": r.get("name")} for r in obj.client().collect("roles")]
    obj.emitter.emit(rows, columns=[("ID", "id"), ("Name", "name")])
