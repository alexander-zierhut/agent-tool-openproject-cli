"""Manage CLI settings — most importantly the default output format."""

from __future__ import annotations

import typer

from ..spec import credentials
from ..config import Config, config_path
from agentcli.errors import OpError
from agentcli.output import OutputFormat
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)


@app.command()
def show(ctx: typer.Context) -> None:
    """Show current settings (default format, active profile, config location)."""
    obj = ctx_obj(ctx)
    cfg = obj.config
    obj.emitter.emit(
        {
            "configPath": str(config_path()),
            "defaultFormat": cfg.default_format or "(not set — defaults to json)",
            "activeProfile": cfg.active_profile_name(),
            "profiles": sorted(cfg.profiles.keys()),
            "credentialBackend": credentials.backend_name(),
            "costCutoffField": cfg.cost_cutoff_field or "(not set)",
            "costBillableField": cfg.cost_billable_field or "(not set)",
        }
    )


@app.command("set-format")
def set_format(
    ctx: typer.Context,
    fmt: str = typer.Argument(..., help="json | table | markdown (md)."),
) -> None:
    """Set the default output format used when no --format/-o is given."""
    obj = ctx_obj(ctx)
    try:
        chosen = OutputFormat.coerce(fmt)
    except ValueError as exc:
        raise OpError(str(exc)) from exc
    cfg = Config.load()  # reload to avoid clobbering concurrent changes
    cfg.default_format = chosen.value
    cfg.save()
    obj.emitter.emit({"status": "saved", "defaultFormat": chosen.value, "configPath": str(config_path())})


@app.command("get-format")
def get_format(ctx: typer.Context) -> None:
    """Print the effective default format."""
    obj = ctx_obj(ctx)
    obj.emitter.emit({"defaultFormat": obj.config.default_format or "json"})


@app.command("set-cutoff-field")
def set_cutoff_field(
    ctx: typer.Context,
    name: str = typer.Argument(..., help='Project date attribute holding the last-billed date, e.g. "Billed through".'),
) -> None:
    """Set the project attribute `cost open` reads as the billing cut-off date."""
    obj = ctx_obj(ctx)
    cfg = Config.load()
    cfg.cost_cutoff_field = name
    cfg.save()
    obj.emitter.emit({"status": "saved", "costCutoffField": name, "configPath": str(config_path())})


@app.command("set-billable-field")
def set_billable_field(
    ctx: typer.Context,
    name: str = typer.Argument(..., help='Project boolean attribute flagging billable projects, e.g. "Billable".'),
) -> None:
    """Set the project attribute `cost open` (without -P) uses to find billable projects."""
    obj = ctx_obj(ctx)
    cfg = Config.load()
    cfg.cost_billable_field = name
    cfg.save()
    obj.emitter.emit({"status": "saved", "costBillableField": name, "configPath": str(config_path())})


@app.command()
def path(ctx: typer.Context) -> None:
    """Print the config file path."""
    ctx_obj(ctx).emitter.emit({"configPath": str(config_path())})
