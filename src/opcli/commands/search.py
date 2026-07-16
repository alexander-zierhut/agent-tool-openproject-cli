"""Powerful, discoverable work-package search.

Three ways to search, easiest first:

1. **Predefined flags** — ``--mine``, ``--overdue``, ``--status open``,
   ``--updated-since 7d``, ``--version v1`` … no JSON needed.
2. **Presets** — ``search mine``, ``search overdue``, ``search recent`` …
3. **``--where``** — compact expressions: ``--where "status = open"``,
   ``--where "assignee:none"``, ``--where "updated > 7d"``.

And to learn what's available:

* ``search fields``    — what you can filter on
* ``search operators`` — what the operator codes mean
* ``search values X``  — allowed values for a field
"""

from __future__ import annotations

import json

import typer

from .. import resolve, searchspec, serialize, wpfilters
from ._shared import ctx_obj, parse_json_option

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ID", "id"),
    ("Type", "type"),
    ("Subject", "subject"),
    ("Status", "status"),
    ("Assignee", lambda r: (r.get("assignee") or {}).get("name")),
    ("Due", "dueDate"),
    ("Updated", "updatedAt"),
]


def _render(obj, client, filters, *, sort, asc, group_by, limit, count, raw):
    params: dict = {"filters": json.dumps(filters), "sortBy": json.dumps([[sort, "asc" if asc else "desc"]])}
    if group_by:
        params["groupBy"] = group_by
    if count:
        params["pageSize"] = 1
        doc = client.get("work_packages", params=params)
        obj.emitter.emit({"total": doc.get("total", 0), "filters": filters})
        return
    if obj.emitter.stream:
        items = client.paginate("work_packages", params=params, limit=limit or None)
        obj.emitter.stream_json(items if raw else (serialize.work_package(w, include_description=False) for w in items))
        return
    elements = client.collect("work_packages", params=params, limit=limit or None)
    if raw:
        obj.emitter.emit(elements)
        return
    rows = [serialize.work_package(w, include_description=False) for w in elements]
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no matches)")


