"""Resolve human-friendly references to API hrefs / ids.

Agents and humans want to write ``--status "In progress"``, ``--assignee admin``
or ``--project my-project`` rather than juggle numeric ids. These helpers take a
loose reference (numeric id, identifier, login, or name) and return the concrete
resource, raising a clear :class:`NotFoundError` when nothing matches.
"""

from __future__ import annotations

from typing import Any, Callable

from .client import Client
from .errors import NotFoundError, OpError
from . import hal

Json = dict[str, Any]


def _is_id(ref: str | int) -> bool:
    return isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit())


def _match(elements: list[Json], ref: str, fields: list[str]) -> Json | None:
    ref_l = ref.strip().lower()
    # exact match, honouring FIELD priority: a login match beats a name match
    # even if the name-matching element appears earlier in the collection.
    for f in fields:
        for el in elements:
            val = el.get(f)
            if isinstance(val, str) and val.lower() == ref_l:
                return el
    # then a unique substring match across all fields
    hits = [
        el
        for el in elements
        if any(isinstance(el.get(f), str) and ref_l in el[f].lower() for f in fields)
    ]
    if len(hits) == 1:
        return hits[0]
    return None


def _resolve_collection(
    client: Client,
    collection: str,
    ref: str | int,
    fields: list[str],
    *,
    label: str,
    params: dict | None = None,
) -> Json:
    if _is_id(ref):
        return client.get(f"{collection}/{ref}")
    elements = client.collect(collection, params=params, page_size=200)
    el = _match(elements, str(ref), fields)
    if el is None:
        names = ", ".join(sorted(str(e.get(fields[0])) for e in elements)[:25])
        raise NotFoundError(f"no {label} matching '{ref}'. Available: {names}")
    return el


def project(client: Client, ref: str | int) -> Json:
    return _resolve_collection(
        client, "projects", ref, ["identifier", "name"], label="project"
    )


def project_id(client: Client, ref: str | int) -> int:
    return int(project(client, ref)["id"])


def status(client: Client, ref: str | int) -> str:
    el = _resolve_collection(client, "statuses", ref, ["name"], label="status")
    return f"/api/v3/statuses/{el['id']}"


def wp_type(client: Client, ref: str | int) -> str:
    el = _resolve_collection(client, "types", ref, ["name"], label="type")
    return f"/api/v3/types/{el['id']}"


def priority(client: Client, ref: str | int) -> str:
    el = _resolve_collection(client, "priorities", ref, ["name"], label="priority")
    return f"/api/v3/priorities/{el['id']}"


def time_activities(
    client: Client, *, project_ref: str | int | None = None, wp_id: int | None = None
) -> list[Json]:
    """List time-entry activities via the time-entry form's schema.

    This version of OpenProject has no ``time_entries/activities`` *collection*
    endpoint; allowed activities live in the form schema (per project/WP).
    """
    links: dict = {}
    if wp_id is not None:
        links["workPackage"] = {"href": f"/api/v3/work_packages/{wp_id}"}
    elif project_ref is not None:
        links["project"] = {"href": f"/api/v3/projects/{project_id(client, project_ref)}"}
    form = client.post("time_entries/form", json={"_links": links})
    schema = (form.get("_embedded") or {}).get("schema") or {}
    activity = schema.get("activity") or {}
    allowed = (activity.get("_embedded") or {}).get("allowedValues") or []
    out: list[Json] = []
    for a in allowed:
        aid = a.get("id")
        href = ((a.get("_links") or {}).get("self") or {}).get("href") or f"/api/v3/time_entries/activities/{aid}"
        out.append({"id": aid, "name": a.get("name"), "href": href})
    return out


def time_activity(
    client: Client, ref: str | int, *, project_ref: str | int | None = None, wp_id: int | None = None
) -> str:
    if _is_id(ref):
        return f"/api/v3/time_entries/activities/{ref}"
    acts = time_activities(client, project_ref=project_ref, wp_id=wp_id)
    el = _match(acts, str(ref), ["name"])
    if el is None:
        names = ", ".join(str(a.get("name")) for a in acts)
        raise NotFoundError(f"no time-entry activity matching '{ref}'. Available: {names}")
    return el["href"]


def role(client: Client, ref: str | int) -> str:
    el = _resolve_collection(client, "roles", ref, ["name"], label="role")
    return f"/api/v3/roles/{el['id']}"


def version(client: Client, ref: str | int, *, project_ref: str | int | None = None) -> Json:
    """Resolve a version/milestone by id or name (project-scoped when given)."""
    if _is_id(ref):
        return client.get(f"versions/{ref}")
    coll = "versions"
    if project_ref is not None:
        coll = f"projects/{project_id(client, project_ref)}/versions"
    elements = client.collect(coll, page_size=200)
    el = _match(elements, str(ref), ["name"])
    if el is None:
        names = ", ".join(str(e.get("name")) for e in elements)
        raise NotFoundError(f"no version matching '{ref}'. Available: {names}")
    return el


def category(client: Client, ref: str | int, *, project_ref: str | int) -> Json:
    if _is_id(ref):
        return client.get(f"categories/{ref}")
    elements = client.collect(f"projects/{project_id(client, project_ref)}/categories", page_size=200)
    el = _match(elements, str(ref), ["name"])
    if el is None:
        raise NotFoundError(f"no category matching '{ref}'")
    return el


def user(client: Client, ref: str | int, *, project_ref: str | int | None = None) -> str:
    """Resolve a user/principal to its href.

    ``me`` resolves to the authenticated user. When ``project_ref`` is given we
    search that project's assignable principals first (so names local to the
    project resolve), then fall back to the global users collection.
    """
    if isinstance(ref, str) and ref.strip().lower() == "me":
        return client.me()["_links"]["self"]["href"]
    if _is_id(ref):
        return f"/api/v3/users/{ref}"

    ref_s = str(ref)
    candidates: list[Json] = []
    if project_ref is not None:
        pid = project_id(client, project_ref)
        candidates = client.collect(
            f"projects/{pid}/available_assignees", page_size=200
        )
        el = _match(candidates, ref_s, ["login", "name", "email"])
        if el is not None:
            return el["_links"]["self"]["href"]
    # global fallback
    users = client.collect("principals", page_size=200)
    el = _match(users, ref_s, ["login", "name", "email"])
    if el is None:
        raise NotFoundError(f"no user/principal matching '{ref}'")
    return el["_links"]["self"]["href"]
