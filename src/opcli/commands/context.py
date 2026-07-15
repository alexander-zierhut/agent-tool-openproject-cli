"""Session context — sticky option defaults applied to later commands.

A context is a small map of option-name -> value (e.g. ``project=webshop``,
``assignee=me``). Once set, those values become the *default* for matching
options on later commands, so you stop repeating ``--project webshop`` etc.
Explicit flags always win, and ``--no-context`` ignores the context for one
command. Contexts can be saved by name and switched between.
"""

from __future__ import annotations

import typer

from ..config import Config, config_path
from ..errors import OpError
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)

# keys the context can hold — each must match a command's option name so it can
# be injected as that option's default.
KNOWN_KEYS = ["project", "user", "assignee", "author", "status", "priority", "query"]


@app.command("set")
def set_context(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P", help="Default project."),
    user: str = typer.Option(None, "--user", "-u", help="Default user (time/cost)."),
    assignee: str = typer.Option(None, "--assignee", "-a", help="Default assignee."),
    author: str = typer.Option(None, "--author", help="Default author."),
    status: str = typer.Option(None, "--status", "-s", help="Default status filter."),
    priority: str = typer.Option(None, "--priority", help="Default priority."),
    query: str = typer.Option(None, "--query", "-q", help="Default text query (wp list)."),
    extra: list[str] = typer.Option(None, "--set", help="Generic key=value (repeatable)."),
) -> None:
    """Set/merge sticky defaults. Applies to later commands' matching options.

    Example: openproject context set --project webshop --assignee me
    Then `openproject wp list` behaves like `wp list --project webshop --assignee me`.
    """
    obj = ctx_obj(ctx)
    cfg = Config.load()
    updates = {
        k: v for k, v in (
            ("project", project), ("user", user), ("assignee", assignee), ("author", author),
            ("status", status), ("priority", priority), ("query", query),
        ) if v is not None
    }
    for item in extra or []:
        if "=" not in item:
            raise OpError(f"--set expects key=value, got '{item}'")
        k, v = item.split("=", 1)
        updates[k.strip()] = v.strip()
    if not updates:
        raise OpError("nothing to set — pass e.g. --project X or --set key=value")
    cfg.context.update(updates)
    cfg.save()
    obj.emitter.emit({"status": "context updated", "context": cfg.context})


@app.command()
def show(ctx: typer.Context) -> None:
    """Show the active context (the defaults currently applied)."""
    obj = ctx_obj(ctx)
    cfg = Config.load()
    obj.emitter.emit({"context": cfg.context, "saved": sorted(cfg.contexts), "configPath": str(config_path())})


@app.command()
def unset(ctx: typer.Context, key: str = typer.Argument(..., help="Context key to remove.")) -> None:
    """Remove one key from the active context."""
    obj = ctx_obj(ctx)
    cfg = Config.load()
    cfg.context.pop(key, None)
    cfg.save()
    obj.emitter.emit({"status": "unset", "key": key, "context": cfg.context})


@app.command()
def clear(ctx: typer.Context) -> None:
    """Clear the active context entirely."""
    obj = ctx_obj(ctx)
    cfg = Config.load()
    cfg.context = {}
    cfg.save()
    obj.emitter.emit({"status": "context cleared"})


@app.command()
def save(ctx: typer.Context, name: str = typer.Argument(..., help="Name to save the current context as.")) -> None:
    """Save the active context under a name for later reuse."""
    obj = ctx_obj(ctx)
    cfg = Config.load()
    if not cfg.context:
        raise OpError("active context is empty — set something first with `context set`")
    cfg.contexts[name] = dict(cfg.context)
    cfg.save()
    obj.emitter.emit({"status": "saved", "name": name, "context": cfg.context})


@app.command()
def use(ctx: typer.Context, name: str = typer.Argument(..., help="Saved context to activate.")) -> None:
    """Load a saved context as the active one."""
    obj = ctx_obj(ctx)
    cfg = Config.load()
    if name not in cfg.contexts:
        raise OpError(f"no saved context '{name}'. Saved: {', '.join(sorted(cfg.contexts)) or '(none)'}")
    cfg.context = dict(cfg.contexts[name])
    cfg.save()
    obj.emitter.emit({"status": "active", "name": name, "context": cfg.context})


@app.command("list")
def list_contexts(ctx: typer.Context) -> None:
    """List saved contexts."""
    obj = ctx_obj(ctx)
    cfg = Config.load()
    rows = [{"name": n, "context": c} for n, c in sorted(cfg.contexts.items())]
    obj.emitter.emit(rows, columns=[("Name", "name"), ("Context", lambda r: ", ".join(f"{k}={v}" for k, v in r["context"].items()))], empty="(no saved contexts)")


@app.command()
def rm(ctx: typer.Context, name: str = typer.Argument(..., help="Saved context to delete.")) -> None:
    """Delete a saved context."""
    obj = ctx_obj(ctx)
    cfg = Config.load()
    cfg.contexts.pop(name, None)
    cfg.save()
    obj.emitter.emit({"status": "deleted", "name": name})
