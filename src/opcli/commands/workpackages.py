"""Work-package commands: CRUD, move, assign, watchers, schema."""

from __future__ import annotations

import json

import typer

from .. import hal, resolve, serialize, wpfilters
from ..duration import parse_hours_input
from ..errors import OpError
from ._shared import apply_custom_fields, ctx_obj, parse_json_option, set_link

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ID", "id"),
    ("Type", "type"),
    ("Subject", "subject"),
    ("Status", "status"),
    ("Assignee", lambda r: (r.get("assignee") or {}).get("name")),
    ("Project", lambda r: (r.get("project") or {}).get("name")),
]


# --------------------------------------------------------------------- list
@app.command("list")
def list_wps(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P", help="Project id/identifier."),
    status: str = typer.Option(None, "--status", "-s", help="'open', 'closed', or a status name."),
    type_: str = typer.Option(None, "--type", "-t", help="Work-package type name."),
    assignee: str = typer.Option(None, "--assignee", "-a", help="Assignee (login/name/id or 'me')."),
    mine: bool = typer.Option(False, "--mine", help="Assigned to me."),
    unassigned: bool = typer.Option(False, "--unassigned", help="No assignee."),
    author: str = typer.Option(None, "--author", "--created-by", help="Author (login/name/id or 'me')."),
    priority: str = typer.Option(None, "--priority", help="Priority name."),
    version: str = typer.Option(None, "--version", help="Target version (name/id)."),
    overdue: bool = typer.Option(False, "--overdue", help="Past due and still open."),
    updated_since: str = typer.Option(None, "--updated-since", help="Updated since (date or 7d/today)."),
    due_before: str = typer.Option(None, "--due-before", help="Due on/before (date or spec)."),
    query: str = typer.Option(None, "--query", "-q", help="Full-text search (subject/description/comments)."),
    where: list[str] = typer.Option(None, "--where", "-w", help='Expression filter, e.g. "status = open" (repeatable).'),
    all_statuses: bool = typer.Option(False, "--all", help="Include closed (disable default open filter)."),
    sort: str = typer.Option("id", "--sort", help="Sort field, e.g. id, updatedAt, dueDate."),
    desc: bool = typer.Option(False, "--desc", help="Sort descending."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum rows (0 = all)."),
) -> None:
    """List / filter work packages (global, scoped by filters). See `search wp` for the full set."""
    obj = ctx_obj(ctx)
    client = obj.client()
    filters = wpfilters.build(
        client, project=project, status=status, type_=type_, assignee=assignee,
        mine=mine, unassigned=unassigned, author=author, priority=priority, version=version,
        overdue=overdue, updated_since=updated_since, due_before=due_before,
        query=query, where=where, all_statuses=all_statuses,
    )
    params = {
        "filters": wpfilters.encode(filters),
        "sortBy": json.dumps([[sort, "desc" if desc else "asc"]]),
    }
    if obj.emitter.stream:
        items = client.paginate("work_packages", params=params, limit=limit or None)
        obj.emitter.stream_json(serialize.work_package(w, include_description=False) for w in items)
        return
    rows = [
        serialize.work_package(w, include_description=False)
        for w in client.collect("work_packages", params=params, limit=limit or None)
    ]
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no work packages)")


# ---------------------------------------------------------------------- get
@app.command()
def get(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    raw: bool = typer.Option(False, "--raw", "-r", help="Return the full HAL document."),
) -> None:
    """Show one work package."""
    obj = ctx_obj(ctx)
    doc = obj.client().get(f"work_packages/{wp_id}")
    obj.emitter.emit(doc if raw else serialize.work_package(doc))


