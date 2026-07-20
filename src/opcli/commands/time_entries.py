"""Time-entry commands: log, edit, list, delete, activities, and reporting.

Time-entry filters use snake_case names (``user_id``, ``project_id``,
``entity_type``/``entity_id``, ``spent_on``) — different from work-package
filters. ``hours`` is an ISO-8601 duration; we accept decimals and convert.
Time entries have no lockVersion.
"""

from __future__ import annotations

import datetime as _dt
import json

import typer

from .. import hal, resolve, serialize
from ..duration import iso_to_hours, parse_hours_input
from agentcli.errors import ApiError, OpError, ValidationError
from ._shared import apply_custom_fields, ctx_obj, set_link

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ID", "id"),
    ("Date", "spentOn"),
    ("Hours", lambda r: iso_to_hours(r.get("hours"))),
    ("User", lambda r: (r.get("user") or {}).get("name")),
    ("WorkPkg", lambda r: (r.get("workPackage") or {}).get("id")),
    ("Activity", "activity"),
    ("Comment", "comment"),
]


def _month_range(month: str) -> tuple[str, str]:
    year, mon = (int(x) for x in month.split("-"))
    first = _dt.date(year, mon, 1)
    nxt = _dt.date(year + (mon == 12), (mon % 12) + 1, 1)
    last = nxt - _dt.timedelta(days=1)
    return first.isoformat(), last.isoformat()


def _build_filters(client, *, user, project, work_package, frm, to, month, wp_style="work_package_id") -> list[dict]:
    filters: list[dict] = []
    if month:
        frm, to = _month_range(month)
    if user:
        href = resolve.user(client, user, project_ref=project)
        filters.append({"user_id": {"operator": "=", "values": [str(hal.id_from_href(href))]}})
    if project:
        filters.append({"project_id": {"operator": "=", "values": [str(resolve.project_id(client, project))]}})
    if work_package:
        if wp_style == "entity":
            filters.append({"entity_type": {"operator": "=", "values": ["WorkPackage"]}})
            filters.append({"entity_id": {"operator": "=", "values": [str(work_package)]}})
        else:
            filters.append({"work_package_id": {"operator": "=", "values": [str(work_package)]}})
    if frm and to:
        filters.append({"spent_on": {"operator": "<>d", "values": [frm, to]}})
    elif frm:
        # single-sided: use the between operator with an empty upper bound
        # (>=d/<=d are not valid OpenProject operator codes).
        filters.append({"spent_on": {"operator": "<>d", "values": [frm, ""]}})
    elif to:
        filters.append({"spent_on": {"operator": "<>d", "values": ["", to]}})
    return filters


def query_time_entries(client, *, user=None, project=None, work_package=None, frm=None, to=None,
                       month=None, sort="spent_on", desc=True, limit=None) -> list[dict]:
    """Fetch time entries, tolerating the work-package-filter name difference
    across OpenProject versions (``work_package_id`` vs ``entity_type``/``entity_id``)."""
    styles = ("work_package_id", "entity") if work_package else ("work_package_id",)
    last: Exception | None = None
    for style in styles:
        filters = _build_filters(client, user=user, project=project, work_package=work_package,
                                 frm=frm, to=to, month=month, wp_style=style)
        params = {"sortBy": json.dumps([[sort, "desc" if desc else "asc"]])}
        if filters:
            params["filters"] = json.dumps(filters)
        try:
            return client.collect("time_entries", params=params, limit=limit)
        except (ApiError, ValidationError) as exc:
            last = exc
            if work_package and "does not exist" in (exc.message or "").lower():
                continue
            raise
    if last:
        raise last
    return []


_GROUP_DIMS = {"user": "user", "activity": "activity", "workpackage": "workPackage", "wp": "workPackage"}


def _norm_group_by(value: str) -> str:
    """Normalise ``--group-by`` (case-insensitive, `-`/`_` ignored) to a canonical
    dimension, or raise a usage error listing the valid choices."""
    key = value.strip().lower().replace("-", "").replace("_", "")
    if key not in _GROUP_DIMS:
        raise OpError("--group-by must be one of: user, activity, workPackage")
    return _GROUP_DIMS[key]


