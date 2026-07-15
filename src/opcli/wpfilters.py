"""Build OpenProject work-package ``filters`` arrays from friendly options.

Encapsulates the fiddly rules the research surfaced:

* values are ALWAYS arrays of strings (ids too);
* omitting filters entirely means "open only" — pass ``[]`` for everything;
* status ``open``/``closed`` use the ``o``/``c`` operators with ``values:null``;
* full-text uses the ``search`` filter with the ``**`` operator.

Beyond the raw options, it accepts lots of predefined conveniences (``mine``,
``unassigned``, ``overdue``, ``updated_since``, ``version`` …) and a list of
``--where`` expressions compiled via :mod:`opcli.searchspec`.
"""

from __future__ import annotations

import json
from typing import Any

from . import hal, resolve, searchspec
from .client import Client


def _date(spec: str | None) -> str | None:
    return searchspec.to_date(spec).isoformat() if spec else None


def _user_value(client: Client, ref: str, project: Any) -> str:
    """Return the filter value for a user ref — 'me' passes straight through
    (the API understands it), otherwise resolve to a numeric id string."""
    if ref.strip().lower() == "me":
        return "me"
    href = resolve.user(client, ref, project_ref=project)
    return str(hal.id_from_href(href))


def build(
    client: Client,
    *,
    project: str | int | None = None,
    status: str | None = None,
    type_: str | None = None,
    assignee: str | None = None,
    author: str | None = None,
    responsible: str | None = None,
    priority: str | None = None,
    parent: str | int | None = None,
    version: str | None = None,
    id_list: str | None = None,
    query: str | None = None,
    subject: str | None = None,
    # predefined booleans
    mine: bool = False,
    unassigned: bool = False,
    watching: bool = False,
    overdue: bool = False,
    # dates (accept ISO or relative specs like 7d / +30d / today)
    created_since: str | None = None,
    created_before: str | None = None,
    updated_since: str | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    start_after: str | None = None,
    start_before: str | None = None,
    where: list[str] | None = None,
    all_statuses: bool = False,
    extra: list[dict] | None = None,
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    status_set = False

    if project is not None:
        filters.append({"project": {"operator": "=", "values": [str(resolve.project_id(client, project))]}})

    if status:
        status_set = True
        low = status.strip().lower()
        if low == "open":
            filters.append({"status": {"operator": "o", "values": None}})
        elif low == "closed":
            filters.append({"status": {"operator": "c", "values": None}})
        else:
            sid = resolve._resolve_collection(client, "statuses", status, ["name"], label="status")["id"]
            filters.append({"status": {"operator": "=", "values": [str(sid)]}})

    if type_:
        tid = resolve._resolve_collection(client, "types", type_, ["name"], label="type")["id"]
        filters.append({"type": {"operator": "=", "values": [str(tid)]}})

    if mine:
        filters.append({"assignee": {"operator": "=", "values": ["me"]}})
    elif unassigned:
        filters.append({"assignee": {"operator": "!*", "values": None}})
    elif assignee:
        filters.append({"assignee": {"operator": "=", "values": [_user_value(client, assignee, project)]}})

    if author:
        filters.append({"author": {"operator": "=", "values": [_user_value(client, author, project)]}})
    if responsible:
        filters.append({"responsible": {"operator": "=", "values": [_user_value(client, responsible, project)]}})
    if watching:
        filters.append({"watcher": {"operator": "=", "values": ["me"]}})

    if priority:
        pid = resolve._resolve_collection(client, "priorities", priority, ["name"], label="priority")["id"]
        filters.append({"priority": {"operator": "=", "values": [str(pid)]}})

    if parent is not None:
        filters.append({"parent": {"operator": "=", "values": [str(parent)]}})

    if version:
        vid = resolve.version(client, version, project_ref=project)["id"]
        filters.append({"version": {"operator": "=", "values": [str(vid)]}})

    if id_list:
        ids = [s.strip() for s in str(id_list).split(",") if s.strip()]
        filters.append({"id": {"operator": "=", "values": ids}})

    if query:
        filters.append({"search": {"operator": "**", "values": [query]}})
    if subject:
        filters.append({"subject": {"operator": "~", "values": [subject]}})

    # date ranges (open-ended <>d with an empty bound)
    if created_since or created_before:
        filters.append({"createdAt": {"operator": "<>d", "values": [_date(created_since) or "", _date(created_before) or ""]}})
    if updated_since:
        filters.append({"updatedAt": {"operator": "<>d", "values": [_date(updated_since), ""]}})
    if overdue:
        # due before today and (unless a status was requested) still open
        filters.append({"dueDate": {"operator": "<>d", "values": ["", _date("yesterday")]}})
        if not status:
            filters.append({"status": {"operator": "o", "values": None}})
            status_set = True
    if due_after or due_before:
        filters.append({"dueDate": {"operator": "<>d", "values": [_date(due_after) or "", _date(due_before) or ""]}})
    if start_after or start_before:
        filters.append({"startDate": {"operator": "<>d", "values": [_date(start_after) or "", _date(start_before) or ""]}})

    if where:
        for expr in where:
            f = searchspec.compile_where(client, expr, project_ref=project)
            filters.append(f)
            if "status" in f:
                status_set = True

    if extra:
        filters.extend(extra)

    # replicate OpenProject's "open by default" (it only auto-applies that when
    # the filters param is omitted, which we never do) unless widened.
    if not status_set and not all_statuses:
        filters.append({"status": {"operator": "o", "values": None}})

    return filters


def encode(filters: list[dict]) -> str:
    return json.dumps(filters)
