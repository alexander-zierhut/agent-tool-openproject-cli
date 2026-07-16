"""File-storage (Nextcloud) links on work packages.

Links an existing file in a configured storage (e.g. your Nextcloud) to a work
package via ``/api/v3/work_packages/{id}/file_links``. Requires the storage to
be set up in OpenProject admin and connected to the project. Creating a link is
idempotent on (originData.id, work package, storage).
"""

from __future__ import annotations

import typer

from .. import serialize
from agentcli.errors import OpError
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ID", "id"),
    ("Name", "originName"),
    ("OriginID", "originId"),
    ("Storage", "storage"),
    ("Status", "status"),
]


@app.command()
def storages(ctx: typer.Context) -> None:
    """List configured file storages (Nextcloud etc.)."""
    obj = ctx_obj(ctx)
    rows = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "type": s.get("_type"),
            "host": s.get("host"),
        }
        for s in obj.client().collect("storages")
    ]
    obj.emitter.emit(rows, columns=[("ID", "id"), ("Name", "name"), ("Type", "type"), ("Host", "host")], empty="(no storages configured)")


@app.command("list")
def list_links(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
) -> None:
    """List file links on a work package."""
    obj = ctx_obj(ctx)
    rows = [serialize.file_link(f) for f in obj.client().collect(f"work_packages/{wp_id}/file_links")]
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no file links)")


@app.command()
def add(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    storage: int = typer.Option(..., "--storage", "-s", help="Storage id (see `filelink storages`)."),
    file_id: str = typer.Option(..., "--file-id", help="File id within the storage (Nextcloud fileid)."),
    file_name: str = typer.Option(..., "--file-name", help="File name to display."),
    mime: str = typer.Option("application/octet-stream", "--mime", help="MIME type (folder: application/x-op-directory)."),
) -> None:
    """Link a Nextcloud/storage file to a work package."""
    obj = ctx_obj(ctx)
    body = {
        "_type": "Collection",
        "_embedded": {
            "elements": [
                {
                    "originData": {"id": file_id, "name": file_name, "mimeType": mime},
                    "_links": {"storage": {"href": f"/api/v3/storages/{storage}"}},
                }
            ]
        },
    }
    resp = obj.client().post(f"work_packages/{wp_id}/file_links", json=body)
    elements = (resp.get("_embedded") or {}).get("elements") or [resp]
    obj.emitter.emit([serialize.file_link(e) for e in elements])


@app.command()
def get(ctx: typer.Context, file_link_id: int = typer.Argument(..., help="File link id.")) -> None:
    """Show a single file link."""
    obj = ctx_obj(ctx)
    obj.emitter.emit(serialize.file_link(obj.client().get(f"file_links/{file_link_id}")))


@app.command()
def delete(
    ctx: typer.Context,
    file_link_id: int = typer.Argument(..., help="File link id."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Remove a file link."""
    obj = ctx_obj(ctx)
    if not yes:
        typer.confirm(f"Delete file link {file_link_id}?", abort=True)
    obj.client().delete(f"file_links/{file_link_id}")
    obj.emitter.emit({"status": "deleted", "fileLink": file_link_id})