def _group_rows(rows: list[dict], dim: str) -> list[dict]:
    """Sum decimal hours per group. `dim` is user | activity | workPackage."""
    buckets: dict = {}
    for r in rows:
        h = r.get("hoursDecimal") or 0.0
        if dim == "activity":
            val = r.get("activity")
            key, label = val, (val or "(none)")
        else:
            ref = r.get(dim) or None
            key = ref.get("id") if ref else None
            val = ref
            label = (ref or {}).get("name") or "(none)"
        b = buckets.get(key)
        if b is None:
            b = buckets[key] = {"value": val, "label": label, "hours": 0.0, "entries": 0}
        b["hours"] += h
        b["entries"] += 1
    out = sorted(buckets.values(), key=lambda b: (-b["hours"], (b["label"] or "").lower()))
    return [{dim: b["value"], "hours": round(b["hours"], 2), "entries": b["entries"]} for b in out]


def _group_columns(dim: str) -> list:
    tail = [("Hours", "hours"), ("Entries", "entries")]
    if dim == "user":
        return [("User", lambda r: (r.get("user") or {}).get("name"))] + tail
    if dim == "activity":
        return [("Activity", "activity")] + tail
    return [
        ("WorkPkg", lambda r: (r.get("workPackage") or {}).get("id")),
        ("Subject", lambda r: (r.get("workPackage") or {}).get("name")),
    ] + tail


@app.command("list")
def list_entries(
    ctx: typer.Context,
    user: str = typer.Option(None, "--user", "-u", help="Filter by user (login/name/id or 'me')."),
    project: str = typer.Option(None, "--project", "-P", help="Filter by project."),
    work_package: int = typer.Option(None, "--work-package", "-w", help="Filter by work package id."),
    frm: str = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)."),
    to: str = typer.Option(None, "--to", help="End date (YYYY-MM-DD)."),
    month: str = typer.Option(None, "--month", help="Convenience month filter YYYY-MM."),
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum rows (0 = all). Ignored with --sum/--group-by (they scan all matches)."),
    sum_: bool = typer.Option(False, "--sum", help="Return the total decimal hours (and entry count) instead of the entry list."),
    group_by: str = typer.Option(None, "--group-by", help="Aggregate hours by user, activity, or workPackage (combine with --sum for a grand total)."),
) -> None:
    """List time entries, or aggregate them.

    Plain: one row per entry. ``--sum``: a single ``{totalHours, entries}``.
    ``--group-by user|activity|workPackage``: per-group subtotals; add ``--sum``
    to also get the grand total in a wrapper. Aggregation scans all matches,
    ignoring ``--limit``.
    """
    obj = ctx_obj(ctx)
    client = obj.client()
    dim = _norm_group_by(group_by) if group_by else None
    aggregating = sum_ or dim is not None
    entries = query_time_entries(client, user=user, project=project, work_package=work_package,
                                 frm=frm, to=to, month=month, limit=None if aggregating else (limit or None))
    rows = [serialize.time_entry(t) for t in entries]

    if aggregating:
        total = round(sum((r.get("hoursDecimal") or 0.0) for r in rows), 2)
        n = len(rows)
        if dim and sum_:
            obj.emitter.emit({"groupBy": dim, "groups": _group_rows(rows, dim), "totalHours": total, "entries": n})
        elif dim:
            groups = _group_rows(rows, dim)
            if obj.emitter.stream:  # --group-by is a row list, so it can stream as NDJSON
                obj.emitter.stream_json(groups)
            else:
                obj.emitter.emit(groups, columns=_group_columns(dim), empty="(no time entries)")
        else:
            obj.emitter.emit({"totalHours": total, "entries": n})
        return

    if obj.emitter.stream:
        obj.emitter.stream_json(rows)
        return
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no time entries)")


@app.command()
def get(ctx: typer.Context, entry_id: int = typer.Argument(..., help="Time entry id.")) -> None:
    """Show a single time entry."""
    obj = ctx_obj(ctx)
    obj.emitter.emit(serialize.time_entry(obj.client().get(f"time_entries/{entry_id}")))


