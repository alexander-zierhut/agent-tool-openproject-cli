"""Work-package comments (activities): list, add, edit.

OpenProject stores comments as *activities*. The collection is fetched by work
package id; edits target the activity id (from each entry's self link). There is
no delete-comment endpoint in API v3.
"""

from __future__ import annotations

import typer

from .. import hal, serialize
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)

_COLUMNS = [
    ("ActID", "id"),
    ("User", lambda r: (r.get("user") or {}).get("name")),
    ("When", "createdAt"),
    ("Comment", "comment"),
]


@app.command("list")
def list_comments(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    comments_only: bool = typer.Option(True, "--comments-only/--all-activity", help="Only entries with a comment."),
) -> None:
    """List activities/comments for a work package (oldest first)."""
    obj = ctx_obj(ctx)
    client = obj.client()
    activities = client.collect(f"work_packages/{wp_id}/activities")
    rows = []
    name_cache: dict[int, str] = {}
    for a in activities:
        s = serialize.comment(a)
        if comments_only and not (s.get("comment") or "").strip():
            continue
        # activity user links carry no title on some versions — resolve once.
        user = s.get("user")
        if user and user.get("id") and not user.get("name"):
            uid = user["id"]
            if uid not in name_cache:
                try:
                    name_cache[uid] = client.get(f"users/{uid}").get("name")
                except Exception:
                    name_cache[uid] = None
            user["name"] = name_cache[uid]
        rows.append(s)
    obj.emitter.emit(rows, columns=_COLUMNS, empty="(no comments)")


@app.command()
def add(
    ctx: typer.Context,
    wp_id: int = typer.Argument(..., help="Work package id."),
    text: str = typer.Argument(..., help="Comment body (markdown)."),
    notify: bool = typer.Option(False, "--notify/--no-notify", help="Send notifications (default off)."),
) -> None:
    """Add a comment to a work package."""
    obj = ctx_obj(ctx)
    doc = obj.client().post(
        f"work_packages/{wp_id}/activities",
        json={"comment": {"raw": text}},
        params={"notify": str(notify).lower()},
    )
    obj.emitter.emit(serialize.comment(doc))


@app.command()
def edit(
    ctx: typer.Context,
    activity_id: int = typer.Argument(..., help="Activity id (from `comment list`)."),
    text: str = typer.Argument(..., help="New comment body (markdown)."),
) -> None:
    """Edit an existing comment by its activity id."""
    obj = ctx_obj(ctx)
    # The activity PATCH endpoint expects `comment` as a plain string (unlike the
    # POST add endpoint, which takes a {"raw": ...} Formattable).
    doc = obj.client().patch(f"activities/{activity_id}", json={"comment": text})
    obj.emitter.emit(serialize.comment(doc))
