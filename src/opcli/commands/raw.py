"""Escape hatch: call any OpenProject API v3 endpoint directly.

Useful for the agent to reach endpoints the typed commands don't wrap yet, and
for debugging. Paths may be given as ``work_packages/1`` or
``/api/v3/work_packages/1``. Bodies and query params are passed as JSON.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ._shared import ctx_obj, parse_json_option

app = typer.Typer(no_args_is_help=True)


def _params(param: list[str]) -> dict:
    out: dict = {}
    for item in param or []:
        if "=" not in item:
            raise typer.BadParameter(f"--param must be key=value, got '{item}'")
        k, v = item.split("=", 1)
        out[k] = v
    return out


def _body(data: str | None, data_file: Path | None):
    if data_file is not None:
        return parse_json_option(data_file.read_text(), what="--data-file")
    return parse_json_option(data, what="--data")


def _run(ctx: typer.Context, method: str, path: str, param, data, data_file):
    obj = ctx_obj(ctx)
    result = obj.client().request(method, path, params=_params(param), json=_body(data, data_file))
    obj.emitter.emit(result)


@app.command()
def get(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="API path, e.g. work_packages/1 or statuses."),
    param: list[str] = typer.Option(None, "--param", "-p", help="Query param key=value (repeatable)."),
) -> None:
    """GET an endpoint."""
    _run(ctx, "GET", path, param, None, None)


@app.command()
def post(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="API path."),
    data: str = typer.Option(None, "--data", "-d", help="JSON request body."),
    data_file: Path = typer.Option(None, "--data-file", help="File containing the JSON body."),
    param: list[str] = typer.Option(None, "--param", "-p", help="Query param key=value (repeatable)."),
) -> None:
    """POST to an endpoint."""
    _run(ctx, "POST", path, param, data, data_file)


@app.command()
def patch(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="API path."),
    data: str = typer.Option(None, "--data", "-d", help="JSON request body."),
    data_file: Path = typer.Option(None, "--data-file", help="File containing the JSON body."),
    param: list[str] = typer.Option(None, "--param", "-p", help="Query param key=value (repeatable)."),
) -> None:
    """PATCH an endpoint. For work packages you MUST include the current lockVersion in the body
    (fetch it with `raw get work_packages/<id>` first) — unlike `wp update`, which handles it."""
    _run(ctx, "PATCH", path, param, data, data_file)


@app.command()
def delete(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="API path."),
    param: list[str] = typer.Option(None, "--param", "-p", help="Query param key=value (repeatable)."),
) -> None:
    """DELETE an endpoint."""
    _run(ctx, "DELETE", path, param, None, None)
