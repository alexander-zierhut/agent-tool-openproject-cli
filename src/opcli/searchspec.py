"""Search ergonomics: a curated field registry, an operator reference, human
date specs, and a ``--where`` mini-language that compiles to OpenProject filters.

The goal is to make work-package search usable *without* memorising the raw
JSON filter syntax:

* a **field registry** so ``search fields`` can tell you what you can filter on;
* an **operator reference** so ``search operators`` explains the codes;
* **date specs** like ``7d``, ``2w``, ``today``, ``+30d`` -> concrete dates;
* a **``--where "field op value"``** compiler so you can write
  ``--where "status = open" --where "updated > 7d"`` instead of JSON.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field as _dc_field
from typing import Any

from . import hal, resolve
from .client import Client
from agentcli.errors import OpError


@dataclass
class Field:
    key: str
    label: str
    kind: str  # status|type|priority|user|project|version|date|datetime|int|text|bool|duration|relation
    ops: list[str] = _dc_field(default_factory=list)
    flag: str = ""
    desc: str = ""


# The common, well-supported filters — used for discoverability and value
# resolution. The live query schema is the source of truth for *which* filters
# exist on an instance (incl. custom fields); this adds human meaning.
REGISTRY: dict[str, Field] = {
    f.key: f
    for f in [
        Field("search", "Full text", "text", ["**"], '"<query>" (positional)', "subject + description + comments"),
        Field("subject", "Subject", "text", ["~", "!~"], "--subject", "title contains text"),
        Field("id", "ID", "int", ["=", "!"], "--id 1,2,3", "specific work-package ids"),
        Field("status", "Status", "status", ["=", "!", "o", "c"], "--status/--open/--closed", "open, closed, or a status name"),
        Field("type", "Type", "type", ["=", "!"], "--type", "Task, Bug, Feature, ..."),
        Field("priority", "Priority", "priority", ["=", "!"], "--priority", "Low, Normal, High, Immediate"),
        Field("assignee", "Assignee", "user", ["=", "!", "*", "!*"], "--assignee/--mine/--unassigned", "login/name/id or 'me'"),
        Field("author", "Author", "user", ["=", "!"], "--author/--created-by", "who created it"),
        Field("responsible", "Accountable", "user", ["=", "!"], "--responsible", "accountable person"),
        Field("watcher", "Watcher", "user", ["=", "!"], "--watching", "who watches it ('me')"),
        Field("project", "Project", "project", ["=", "!"], "--project", "project id/identifier"),
        Field("version", "Version", "version", ["=", "!"], "--version", "target version/milestone"),
        Field("parent", "Parent", "int", ["=", "!"], "--parent", "parent work-package id"),
        Field("dueDate", "Due date", "date", ["<>d", "=d", "t", "w"], "--due-before/--due-after/--overdue", "deadline"),
        Field("startDate", "Start date", "date", ["<>d", "=d"], "--start-after/--start-before", "start date"),
        Field("createdAt", "Created", "datetime", ["<>d", "t"], "--created-since/--created-before", "creation time"),
        Field("updatedAt", "Updated", "datetime", ["<>d", "t"], "--updated-since", "last change time"),
        Field("percentageDone", "% done", "int", [">=", "<="], '--where "percentageDone>=50"', "progress percent"),
        Field("estimatedTime", "Estimated", "duration", [">=", "<="], '--where "estimatedTime>=PT2H"', "estimated time"),
    ]
}


OPERATORS: list[tuple[str, str]] = [
    ("=", "equals / one of (values are OR-ed)"),
    ("!", "is none of / not equal"),
    ("~", "contains (text, LIKE)"),
    ("!~", "does not contain"),
    ("o", "open statuses (status filter, no value)"),
    ("c", "closed statuses (status filter, no value)"),
    ("*", "has any value / is set"),
    ("!*", "has no value / is empty (e.g. unassigned)"),
    (">=", "greater than or equal (numbers)"),
    ("<=", "less than or equal (numbers)"),
    ("=d", "on a specific date"),
    ("<>d", "between two dates (values=[from,to]; '' = open bound)"),
    ("t", "today (date filter, no value)"),
    ("w", "this week (date filter, no value)"),
    ("t-", "exactly N days ago"),
    ("t+", "exactly N days ahead"),
    ("<t-", "more than N days ago"),
    (">t-", "within the last N days"),
    ("<t+", "within the next N days"),
    (">t+", "more than N days ahead"),
]


# ------------------------------------------------------------------ dates
_REL_RE = re.compile(r"^([+-]?)(\d+)\s*([dwmy])$")


def to_date(spec: str, *, base: _dt.date | None = None) -> _dt.date:
    """Human date spec -> concrete date.

    ``today``/``yesterday``/``tomorrow``; ``7d``/``2w``/``1m``/``1y`` (N units
    ago); ``+7d`` (N units ahead); or an ISO ``YYYY-MM-DD`` date.
    """
    base = base or _dt.date.today()
    s = spec.strip().lower()
    if s == "today":
        return base
    if s == "yesterday":
        return base - _dt.timedelta(days=1)
    if s == "tomorrow":
        return base + _dt.timedelta(days=1)
    m = _REL_RE.match(s)
    if m:
        sign = 1 if m.group(1) == "+" else -1  # default: into the past
        n = int(m.group(2)) * sign
        unit = m.group(3)
        if unit == "d":
            return base + _dt.timedelta(days=n)
        if unit == "w":
            return base + _dt.timedelta(weeks=n)
        if unit == "m":
            return _shift_months(base, n)
        if unit == "y":
            try:
                return base.replace(year=base.year + n)
            except ValueError:
                return base.replace(year=base.year + n, day=28)
    try:
        return _dt.date.fromisoformat(spec)
    except ValueError as exc:
        raise OpError(
            f"invalid date '{spec}' — use YYYY-MM-DD, or relative like 7d, 2w, 1m, +30d, today, yesterday"
        ) from exc


def _shift_months(d: _dt.date, months: int) -> _dt.date:
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    import calendar

    day = min(d.day, calendar.monthrange(year, month)[1])
    return _dt.date(year, month, day)


# --------------------------------------------------------- value resolution
def resolve_value(client: Client, kind: str, raw: str, *, project_ref: Any = None) -> str:
    r = raw.strip()
    if kind == "user":
        if r.lower() == "me":
            return "me"
        href = resolve.user(client, r, project_ref=project_ref)
        return str(hal.id_from_href(href))
    if kind == "status":
        return str(resolve._resolve_collection(client, "statuses", r, ["name"], label="status")["id"])
    if kind == "type":
        return str(resolve._resolve_collection(client, "types", r, ["name"], label="type")["id"])
    if kind == "priority":
        return str(resolve._resolve_collection(client, "priorities", r, ["name"], label="priority")["id"])
    if kind == "project":
        return str(resolve.project_id(client, r))
    if kind == "version":
        return str(resolve.version(client, r, project_ref=project_ref)["id"])
    if kind in ("date", "datetime"):
        return to_date(r).isoformat()
    return r  # int/text/bool/relation/customfield -> as-is


# friendly aliases so `--where "updated > 7d"` works, not just "updatedAt"
ALIASES = {
    "updated": "updatedAt",
    "created": "createdAt",
    "due": "dueDate",
    "start": "startDate",
    "done": "percentageDone",
    "progress": "percentageDone",
    "estimate": "estimatedTime",
    "estimated": "estimatedTime",
    "assigned": "assignee",
    "milestone": "version",
}


def canonical_field(name: str) -> str:
    return ALIASES.get(name.strip(), name.strip())


# ------------------------------------------------------------- --where lang
# order matters: match multi-char operators before single-char ones
_WHERE_OPS = ["!~", ">=", "<=", "!=", "~", "=", ">", "<"]


def parse_where(expr: str) -> tuple[str, str, list[str]]:
    """``"status = open"`` / ``"updated>7d"`` / ``"assignee:none"`` ->
    (field, symbol, values). ``:kw`` forms use symbols ``:open|:closed|:none|:any``."""
    e = expr.strip()
    # bare keyword form:  field:open
    m = re.match(r"^\s*([A-Za-z0-9_]+)\s*:\s*(open|closed|none|any)\s*$", e, re.I)
    if m:
        return m.group(1), ":" + m.group(2).lower(), []
    for sym in _WHERE_OPS:
        idx = e.find(sym)
        if idx > 0:
            field = e[:idx].strip()
            value = e[idx + len(sym):].strip()
            if not field:
                break
            values = [v.strip() for v in value.split(",") if v.strip()]
            return field, sym, values
    raise OpError(f"could not parse --where '{expr}' (use e.g. \"status = open\", \"updated > 7d\", \"assignee:none\")")


def compile_where(client: Client, expr: str, *, project_ref: Any = None) -> dict:
    field, sym, values = parse_where(expr)
    field = canonical_field(field)
    fld = REGISTRY.get(field)
    kind = fld.kind if fld else ("customfield" if field.startswith("customField") else "text")

    # bare keyword operators
    if sym == ":open":
        return {field: {"operator": "o", "values": None}}
    if sym == ":closed":
        return {field: {"operator": "c", "values": None}}
    if sym == ":none":
        return {field: {"operator": "!*", "values": None}}
    if sym == ":any":
        return {field: {"operator": "*", "values": None}}

    if not values:
        raise OpError(f"--where '{expr}' needs a value")

    resolved = [resolve_value(client, kind, v, project_ref=project_ref) for v in values]

    # dates: >/< become open-ended ranges; = becomes on-date
    if kind in ("date", "datetime"):
        if sym in (">", ">="):
            return {field: {"operator": "<>d", "values": [resolved[0], ""]}}
        if sym in ("<", "<="):
            return {field: {"operator": "<>d", "values": ["", resolved[0]]}}
        if sym == "=":
            return {field: {"operator": "=d", "values": [resolved[0]]}}

    op_map = {"=": "=", "!=": "!", "!": "!", "~": "~", "!~": "!~", ">=": ">=", "<=": "<=", ">": ">=", "<": "<="}
    op = op_map.get(sym)
    if op is None:
        raise OpError(f"operator '{sym}' not supported in --where")
    return {field: {"operator": op, "values": resolved}}


# ---------------------------------------------------------- live field list
def live_fields(client: Client, project_ref: Any = None) -> list[dict]:
    """List the filters available on this instance (from the query schema),
    enriched with human descriptions from the registry."""
    path = "queries/filter_instance_schemas"
    if project_ref is not None:
        path = f"projects/{resolve.project_id(client, project_ref)}/queries/filter_instance_schemas"
    out: list[dict] = []
    for el in client.collect(path, page_size=200):
        href = ((el.get("_links") or {}).get("self") or {}).get("href", "")
        key = href.rstrip("/").split("/")[-1]
        if not key:
            continue
        reg = REGISTRY.get(key)
        out.append(
            {
                "field": key,
                "label": reg.label if reg else key,
                "kind": reg.kind if reg else ("customField" if key.startswith("customField") else ""),
                "operators": reg.ops if reg else [],
                "flag": reg.flag if reg else ("--where / --filters" if not reg else ""),
                "description": reg.desc if reg else "",
            }
        )
    return out
