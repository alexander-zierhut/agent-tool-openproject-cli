"""The shared application context stored on Typer's ``ctx.obj``.

Wires together configuration, stored credentials, the HTTP client, and the
output emitter so every command can reach them without re-plumbing.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from . import credentials
from .client import Client
from .config import Config, Profile
from .errors import AuthError
from .output import Emitter, OutputFormat


class AppContext:
    def __init__(
        self,
        output: Optional[OutputFormat] = None,
        color: bool = True,
        *,
        interactive: Optional[bool] = None,
    ):
        self.config = Config.load()
        fmt = self._resolve_format(output, interactive)
        env_fields = os.environ.get("OPCLI_CLI_FIELDS")
        fields = env_fields.split(",") if env_fields else None
        self.emitter = Emitter(fmt, color=color, fields=fields)
        self._client: Optional[Client] = None

    # ---- output-format resolution ------------------------------------
    def _resolve_format(self, output: Optional[OutputFormat], interactive: Optional[bool]) -> OutputFormat:
        """Precedence: --format anywhere > -o/--output > $OPCLI_FORMAT >
        saved default > first-run prompt (interactive) > json."""
        cli = os.environ.get("OPCLI_CLI_FORMAT")  # set by `--format/-f` (main pre-parse)
        if cli:
            try:
                return OutputFormat.coerce(cli)
            except ValueError:
                pass
        if output is not None:
            return output
        env = os.environ.get("OPCLI_FORMAT")
        if env:
            try:
                return OutputFormat.coerce(env)
            except ValueError:
                pass
        if self.config.default_format:
            try:
                return OutputFormat.coerce(self.config.default_format)
            except ValueError:
                pass
        if interactive is None:
            interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if interactive:
            chosen = self._prompt_default_format()
            if chosen is not None:
                self.config.default_format = chosen.value
                try:
                    self.config.save()
                except Exception:
                    pass
                return chosen
        return OutputFormat.json

    def _prompt_default_format(self) -> Optional[OutputFormat]:
        # Prompt on stderr so stdout (the real command output) stays clean.
        try:
            sys.stderr.write(
                "\nFirst run — choose a default output format (saved for next time):\n"
                "  1) json      structured, best for scripts & agents (default)\n"
                "  2) table     human-readable terminal tables\n"
                "  3) markdown  paste-into-docs tables\n"
                "Enter 1/2/3 [1]: "
            )
            sys.stderr.flush()
            ans = sys.stdin.readline().strip().lower()
        except Exception:
            return None
        return {
            "": OutputFormat.json, "1": OutputFormat.json, "json": OutputFormat.json,
            "2": OutputFormat.table, "table": OutputFormat.table,
            "3": OutputFormat.markdown, "markdown": OutputFormat.markdown, "md": OutputFormat.markdown,
        }.get(ans, OutputFormat.json)

    @property
    def output(self) -> OutputFormat:
        return self.emitter.fmt

    def profile(self) -> Profile:
        return self.config.resolve()

    def token(self) -> Optional[str]:
        return credentials.get_token(self.config.active_profile_name())

    def client(self) -> Client:
        if self._client is not None:
            return self._client
        prof = self.profile()
        token = self.token()
        if not token:
            raise AuthError(
                f"no API token for profile '{prof.name}'. Run `openproject auth login` "
                f"(or set OPCLI_TOKEN)."
            )
        self._client = Client(prof.base_url, token, verify_ssl=prof.verify_ssl)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
