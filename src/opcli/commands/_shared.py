"""Helpers shared across command modules."""

from __future__ import annotations

import json
from typing import Any

import typer

from ..context import AppContext
from agentcli.errors import OpError


def ctx_obj(ctx: typer.Context) -> AppContext:
    return ctx.obj


def parse_json_option(value: str | None, *, what: str = "value") -> Any:
    """Parse a JSON string passed on the command line (``--fields '{...}'``)."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise OpError(f"invalid JSON for {what}: {exc}") from exc


def set_link(body: dict, name: str, href: str | None) -> None:
    body.setdefault("_links", {})[name] = {"href": href}


def apply_custom_fields(body: dict, raw: str | None) -> None:
    """Merge a ``--custom-fields`` JSON object into a write body.

    Scalars land at the top level; values shaped like ``{"href": ...}`` (or a
    list of them) go under ``_links`` — matching OpenProject's split between
    value and reference custom fields.
    """
    if not raw:
        return
    data = parse_json_option(raw, what="--custom-fields")
    if not isinstance(data, dict):
        raise OpError("--custom-fields must be a JSON object keyed by customFieldN")
    for key, val in data.items():
        if isinstance(val, dict) and set(val.keys()) <= {"href"}:
            set_link(body, key, val.get("href"))
        elif isinstance(val, list) and all(isinstance(v, dict) and "href" in v for v in val):
            body.setdefault("_links", {})[key] = val
        else:
            body[key] = val
