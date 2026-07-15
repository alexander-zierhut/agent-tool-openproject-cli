"""Helpers for OpenProject's HAL+JSON representation.

OpenProject resources are HAL documents: attributes live at the top level,
relationships live under ``_links`` (each a ``{"href": ...}`` or a list of
them), and embedded resources live under ``_embedded``. Collections put their
items in ``_embedded.elements`` with ``total``/``count``/``pageSize`` alongside.

These helpers keep that structure out of the command code.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

Json = dict[str, Any]


def link(href: str | None) -> Json:
    """Build a HAL link object. ``None`` clears a relationship (e.g. unassign)."""
    return {"href": href}


def ref(resource: str, id: Any) -> Json:
    """Build a link to ``/api/v3/<resource>/<id>`` (the accepted path form)."""
    return {"href": f"/api/v3/{resource}/{id}"}


_ID_RE = re.compile(r"/api/v3/[^/]+/(\d+)(?:/.*)?$")


def id_from_href(href: str | None) -> int | None:
    if not href:
        return None
    m = _ID_RE.search(href)
    return int(m.group(1)) if m else None


def link_href(doc: Json, name: str) -> str | None:
    node = (doc.get("_links") or {}).get(name)
    if isinstance(node, dict):
        return node.get("href")
    return None


def link_title(doc: Json, name: str) -> str | None:
    node = (doc.get("_links") or {}).get(name)
    if isinstance(node, dict):
        return node.get("title")
    return None


def link_id(doc: Json, name: str) -> int | None:
    return id_from_href(link_href(doc, name))


def elements(collection: Json) -> list[Json]:
    return (collection.get("_embedded") or {}).get("elements") or []


def total(collection: Json) -> int:
    return int(collection.get("total") or 0)


def formattable(raw: str | None) -> Json:
    """Wrap text as a Formattable (markdown) value used by description/comment."""
    return {"raw": raw or ""}


def iter_link_list(doc: Json, name: str) -> Iterable[Json]:
    node = (doc.get("_links") or {}).get(name)
    if isinstance(node, list):
        yield from node
    elif isinstance(node, dict):
        yield node
