"""User / principal commands: list, get, me, available assignees, groups."""

from __future__ import annotations

import json

import typer

from .. import resolve, serialize
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ID", "id"),
    ("Login", "login"),
    ("Name", "name"),
    ("Email", "email"),
    ("Status", "status"),
    ("Admin", "admin"),
]


@app.command("list")
def list_users(
    ctx: typer.Context,
    status: str = typer.Option(None, "--status", help="Filter by status (active, locked, invited...)."),
    name: str = typer.Option(None, "--name", help="Name/login substring filter."),
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum rows (0 = all)."),
) -> None:
    """List users (requires admin permission on most instances)."""
    obj = ctx_obj(ctx)
    filters = []
    if status:
        filters.append({"status": {"operator": "=", "values": [status]}})
    if name:
        filters.append({"name": {"operator": "~", "values": [name]}})
    params = {"filters": json.dumps(filters)} if filters else {}
    rows = [serialize.user(u) for u in obj.client().collect("users", params=params, limit=limit or None)]
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no users)")


@app.command()
def get(
    ctx: typer.Context,
    user: str = typer.Argument(..., help="User id, login, or 'me'."),
    raw: bool = typer.Option(False, "--raw", "-r", help="Return the full HAL document."),
) -> None:
    """Show a single user."""
    obj = ctx_obj(ctx)
    client = obj.client()
    href = resolve.user(client, user)
    doc = client.get(href)
    obj.emitter.emit(doc if raw else serialize.user(doc))


@app.command()
def create(
    ctx: typer.Context,
    login: str = typer.Argument(..., help="Login/username."),
    email: str = typer.Option(..., "--email", "-e", help="Email address."),
    first_name: str = typer.Option(..., "--first-name", help="First name."),
    last_name: str = typer.Option(..., "--last-name", help="Last name."),
    password: str = typer.Option(None, "--password", help="Initial password (else invite/status)."),
    status: str = typer.Option("active", "--status", help="active | invited | registered."),
    admin: bool = typer.Option(False, "--admin", help="Grant admin."),
) -> None:
    """Create a user (requires admin)."""
    obj = ctx_obj(ctx)
    body: dict = {
        "login": login,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "admin": admin,
        "status": status,
    }
    if password:
        body["password"] = password
        body["status"] = "active"
    obj.emitter.emit(serialize.user(obj.client().post("users", json=body)))


@app.command()
def me(ctx: typer.Context) -> None:
    """Show the authenticated user."""
    obj = ctx_obj(ctx)
    obj.emitter.emit(serialize.user(obj.client().me()))


@app.command()
def available(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project id/identifier."),
) -> None:
    """List users assignable within a project (available assignees)."""
    obj = ctx_obj(ctx)
    client = obj.client()
    pid = resolve.project_id(client, project)
    rows = [serialize.principal(p) for p in client.collect(f"projects/{pid}/available_assignees")]
    obj.emitter.emit(rows, columns=[("ID", "id"), ("Name", "name"), ("Login", "login"), ("Type", "type")])


@app.command()
def groups(ctx: typer.Context) -> None:
    """List groups."""
    obj = ctx_obj(ctx)
    rows = [{"id": g.get("id"), "name": g.get("name")} for g in obj.client().collect("groups")]
    obj.emitter.emit(rows, columns=[("ID", "id"), ("Name", "name")])
