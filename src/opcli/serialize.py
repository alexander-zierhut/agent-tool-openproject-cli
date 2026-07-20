"""Turn verbose HAL documents into flat, agent-friendly dicts.

Every serializer returns plain JSON-able dicts with relationships resolved to
``{id, name}`` shapes and custom fields surfaced under a ``customFields`` map.
The full HAL document is always available via ``--raw`` on the relevant
commands, so these summaries can stay focused on what's useful.
"""

from __future__ import annotations

import re
from typing import Any

from . import hal
from .duration import iso_to_hours

Json = dict[str, Any]

# Only keys like customField1, customField42 are real custom fields; the bare
# "customFields" _link is the admin collection and must be ignored.
_CF_RE = re.compile(r"^customField\d+$")


def _link_ref(doc: Json, name: str) -> Json | None:
    href = hal.link_href(doc, name)
    if href is None:
        return None
    return {"id": hal.id_from_href(href), "name": hal.link_title(doc, name), "href": href}


def _formattable(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("raw")
    return value


def custom_fields(doc: Json) -> Json:
    """Collect customFieldN values from attributes and _links into one map."""
    out: Json = {}
    for key, value in doc.items():
        if _CF_RE.match(key):
            out[key] = _formattable(value) if isinstance(value, dict) and "raw" in value else value
    for key in (doc.get("_links") or {}):
        if _CF_RE.match(key):
            node = doc["_links"][key]
            if isinstance(node, list):
                out[key] = [n.get("title") for n in node]
            elif isinstance(node, dict):
                out[key] = node.get("title")
    return out


def work_package(doc: Json, *, include_description: bool = True) -> Json:
    out: Json = {
        "id": doc.get("id"),
        "subject": doc.get("subject"),
        "type": hal.link_title(doc, "type"),
        "status": hal.link_title(doc, "status"),
        "priority": hal.link_title(doc, "priority"),
        "project": _link_ref(doc, "project"),
        "assignee": _link_ref(doc, "assignee"),
        "responsible": _link_ref(doc, "responsible"),
        "author": _link_ref(doc, "author"),
        "parent": _link_ref(doc, "parent"),
        "startDate": doc.get("startDate"),
        "dueDate": doc.get("dueDate"),
        "estimatedTime": doc.get("estimatedTime"),
        "spentTime": doc.get("spentTime"),
        "percentageDone": doc.get("percentageDone"),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
        "lockVersion": doc.get("lockVersion"),
    }
    if include_description:
        out["description"] = _formattable(doc.get("description"))
    cf = custom_fields(doc)
    if cf:
        out["customFields"] = cf
    return out


def _project_attributes(cf: Json, schema: Json) -> list[Json]:
    """Join resolved custom-field values (`cf`) to their human name and type from
    the project form `schema` (``customFieldNN`` -> ``{name, type}``). Includes
    every schema-defined project attribute (value ``None`` when unset) plus any
    value-bearing field not in the schema, ordered by field number."""
    keys = [k for k in schema if _CF_RE.match(k)]
    for k in cf:
        if k not in keys:
            keys.append(k)
    rows = [
        {"key": k, "name": (schema.get(k) or {}).get("name") or k,
         "type": (schema.get(k) or {}).get("type"), "value": cf.get(k)}
        for k in keys
    ]
    rows.sort(key=lambda a: int(a["key"][11:]) if a["key"][11:].isdigit() else 1_000_000)
    return rows


def project(doc: Json, schema: Json | None = None) -> Json:
    out: Json = {
        "id": doc.get("id"),
        "name": doc.get("name"),
        "identifier": doc.get("identifier"),
        "active": doc.get("active"),
        "public": doc.get("public"),
        "parent": _link_ref(doc, "parent"),
        "status": hal.link_title(doc, "status") or hal.link_id(doc, "status"),
        "description": _formattable(doc.get("description")),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
    }
    cf = custom_fields(doc)
    if cf:
        out["customFields"] = cf
    # With a form schema, surface every project attribute with its value resolved
    # to a human name/type — the join callers otherwise do by hand (issue #4).
    if schema is not None:
        out["attributes"] = _project_attributes(cf, schema)
    return out


def user(doc: Json) -> Json:
    return {
        "id": doc.get("id"),
        "login": doc.get("login"),
        "name": doc.get("name"),
        "firstName": doc.get("firstName"),
        "lastName": doc.get("lastName"),
        "email": doc.get("email"),
        "admin": doc.get("admin"),
        "status": doc.get("status"),
        "_type": doc.get("_type"),
    }


def principal(doc: Json) -> Json:
    """A user, group, or placeholder user (used for assignees/members)."""
    return {
        "id": doc.get("id"),
        "name": doc.get("name"),
        "login": doc.get("login"),
        "email": doc.get("email"),
        "type": doc.get("_type"),
    }


def comment(doc: Json) -> Json:
    """An activity entry; comments have a non-empty ``comment.raw``."""
    return {
        "id": doc.get("id"),
        "comment": _formattable(doc.get("comment")),
        "user": _link_ref(doc, "user"),
        "workPackage": _link_ref(doc, "workPackage"),
        "version": doc.get("version"),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
        "_type": doc.get("_type"),
    }


def time_entry(doc: Json) -> Json:
    # Resolve the ISO8601 duration to decimal hours (working-day model: P1D=8h)
    # so callers never have to parse it — and `--fields hoursDecimal` can sum.
    _hd = iso_to_hours(doc.get("hours"))
    return {
        "id": doc.get("id"),
        "hours": doc.get("hours"),
        "hoursDecimal": None if _hd is None else round(_hd, 4),
        "spentOn": doc.get("spentOn"),
        "comment": _formattable(doc.get("comment")),
        "user": _link_ref(doc, "user"),
        "workPackage": _link_ref(doc, "workPackage"),
        "project": _link_ref(doc, "project"),
        "activity": hal.link_title(doc, "activity"),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
        "customFields": custom_fields(doc) or None,
    }


def membership(doc: Json) -> Json:
    roles = [n.get("title") for n in hal.iter_link_list(doc, "roles")]
    principal = _link_ref(doc, "principal")
    if principal is not None:
        # `login` is not in the memberships payload; memberships.py fills it via a
        # batched principals lookup. Reserve the slot so shape is stable either way.
        principal.setdefault("login", None)
    return {
        "id": doc.get("id"),
        # Top-level name = principal title, so `--fields name` (a top-level lookup)
        # resolves to a human name instead of null (issue #6).
        "name": hal.link_title(doc, "principal"),
        "principal": principal,
        "project": _link_ref(doc, "project"),
        "roles": roles,
        "createdAt": doc.get("createdAt"),
    }


def notification(doc: Json) -> Json:
    return {
        "id": doc.get("id"),
        "subject": doc.get("subject"),
        "reason": doc.get("reason"),
        "readIAN": doc.get("readIAN"),
        "resource": _link_ref(doc, "resource"),
        "project": _link_ref(doc, "project"),
        "actor": _link_ref(doc, "actor"),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
    }


def attachment(doc: Json) -> Json:
    return {
        "id": doc.get("id"),
        "fileName": doc.get("fileName"),
        "fileSize": doc.get("fileSize"),
        "description": _formattable(doc.get("description")),
        "contentType": doc.get("contentType"),
        "author": _link_ref(doc, "author"),
        "downloadLocation": hal.link_href(doc, "downloadLocation"),
        "createdAt": doc.get("createdAt"),
    }


def file_link(doc: Json) -> Json:
    origin = doc.get("originData") or {}
    return {
        "id": doc.get("id"),
        "originName": origin.get("name"),
        "originId": origin.get("id"),
        "mimeType": origin.get("mimeType"),
        "storage": hal.link_title(doc, "storage"),
        "storageUrl": hal.link_href(doc, "storage"),
        "status": hal.link_title(doc, "status"),
        "createdAt": doc.get("createdAt"),
    }


def custom_field_schema(name: str, spec: Json) -> Json:
    """Describe one field from a resource schema (used by `cf` commands)."""
    out: Json = {
        "key": name,
        "name": spec.get("name"),
        "type": spec.get("type"),
        "required": spec.get("required"),
        "writable": spec.get("writable"),
    }
    allowed = spec.get("_embedded", {}).get("allowedValues")
    if isinstance(allowed, list) and allowed:
        out["allowedValues"] = [
            {"id": a.get("id"), "name": a.get("name") or a.get("value")} for a in allowed if isinstance(a, dict)
        ]
    elif "_links" in spec and isinstance(spec["_links"].get("allowedValues"), list):
        out["allowedValues"] = [
            {"href": a.get("href"), "name": a.get("title")} for a in spec["_links"]["allowedValues"]
        ]
    return out
