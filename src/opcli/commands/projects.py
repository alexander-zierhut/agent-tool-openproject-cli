"""Project commands: list, get, create, update, archive, unarchive, delete."""

from __future__ import annotations

import json

import typer

from .. import hal, resolve, serialize
from agentcli.errors import OpError
from ._shared import apply_custom_fields, ctx_obj, set_link

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ID", "id"),
    ("Identifier", "identifier"),
    ("Name", "name"),
    ("Active", "active"),
    ("Public", "public"),
]


@app.command("list")
def list_projects(
    ctx: typer.Context,
    active: bool = typer.Option(None, "--active/--archived", help="Filter by active state."),
    filters: str = typer.Option(None, "--filters", help="Raw OpenProject filters JSON (overrides --active)."),
    sort: str = typer.Option("name", "--sort", help="Sort column (e.g. name, id, created_at)."),
    limit: int = typer.Option(None, "--limit", "-n", help="Maximum rows."),
) -> None:
    """List projects (active by default include all unless filtered)."""
    obj = ctx_obj(ctx)
    params: dict = {"sortBy": json.dumps([[sort, "asc"]])}
    if filters:
        params["filters"] = filters
    elif active is not None:
        params["filters"] = json.dumps([{"active": {"operator": "=", "values": ["t" if active else "f"]}}])
    rows = [serialize.project(p) for p in obj.client().collect("projects", params=params, limit=limit)]
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no projects)")


@app.command()
def get(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project id or identifier."),
    raw: bool = typer.Option(False, "--raw", "-r", help="Return the full HAL document."),
    attributes: bool = typer.Option(
        False, "--attributes", "-a",
        help="Resolve project custom fields to their human names, types and values.",
    ),
) -> None:
    """Show a single project.

    With ``--attributes`` the project's custom fields are joined to their human
    names and types (and CustomOption values resolved to titles), so you don't
    have to read the definitions with ``cf project`` and map ``customFieldNN`` by
    hand. ``--raw`` wins over ``--attributes`` (returns the untouched HAL doc).
    """
    obj = ctx_obj(ctx)
    client = obj.client()
    doc = resolve.project(client, project)
    if raw:
        obj.emitter.emit(doc)
        return
    schema = resolve.project_form_schema(client, doc.get("id")) if attributes else None
    obj.emitter.emit(serialize.project(doc, schema=schema))


@app.command()
def create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Project name."),
    identifier: str = typer.Option(None, "--identifier", help="URL identifier (auto from name if omitted)."),
    description: str = typer.Option(None, "--description", "-d", help="Description (markdown)."),
    parent: str = typer.Option(None, "--parent", help="Parent project id/identifier."),
    public: bool = typer.Option(False, "--public", help="Make the project public."),
    custom_fields: str = typer.Option(None, "--custom-fields", help='JSON of customFieldN values.'),
) -> None:
    """Create a project."""
    obj = ctx_obj(ctx)
    client = obj.client()
    body: dict = {"name": name, "public": public}
    if identifier:
        body["identifier"] = identifier
    if description is not None:
        body["description"] = {"raw": description}
    if parent:
        set_link(body, "parent", f"/api/v3/projects/{resolve.project_id(client, parent)}")
    apply_custom_fields(body, custom_fields)
    doc = client.post("projects", json=body)
    obj.emitter.emit(serialize.project(doc))


@app.command()
def update(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project id or identifier."),
    name: str = typer.Option(None, "--name", help="New name."),
    identifier: str = typer.Option(None, "--identifier", help="New identifier."),
    description: str = typer.Option(None, "--description", "-d", help="New description."),
    parent: str = typer.Option(None, "--parent", help="New parent id/identifier ('none' to detach)."),
    public: bool = typer.Option(None, "--public/--private", help="Public flag."),
    custom_fields: str = typer.Option(None, "--custom-fields", help="JSON of customFieldN values."),
) -> None:
    """Update project attributes (no lockVersion needed for projects)."""
    obj = ctx_obj(ctx)
    client = obj.client()
    pid = resolve.project_id(client, project)
    body: dict = {}
    if name is not None:
        body["name"] = name
    if identifier is not None:
        body["identifier"] = identifier
    if description is not None:
        body["description"] = {"raw": description}
    if public is not None:
        body["public"] = public
    if parent is not None:
        if parent.lower() == "none":
            set_link(body, "parent", None)
        else:
            set_link(body, "parent", f"/api/v3/projects/{resolve.project_id(client, parent)}")
    apply_custom_fields(body, custom_fields)
    if not body:
        raise OpError("nothing to update — pass at least one field")
    doc = client.patch(f"projects/{pid}", json=body)
    obj.emitter.emit(serialize.project(doc))


def _set_active(ctx: typer.Context, project: str, active: bool) -> None:
    obj = ctx_obj(ctx)
    client = obj.client()
    pid = resolve.project_id(client, project)
    doc = client.patch(f"projects/{pid}", json={"active": active})
    obj.emitter.emit(serialize.project(doc))


@app.command()
def archive(ctx: typer.Context, project: str = typer.Argument(..., help="Project id/identifier.")) -> None:
    """Archive a project (PATCH active=false)."""
    _set_active(ctx, project, False)


@app.command()
def unarchive(ctx: typer.Context, project: str = typer.Argument(..., help="Project id/identifier.")) -> None:
    """Restore an archived project (PATCH active=true)."""
    _set_active(ctx, project, True)


@app.command()
def delete(
    ctx: typer.Context,
    project: str = typer.Argument(..., help="Project id or identifier."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Permanently delete a project (asynchronous on the server)."""
    obj = ctx_obj(ctx)
    client = obj.client()
    pid = resolve.project_id(client, project)
    if not yes:
        typer.confirm(f"Delete project {pid}? This cannot be undone.", abort=True)
    client.delete(f"projects/{pid}")
    obj.emitter.emit({"status": "delete requested", "project": pid})
