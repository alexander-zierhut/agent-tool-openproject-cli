"""Custom-field discovery.

Custom fields cannot be *created* through the API v3 (that's admin-UI/Rails
only). What the API *does* let you do is discover which custom fields exist on a
resource and their allowed values — which is exactly what you need to then set
them via `wp create/update --custom-fields`. These commands read the relevant
schema/form and surface the ``customFieldN`` entries.
"""

from __future__ import annotations

import typer

from .. import resolve, serialize
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("Key", "key"),
    ("Name", "name"),
    ("Type", "type"),
    ("Required", "required"),
    ("Writable", "writable"),
    ("AllowedValues", lambda r: len(r.get("allowedValues", [])) if r.get("allowedValues") else ""),
]


def _schema_fields(schema: dict, *, only_custom: bool) -> list[dict]:
    out = []
    for name, spec in schema.items():
        if not isinstance(spec, dict) or not spec.get("type"):
            continue
        if only_custom and not name.startswith("customField"):
            continue
        out.append(serialize.custom_field_schema(name, spec))
    return out


@app.command()
def wp(
    ctx: typer.Context,
    project: str = typer.Option(..., "--project", "-P", help="Project id/identifier."),
    type_: str = typer.Option("Task", "--type", "-t", help="Work-package type name."),
    all_fields: bool = typer.Option(False, "--all", help="Include built-in fields, not just custom."),
) -> None:
    """List custom fields available on work packages of a project/type."""
    obj = ctx_obj(ctx)
    client = obj.client()
    pid = resolve.project_id(client, project)
    form = client.post(
        f"projects/{pid}/work_packages/form",
        json={"_links": {"project": {"href": f"/api/v3/projects/{pid}"}, "type": {"href": resolve.wp_type(client, type_)}}},
    )
    schema = (form.get("_embedded") or {}).get("schema") or {}
    obj.emitter.emit(_schema_fields(schema, only_custom=not all_fields), columns=_COLUMNS, empty="(no custom fields)")


@app.command()
def project(
    ctx: typer.Context,
    all_fields: bool = typer.Option(False, "--all", help="Include built-in fields, not just custom."),
) -> None:
    """List custom fields (project attributes) available on projects."""
    obj = ctx_obj(ctx)
    client = obj.client()
    form = client.post("projects/form", json={})
    schema = (form.get("_embedded") or {}).get("schema") or {}
    obj.emitter.emit(_schema_fields(schema, only_custom=not all_fields), columns=_COLUMNS, empty="(no custom fields)")


@app.command("time")
def time_entry(
    ctx: typer.Context,
    all_fields: bool = typer.Option(False, "--all", help="Include built-in fields, not just custom."),
) -> None:
    """List custom fields available on time entries."""
    obj = ctx_obj(ctx)
    client = obj.client()
    form = client.post("time_entries/form", json={})
    schema = (form.get("_embedded") or {}).get("schema") or {}
    obj.emitter.emit(_schema_fields(schema, only_custom=not all_fields), columns=_COLUMNS, empty="(no custom fields)")