# ------------------------------------------------------------------- create
@app.command()
def create(
    ctx: typer.Context,
    subject: str = typer.Argument(..., help="Work package subject/title."),
    project: str = typer.Option(..., "--project", "-P", help="Project id/identifier."),
    type_: str = typer.Option("Task", "--type", "-t", help="Type name (default Task)."),
    description: str = typer.Option(None, "--description", "-d", help="Description (markdown)."),
    status: str = typer.Option(None, "--status", "-s", help="Initial status name."),
    priority: str = typer.Option(None, "--priority", help="Priority name."),
    assignee: str = typer.Option(None, "--assignee", "-a", help="Assignee (login/name/id or 'me')."),
    responsible: str = typer.Option(None, "--responsible", help="Accountable user."),
    parent: int = typer.Option(None, "--parent", help="Parent work package id."),
    start_date: str = typer.Option(None, "--start-date", help="YYYY-MM-DD."),
    due_date: str = typer.Option(None, "--due-date", help="YYYY-MM-DD."),
    estimated: str = typer.Option(None, "--estimated", help="Estimated time (hours or ISO8601)."),
    custom_fields: str = typer.Option(None, "--custom-fields", help="JSON of customFieldN values."),
    set_: str = typer.Option(None, "--set", help="Raw JSON merged into the create body."),
    notify: bool = typer.Option(False, "--notify", help="Send notifications for this create."),
) -> None:
    """Create a work package. Pass names (type/status/priority/assignee) — they're resolved.

    Example: openproject wp create "Fix login" --project webshop --type Bug --assignee me --priority High
    Custom fields: --custom-fields '{"customField1":"INV-1"}' (discover them with `cf wp`).
    Note: the assignee must be a member of the project (see `member add`).
    """
    obj = ctx_obj(ctx)
    client = obj.client()
    pid = resolve.project_id(client, project)

    body: dict = {"subject": subject, "_links": {}}
    set_link(body, "project", f"/api/v3/projects/{pid}")
    set_link(body, "type", resolve.wp_type(client, type_))
    if description is not None:
        body["description"] = {"raw": description}
    if status:
        set_link(body, "status", resolve.status(client, status))
    if priority:
        set_link(body, "priority", resolve.priority(client, priority))
    if assignee:
        set_link(body, "assignee", resolve.user(client, assignee, project_ref=project))
    if responsible:
        set_link(body, "responsible", resolve.user(client, responsible, project_ref=project))
    if parent:
        set_link(body, "parent", f"/api/v3/work_packages/{parent}")
    if start_date:
        body["startDate"] = start_date
    if due_date:
        body["dueDate"] = due_date
    if estimated:
        body["estimatedTime"] = parse_hours_input(estimated)
    apply_custom_fields(body, custom_fields)
    if set_:
        extra = parse_json_option(set_, what="--set")
        if isinstance(extra, dict):
            body.update({k: v for k, v in extra.items() if k != "_links"})
            body["_links"].update(extra.get("_links", {}))

    doc = client.post("work_packages", json=body, params={"notify": str(notify).lower()})
    obj.emitter.emit(serialize.work_package(doc))


# ------------------------------------------------------------------- update
@app.command()
def update(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    subject: str = typer.Option(None, "--subject", help="New subject."),
    description: str = typer.Option(None, "--description", "-d", help="New description."),
    status: str = typer.Option(None, "--status", "-s", help="New status name."),
    type_: str = typer.Option(None, "--type", "-t", help="New type name."),
    priority: str = typer.Option(None, "--priority", help="New priority."),
    assignee: str = typer.Option(None, "--assignee", "-a", help="Assignee ('none' to clear)."),
    responsible: str = typer.Option(None, "--responsible", help="Accountable ('none' to clear)."),
    parent: str = typer.Option(None, "--parent", help="Parent id ('none' to detach)."),
    start_date: str = typer.Option(None, "--start-date", help="YYYY-MM-DD."),
    due_date: str = typer.Option(None, "--due-date", help="YYYY-MM-DD."),
    estimated: str = typer.Option(None, "--estimated", help="Estimated time (hours or ISO8601)."),
    done_ratio: int = typer.Option(None, "--done-ratio", help="Percentage done 0-100."),
    custom_fields: str = typer.Option(None, "--custom-fields", help="JSON of customFieldN values."),
    set_: str = typer.Option(None, "--set", help="Raw JSON merged into the patch body."),
    notify: bool = typer.Option(False, "--notify", help="Send notifications for this change."),
) -> None:
    """Update a work package. lockVersion is fetched and retried automatically.

    Example: openproject wp update 42 --status "In progress" --assignee jane.doe --done-ratio 50
    Clear a link with the value 'none' (e.g. --assignee none). Use --set '{...}' for arbitrary fields.
    """
    obj = ctx_obj(ctx)
    client = obj.client()

    body: dict = {"_links": {}}
    if subject is not None:
        body["subject"] = subject
    if description is not None:
        body["description"] = {"raw": description}
    if start_date is not None:
        body["startDate"] = start_date
    if due_date is not None:
        body["dueDate"] = due_date
    if estimated is not None:
        body["estimatedTime"] = parse_hours_input(estimated)
    if done_ratio is not None:
        body["percentageDone"] = done_ratio
    if status:
        set_link(body, "status", resolve.status(client, status))
    if type_:
        set_link(body, "type", resolve.wp_type(client, type_))
    if priority:
        set_link(body, "priority", resolve.priority(client, priority))
    if assignee is not None:
        set_link(body, "assignee", None if assignee.lower() == "none" else resolve.user(client, assignee))
    if responsible is not None:
        set_link(body, "responsible", None if responsible.lower() == "none" else resolve.user(client, responsible))
    if parent is not None:
        set_link(body, "parent", None if parent.lower() == "none" else f"/api/v3/work_packages/{parent}")
    apply_custom_fields(body, custom_fields)
    if set_:
        extra = parse_json_option(set_, what="--set")
        if isinstance(extra, dict):
            body.update({k: v for k, v in extra.items() if k != "_links"})
            body["_links"].update(extra.get("_links", {}))
    if not body.get("_links"):
        body.pop("_links")
    if not body:
        raise OpError("nothing to update — pass at least one field")

    doc = client.update_locked(f"work_packages/{wp_id}", body, params={"notify": str(notify).lower()})
    obj.emitter.emit(serialize.work_package(doc))


