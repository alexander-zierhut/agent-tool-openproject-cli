"""Authentication commands: login, logout, status, whoami."""

from __future__ import annotations

import os

import typer

from .. import serialize
from ..spec import credentials
from ..client import Client
from ..config import Profile
from agentcli.errors import AuthError, OpError
from ._shared import ctx_obj

app = typer.Typer(no_args_is_help=True)


@app.command()
def login(
    ctx: typer.Context,
    url: str = typer.Option(None, "--url", "-u", help="Base URL, e.g. https://op.example.com"),
    token: str = typer.Option(None, "--token", "-t", help="API token (prompted if omitted)."),
    name: str = typer.Option(None, "--name", help="Profile name to store under."),
    username: str = typer.Option(None, "--username", help="Informational: the API user's login."),
    no_verify_ssl: bool = typer.Option(False, "--no-verify-ssl", help="Skip TLS verification."),
) -> None:
    """Verify and store an API token securely (OS keyring by default).

    Non-interactive example:
      openproject auth login --url http://localhost:8090 --token opapi-xxxx
    """
    obj = ctx_obj(ctx)
    profile_name = name or os.environ.get("OPCLI_PROFILE") or obj.config.current_profile or "default"

    base_url = url or os.environ.get("OPCLI_BASE_URL")
    if not base_url:
        base_url = typer.prompt("OpenProject base URL")
    if not token:
        token = os.environ.get("OPCLI_TOKEN") or typer.prompt("API token", hide_input=True)

    # Verify before persisting anything.
    with Client(base_url, token, verify_ssl=not no_verify_ssl) as client:
        try:
            me = client.me()
        except AuthError as exc:
            raise AuthError(f"login failed: {exc.message}") from exc

    prof = Profile(
        name=profile_name,
        base_url=base_url,
        username=username or me.get("login"),
        verify_ssl=not no_verify_ssl,
    )
    obj.config.upsert_profile(prof, make_current=True)
    obj.config.save()
    backend = credentials.store_token(profile_name, token)

    obj.emitter.emit(
        {
            "status": "logged in",
            "profile": profile_name,
            "baseUrl": base_url,
            "user": serialize.user(me),
            "tokenStoredIn": backend,
        }
    )


@app.command()
def status(ctx: typer.Context) -> None:
    """Show the active profile, credential backend, and connectivity."""
    obj = ctx_obj(ctx)
    try:
        prof = obj.profile()
    except OpError as exc:
        obj.emitter.emit({"configured": False, "reason": exc.message})
        return

    info = {
        "profile": prof.name,
        "baseUrl": prof.base_url,
        "username": prof.username,
        "verifySsl": prof.verify_ssl,
        "credentialBackend": credentials.backend_name(),
        "hasToken": bool(obj.token()),
    }
    if obj.token():
        try:
            info["reachable"] = True
            info["me"] = serialize.user(obj.client().me())
        except OpError as exc:
            info["reachable"] = False
            info["error"] = exc.message
    obj.emitter.emit(info)


@app.command()
def whoami(ctx: typer.Context) -> None:
    """Print the authenticated user (GET /users/me)."""
    obj = ctx_obj(ctx)
    obj.emitter.emit(serialize.user(obj.client().me()))


@app.command()
def logout(
    ctx: typer.Context,
    name: str = typer.Option(None, "--name", help="Profile to log out (defaults to active)."),
) -> None:
    """Remove the stored API token for a profile."""
    obj = ctx_obj(ctx)
    profile_name = name or obj.config.active_profile_name()
    credentials.delete_token(profile_name)
    obj.emitter.emit({"status": "logged out", "profile": profile_name})
