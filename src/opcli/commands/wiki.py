"""Wiki commands (read-only metadata).

OpenProject API v3 exposes only ``GET /api/v3/wiki_pages/{id}`` and the page's
attachments. The WikiPage model is a stub (id + title only) — there is NO
list/create/update/delete and NO way to read or write the page body over the
API. These commands surface what's available and are explicit about the limits.
"""

from __future__ import annotations

import typer

from .. import serialize
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)


@app.command()
def get(
    ctx: typer.Context,
    page_id: int = typer.Argument(..., help="Wiki page id."),
    raw: bool = typer.Option(False, "--raw", "-r", help="Return the full HAL document."),
) -> None:
    """Show wiki page metadata (id + title only; body is not exposed by the API)."""
    obj = ctx_obj(ctx)
    doc = obj.client().get(f"wiki_pages/{page_id}")
    if raw:
        obj.emitter.emit(doc)
        return
    obj.emitter.emit(
        {
            "id": doc.get("id"),
            "title": doc.get("title"),
            "project": (doc.get("_embedded") or {}).get("project", {}).get("identifier"),
            "note": "OpenProject API v3 does not expose wiki page body text.",
        }
    )


@app.command()
def attachments(
    ctx: typer.Context,
    page_id: int = typer.Argument(..., help="Wiki page id."),
) -> None:
    """List attachments on a wiki page."""
    obj = ctx_obj(ctx)
    rows = [serialize.attachment(a) for a in obj.client().collect(f"wiki_pages/{page_id}/attachments")]
    obj.emitter.emit(rows, columns=[("ID", "id"), ("File", "fileName"), ("Size", "fileSize"), ("Type", "contentType")])
