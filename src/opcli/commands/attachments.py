"""Attachment commands: list, upload, download, get, delete.

Upload is multipart/form-data with two parts: a JSON ``metadata`` part
(``fileName`` + optional ``description``) and the raw ``file`` part. Downloads
follow the attachment's ``downloadLocation`` link (which may redirect to remote
storage).
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path

import typer

from .. import hal, serialize
from ..errors import OpError
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ID", "id"),
    ("File", "fileName"),
    ("Size", "fileSize"),
    ("Type", "contentType"),
    ("Author", lambda r: (r.get("author") or {}).get("name")),
    ("When", "createdAt"),
]


@app.command("list")
def list_attachments(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
) -> None:
    """List attachments on a work package."""
    obj = ctx_obj(ctx)
    rows = [serialize.attachment(a) for a in obj.client().collect(f"work_packages/{wp_id}/attachments")]
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no attachments)")


@app.command()
def upload(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    path: Path = typer.Argument(..., help="Local file to upload."),
    name: str = typer.Option(None, "--name", help="Override the stored file name."),
    description: str = typer.Option(None, "--description", "-d", help="Attachment description."),
) -> None:
    """Upload a file and attach it to a work package."""
    obj = ctx_obj(ctx)
    if not path.exists() or not path.is_file():
        raise OpError(f"file not found: {path}")
    file_name = name or path.name
    metadata = {"fileName": file_name}
    if description is not None:
        metadata["description"] = description
    content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    files = {
        "metadata": (None, json.dumps(metadata), "application/json"),
        "file": (file_name, path.read_bytes(), content_type),
    }
    doc = obj.client().request("POST", f"work_packages/{wp_id}/attachments", files=files)
    obj.emitter.emit(serialize.attachment(doc))


@app.command()
def get(ctx: typer.Context, attachment_id: int = typer.Argument(..., help="Attachment id.")) -> None:
    """Show attachment metadata."""
    obj = ctx_obj(ctx)
    obj.emitter.emit(serialize.attachment(obj.client().get(f"attachments/{attachment_id}")))


@app.command()
def download(
    ctx: typer.Context,
    attachment_id: int = typer.Argument(..., help="Attachment id."),
    output: Path = typer.Option(None, "--output", "-O", help="Output path (default: original file name)."),
) -> None:
    """Download an attachment's content."""
    obj = ctx_obj(ctx)
    client = obj.client()
    meta = client.get(f"attachments/{attachment_id}")
    href = hal.link_href(meta, "downloadLocation") or f"/api/v3/attachments/{attachment_id}/content"
    resp = client.request("GET", href, parse=False)
    dest = output or Path(meta.get("fileName") or f"attachment-{attachment_id}")
    dest.write_bytes(resp.content)
    obj.emitter.emit({"status": "downloaded", "attachment": attachment_id, "path": str(dest), "bytes": len(resp.content)})


@app.command()
def delete(
    ctx: typer.Context,
    attachment_id: int = typer.Argument(..., help="Attachment id."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Delete an attachment."""
    obj = ctx_obj(ctx)
    if not yes:
        typer.confirm(f"Delete attachment {attachment_id}?", abort=True)
    obj.client().delete(f"attachments/{attachment_id}")
    obj.emitter.emit({"status": "deleted", "attachment": attachment_id})
