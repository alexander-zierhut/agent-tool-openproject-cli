"""In-app notification commands: list, get, mark read/unread, mark all read.

``readIAN`` is boolean-encoded as the strings ``"t"``/``"f"``. Mark endpoints
return 204 with an empty body.
"""

from __future__ import annotations

import datetime as _dt
import json

import typer

from .. import resolve, serialize
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ID", "id"),
    ("Reason", "reason"),
    ("Read", "readIAN"),
    ("Subject", "subject"),
    ("Resource", lambda r: (r.get("resource") or {}).get("name")),
    ("When", "createdAt"),
]


@app.command("list")
def list_notifications(
    ctx: typer.Context,
    state: str = typer.Option("unread", "--state", help="unread | read | all."),
    reason: str = typer.Option(None, "--reason", help="mentioned, assigned, watched, ..."),
    project: str = typer.Option(None, "--project", "-P", help="Filter by project."),
    today: bool = typer.Option(False, "--today", help="Only notifications created today."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum rows (0 = all)."),
) -> None:
    """List your in-app notifications (unread by default)."""
    obj = ctx_obj(ctx)
    client = obj.client()
    filters = _filters(client, state=state, reason=reason, project=project)
    params = {"sortBy": json.dumps([["id", "desc"]])}
    if filters:
        params["filters"] = json.dumps(filters)
    # `today` isn't a server-side filter for notifications, so scope client-side.
    fetch_limit = None if today else (limit or None)
    rows = [serialize.notification(n) for n in client.collect("notifications", params=params, limit=fetch_limit)]
    if today:
        prefix = _dt.date.today().isoformat()
        rows = [r for r in rows if (r.get("createdAt") or "").startswith(prefix)]
        if limit:
            rows = rows[:limit]
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no notifications)")


def _filters(client, *, state=None, reason=None, project=None) -> list[dict]:
    filters = []
    if state == "unread":
        filters.append({"readIAN": {"operator": "=", "values": ["f"]}})
    elif state == "read":
        filters.append({"readIAN": {"operator": "=", "values": ["t"]}})
    if reason:
        filters.append({"reason": {"operator": "=", "values": [reason]}})
    if project:
        filters.append({"project": {"operator": "=", "values": [str(resolve.project_id(client, project))]}})
    return filters


@app.command()
def count(
    ctx: typer.Context,
    today: bool = typer.Option(False, "--today", help="Also count today's notifications."),
    project: str = typer.Option(None, "--project", "-P", help="Scope counts to a project."),
) -> None:
    """Count notifications (total + unread, and optionally today's)."""
    obj = ctx_obj(ctx)
    client = obj.client()

    def total(filters: list[dict]) -> int:
        params = {"pageSize": 1}
        if filters:
            params["filters"] = json.dumps(filters)
        return int(client.get("notifications", params=params).get("total", 0))

    proj_filter = _filters(client, project=project)
    out = {
        "total": total(proj_filter),
        "unread": total(_filters(client, state="unread", project=project)),
    }
    if today:
        prefix = _dt.date.today().isoformat()
        params = {"sortBy": json.dumps([["id", "desc"]])}
        if proj_filter:
            params["filters"] = json.dumps(proj_filter)
        todays = [n for n in client.collect("notifications", params=params, limit=None)
                  if (n.get("createdAt") or "").startswith(prefix)]
        out["today"] = len(todays)
        out["todayUnread"] = sum(1 for n in todays if not n.get("readIAN"))
    obj.emitter.emit(out)


@app.command()
def get(ctx: typer.Context, notification_id: int = typer.Argument(..., help="Notification id.")) -> None:
    """Show one notification."""
    obj = ctx_obj(ctx)
    obj.emitter.emit(serialize.notification(obj.client().get(f"notifications/{notification_id}")))


@app.command()
def read(ctx: typer.Context, notification_id: int = typer.Argument(..., help="Notification id.")) -> None:
    """Mark a notification as read."""
    obj = ctx_obj(ctx)
    obj.client().post(f"notifications/{notification_id}/read_ian")
    obj.emitter.emit({"status": "read", "notification": notification_id})


@app.command()
def unread(ctx: typer.Context, notification_id: int = typer.Argument(..., help="Notification id.")) -> None:
    """Mark a notification as unread."""
    obj = ctx_obj(ctx)
    obj.client().post(f"notifications/{notification_id}/unread_ian")
    obj.emitter.emit({"status": "unread", "notification": notification_id})


@app.command("read-all")
def read_all(ctx: typer.Context) -> None:
    """Mark all notifications as read."""
    obj = ctx_obj(ctx)
    obj.client().post("notifications/read_ian")
    obj.emitter.emit({"status": "all read"})