# --------------------------------------------------------------------- move
@app.command()
def move(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    project: str = typer.Argument(..., help="Destination project id/identifier."),
    type_: str = typer.Option(None, "--type", "-t", help="New type (if not valid in target project)."),
) -> None:
    """Move a work package to another project."""
    obj = ctx_obj(ctx)
    client = obj.client()
    pid = resolve.project_id(client, project)
    body: dict = {"_links": {"project": {"href": f"/api/v3/projects/{pid}"}}}
    if type_:
        body["_links"]["type"] = {"href": resolve.wp_type(client, type_)}
    doc = client.update_locked(f"work_packages/{wp_id}", body)
    obj.emitter.emit(serialize.work_package(doc))


# ------------------------------------------------------------------- delete
@app.command()
def delete(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Delete a work package."""
    obj = ctx_obj(ctx)
    if not yes:
        typer.confirm(f"Delete work package {wp_id}?", abort=True)
    obj.client().delete(f"work_packages/{wp_id}")
    obj.emitter.emit({"status": "deleted", "workPackage": wp_id})


# ------------------------------------------------------- assignee shortcuts
@app.command()
def assign(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    user: str = typer.Argument(..., help="Assignee (login/name/id or 'me'; 'none' to unassign)."),
) -> None:
    """Set (or clear with 'none') the assignee."""
    obj = ctx_obj(ctx)
    client = obj.client()
    href = None if user.lower() == "none" else resolve.user(client, user)
    doc = client.update_locked(f"work_packages/{wp_id}", {"_links": {"assignee": {"href": href}}})
    obj.emitter.emit(serialize.work_package(doc))


@app.command()
def unassign(ctx: typer.Context, wp_id: int = typer.Argument(..., help="Work package id.")) -> None:
    """Remove the assignee."""
    obj = ctx_obj(ctx)
    doc = obj.client().update_locked(f"work_packages/{wp_id}", {"_links": {"assignee": {"href": None}}})
    obj.emitter.emit(serialize.work_package(doc))


@app.command()
def assignees(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
) -> None:
    """List users assignable to this work package."""
    obj = ctx_obj(ctx)
    rows = [serialize.principal(p) for p in obj.client().collect(f"work_packages/{wp_id}/available_assignees")]
    obj.emitter.emit(rows, columns=[("ID", "id"), ("Name", "name"), ("Login", "login"), ("Type", "type")])


# ----------------------------------------------------------------- watchers
@app.command()
def watchers(ctx: typer.Context, wp_id: int = typer.Argument(..., help="Work package id.")) -> None:
    """List watchers of a work package."""
    obj = ctx_obj(ctx)
    rows = [serialize.principal(p) for p in obj.client().collect(f"work_packages/{wp_id}/watchers")]
    obj.emitter.emit(rows, columns=[("ID", "id"), ("Name", "name"), ("Login", "login")])


@app.command()
def watch(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    user: str = typer.Argument("me", help="User to add as watcher (default: me)."),
) -> None:
    """Add a watcher (note: body key is 'user', not under _links)."""
    obj = ctx_obj(ctx)
    client = obj.client()
    href = resolve.user(client, user)
    client.post(f"work_packages/{wp_id}/watchers", json={"user": {"href": href}})
    obj.emitter.emit({"status": "watching", "workPackage": wp_id, "user": href})


@app.command()
def unwatch(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    user: str = typer.Argument("me", help="User to remove (default: me)."),
) -> None:
    """Remove a watcher."""
    obj = ctx_obj(ctx)
    client = obj.client()
    href = resolve.user(client, user)
    uid = hal.id_from_href(href)
    client.delete(f"work_packages/{wp_id}/watchers/{uid}")
    obj.emitter.emit({"status": "unwatched", "workPackage": wp_id, "user": uid})


# ------------------------------------------------------------------- schema
@app.command()
def schema(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project", "-P", help="Project id/identifier."),
    type_: str = typer.Option("Task", "--type", "-t", help="Type name."),
) -> None:
    """Discover the create schema (fields, required flags, custom fields) via the form."""
    obj = ctx_obj(ctx)
    client = obj.client()
    pid = resolve.project_id(client, project)
    body = {"_links": {"project": {"href": f"/api/v3/projects/{pid}"}, "type": {"href": resolve.wp_type(client, type_)}}}
    form = client.post(f"projects/{pid}/work_packages/form", json=body)
    sch = (form.get("_embedded") or {}).get("schema") or {}
    fields = [
        serialize.custom_field_schema(name, spec)
        for name, spec in sch.items()
        if isinstance(spec, dict) and spec.get("type")
    ]
    obj.emitter.emit(fields, columns=[("Key", "key"), ("Name", "name"), ("Type", "type"), ("Required", "required"), ("Writable", "writable")])