@app.command()
def wp(
    ctx: typer.Context,
    text: str = typer.Argument(None, help="Full-text query (subject/description/comments)."),
    project: str = typer.Option(None, "--project", "-P", help="Restrict to a project."),
    status: str = typer.Option(None, "--status", "-s", help="'open', 'closed', or a status name."),
    open_: bool = typer.Option(False, "--open", help="Only open work packages."),
    closed: bool = typer.Option(False, "--closed", help="Only closed work packages."),
    type_: str = typer.Option(None, "--type", "-t", help="Type name."),
    priority: str = typer.Option(None, "--priority", help="Priority name."),
    assignee: str = typer.Option(None, "--assignee", "-a", help="Assignee (login/name/id or 'me')."),
    mine: bool = typer.Option(False, "--mine", help="Assigned to me."),
    unassigned: bool = typer.Option(False, "--unassigned", help="No assignee."),
    author: str = typer.Option(None, "--author", "--created-by", help="Author (login/name/id or 'me')."),
    responsible: str = typer.Option(None, "--responsible", help="Accountable person."),
    watching: bool = typer.Option(False, "--watching", help="Watched by me."),
    version: str = typer.Option(None, "--version", help="Target version/milestone (name/id)."),
    parent: int = typer.Option(None, "--parent", help="Children of this work-package id."),
    ids: str = typer.Option(None, "--id", help="Specific ids, comma-separated."),
    subject: str = typer.Option(None, "--subject", help="Subject contains (LIKE)."),
    created_since: str = typer.Option(None, "--created-since", help="Created on/after (date or 7d/2w/today)."),
    created_before: str = typer.Option(None, "--created-before", help="Created before (date or spec)."),
    updated_since: str = typer.Option(None, "--updated-since", help="Updated on/after (date or spec)."),
    due_before: str = typer.Option(None, "--due-before", help="Due on/before (date or spec)."),
    due_after: str = typer.Option(None, "--due-after", help="Due on/after (date or spec)."),
    overdue: bool = typer.Option(False, "--overdue", help="Past due and still open."),
    start_after: str = typer.Option(None, "--start-after", help="Starts on/after."),
    start_before: str = typer.Option(None, "--start-before", help="Starts on/before."),
    where: list[str] = typer.Option(None, "--where", "-w", help='Expression e.g. "status = open" (repeatable).'),
    filters_json: str = typer.Option(None, "--filters", help="Raw OpenProject filters JSON (overrides everything)."),
    all_statuses: bool = typer.Option(False, "--all", help="Include closed work packages."),
    sort: str = typer.Option("updatedAt", "--sort", help="Sort field."),
    asc: bool = typer.Option(False, "--asc", help="Ascending (default descending)."),
    group_by: str = typer.Option(None, "--group-by", help="Group column (status/type/assignee/project/priority)."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum rows (0 = all)."),
    count: bool = typer.Option(False, "--count", help="Return only the total match count."),
    raw: bool = typer.Option(False, "--raw", "-r", help="Return raw HAL elements."),
) -> None:
    """Search work packages with rich, plain-language filters."""
    obj = ctx_obj(ctx)
    client = obj.client()

    if filters_json:
        filters = parse_json_option(filters_json, what="--filters")
    else:
        if open_:
            status = "open"
        elif closed:
            status = "closed"
        filters = wpfilters.build(
            client, project=project, status=status, type_=type_, priority=priority,
            assignee=assignee, mine=mine, unassigned=unassigned, author=author,
            responsible=responsible, watching=watching, version=version, parent=parent,
            id_list=ids, query=text, subject=subject,
            created_since=created_since, created_before=created_before,
            updated_since=updated_since, due_before=due_before, due_after=due_after,
            overdue=overdue, start_after=start_after, start_before=start_before,
            where=where, all_statuses=all_statuses,
        )
    _render(obj, client, filters, sort=sort, asc=asc, group_by=group_by, limit=limit, count=count, raw=raw)


# ------------------------------------------------------------- presets
def _preset(ctx, *, sort="updatedAt", asc=False, limit=50, **build_kwargs):
    obj = ctx_obj(ctx)
    client = obj.client()
    filters = wpfilters.build(client, **build_kwargs)
    _render(obj, client, filters, sort=sort, asc=asc, group_by=None, limit=limit, count=False, raw=False)


@app.command()
def mine(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P", help="Restrict to a project."),
    all_statuses: bool = typer.Option(False, "--all", help="Include closed."),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Open work packages assigned to me."""
    _preset(ctx, mine=True, project=project, all_statuses=all_statuses, limit=limit)


@app.command()
def reported(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P"),
    all_statuses: bool = typer.Option(False, "--all"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Work packages I created (authored)."""
    _preset(ctx, author="me", project=project, all_statuses=all_statuses, limit=limit)


@app.command()
def watching(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P"),
    all_statuses: bool = typer.Option(False, "--all"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Work packages I watch."""
    _preset(ctx, watching=True, project=project, all_statuses=all_statuses, limit=limit)


@app.command()
def unassigned(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Open work packages with no assignee."""
    _preset(ctx, unassigned=True, project=project, limit=limit)


@app.command()
def overdue(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Past-due, still-open work packages."""
    _preset(ctx, overdue=True, project=project, sort="dueDate", asc=True, limit=limit)


@app.command()
def recent(
    ctx: typer.Context,
    days: int = typer.Option(7, "--days", "-d", help="Updated within the last N days."),
    project: str = typer.Option(None, "--project", "-P"),
    all_statuses: bool = typer.Option(True, "--all/--open-only", help="Include closed (default yes)."),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Recently updated work packages."""
    _preset(ctx, updated_since=f"{days}d", project=project, all_statuses=all_statuses, limit=limit)


# ------------------------------------------------------- discoverability
@app.command()
def fields(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P", help="Show project-specific filters (incl. its custom fields)."),
) -> None:
    """List what you can filter/search work packages on (live from the instance)."""
    obj = ctx_obj(ctx)
    rows = searchspec.live_fields(obj.client(), project)
    obj.emitter.emit(
        rows,
        columns=[("Field", "field"), ("Kind", "kind"), ("CLI flag", "flag"), ("Description", "description")],
        empty="(no filters)",
    )


@app.command()
def operators(ctx: typer.Context) -> None:
    """Explain the filter operator codes."""
    obj = ctx_obj(ctx)
    rows = [{"operator": code, "meaning": meaning} for code, meaning in searchspec.OPERATORS]
    obj.emitter.emit(rows, columns=[("Operator", "operator"), ("Meaning", "meaning")])


@app.command()
def values(
    ctx: typer.Context,
    field: str = typer.Argument(..., help="Field to list allowed values for (status/type/priority/version/...)."),
    project: str = typer.Option(None, "--project", "-P", help="Project context (versions, assignees, custom fields)."),
    limit: int = typer.Option(100, "--limit", "-n"),
) -> None:
    """List the allowed values for a filterable field."""
    obj = ctx_obj(ctx)
    client = obj.client()
    f = field.strip()
    simple = {"status": "statuses", "type": "types", "priority": "priorities", "project": "projects"}
    rows: list[dict]
    if f in simple:
        rows = [{"id": e.get("id"), "name": e.get("name")} for e in client.collect(simple[f], limit=limit)]
    elif f == "version":
        coll = f"projects/{resolve.project_id(client, project)}/versions" if project else "versions"
        rows = [{"id": e.get("id"), "name": e.get("name")} for e in client.collect(coll, limit=limit)]
    elif f in ("assignee", "author", "responsible", "watcher", "user"):
        if project:
            pid = resolve.project_id(client, project)
            rows = [serialize.principal(p) for p in client.collect(f"projects/{pid}/available_assignees", limit=limit)]
        else:
            rows = [serialize.principal(p) for p in client.collect("principals", limit=limit)]
    elif f.startswith("customField"):
        pid = resolve.project_id(client, project or 1)
        form = client.post(
            f"projects/{pid}/work_packages/form",
            json={"_links": {"project": {"href": f"/api/v3/projects/{pid}"}}},
        )
        spec = ((form.get("_embedded") or {}).get("schema") or {}).get(f) or {}
        allowed = (spec.get("_links") or {}).get("allowedValues") or []
        rows = [{"name": a.get("title"), "href": a.get("href")} for a in allowed]
    else:
        from agentcli.errors import OpError

        raise OpError(
            f"no value list for '{field}'. Try status, type, priority, project, version, assignee, or a customFieldN. "
            f"Free-text/date/number fields take literal values."
        )
    obj.emitter.emit(rows, columns=[("ID", "id"), ("Name", "name")], empty="(no values)")