@app.command()
def add(
    ctx: typer.Context,
    hours: str = typer.Argument(..., help="Hours (decimal like 2.5 or ISO8601 like PT2H30M)."),
    work_package: int = typer.Option(None, "--work-package", "-w", help="Work package id to log against."),
    project: str = typer.Option(None, "--project", "-P", help="Project id/identifier (if not logging on a WP)."),
    spent_on: str = typer.Option(None, "--date", help="Date YYYY-MM-DD (default today)."),
    activity: str = typer.Option(None, "--activity", help="Activity name (e.g. Development)."),
    comment: str = typer.Option(None, "--comment", "-m", help="Comment."),
    user: str = typer.Option(None, "--user", "-u", help="Log on behalf of another user (needs permission)."),
    custom_fields: str = typer.Option(None, "--custom-fields", help="JSON of customFieldN values (see `cf time`)."),
) -> None:
    """Log a time entry. Hours accept decimals (2.5) or ISO-8601 (PT2H30M).

    Example: openproject time add 2.5 --work-package 42 --activity Development --comment "debugging"
    Provide --work-package OR --project. Date defaults to today (`--date 2026-07-10`).
    """
    obj = ctx_obj(ctx)
    client = obj.client()
    if not work_package and not project:
        raise OpError("provide --work-package or --project")

    body: dict = {
        "hours": parse_hours_input(hours),
        "spentOn": spent_on or _dt.date.today().isoformat(),
        "_links": {},
    }
    if work_package:
        set_link(body, "workPackage", f"/api/v3/work_packages/{work_package}")
    if project:
        set_link(body, "project", f"/api/v3/projects/{resolve.project_id(client, project)}")
    if activity:
        set_link(body, "activity", resolve.time_activity(client, activity, project_ref=project, wp_id=work_package))
    if comment is not None:
        body["comment"] = {"raw": comment}
    if user:
        set_link(body, "user", resolve.user(client, user, project_ref=project))
    apply_custom_fields(body, custom_fields)

    obj.emitter.emit(serialize.time_entry(client.post("time_entries", json=body)))


@app.command()
def edit(
    ctx: typer.Context,
    entry_id: int = typer.Argument(..., help="Time entry id."),
    hours: str = typer.Option(None, "--hours", help="New hours (decimal or ISO8601)."),
    spent_on: str = typer.Option(None, "--date", help="New date YYYY-MM-DD."),
    activity: str = typer.Option(None, "--activity", help="New activity name."),
    comment: str = typer.Option(None, "--comment", "-m", help="New comment."),
    custom_fields: str = typer.Option(None, "--custom-fields", help="JSON of customFieldN values."),
) -> None:
    """Edit a time entry (partial; no lockVersion)."""
    obj = ctx_obj(ctx)
    client = obj.client()
    body: dict = {}
    apply_custom_fields(body, custom_fields)
    if hours is not None:
        body["hours"] = parse_hours_input(hours)
    if spent_on is not None:
        body["spentOn"] = spent_on
    if comment is not None:
        body["comment"] = {"raw": comment}
    if activity is not None:
        current = client.get(f"time_entries/{entry_id}")
        pid = hal.link_id(current, "project")
        set_link(body, "activity", resolve.time_activity(client, activity, project_ref=pid))
    if not body:
        raise OpError("nothing to update")
    obj.emitter.emit(serialize.time_entry(client.patch(f"time_entries/{entry_id}", json=body)))


@app.command()
def delete(
    ctx: typer.Context,
    entry_id: int = typer.Argument(..., help="Time entry id."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Delete a time entry."""
    obj = ctx_obj(ctx)
    if not yes:
        typer.confirm(f"Delete time entry {entry_id}?", abort=True)
    obj.client().delete(f"time_entries/{entry_id}")
    obj.emitter.emit({"status": "deleted", "timeEntry": entry_id})


@app.command()
def activities(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P", help="Project context (activities can be project-scoped)."),
) -> None:
    """List available time-entry activities (Development, Management, ...)."""
    obj = ctx_obj(ctx)
    client = obj.client()
    if project is None:
        # activities live in the form schema; any accessible project gives the global set
        first = client.collect("projects", page_size=1, limit=1)
        project = first[0]["id"] if first else None
    acts = resolve.time_activities(client, project_ref=project)
    obj.emitter.emit([{"id": a["id"], "name": a["name"]} for a in acts], columns=[("ID", "id"), ("Name", "name")])
