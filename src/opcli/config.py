"""Non-secret configuration: connection profiles.

Config lives in a plain JSON file (``~/.config/op-cli/config.json`` by
default). It never contains the API token — that is kept in the OS keyring by
``agentcli.Credentials`` (see :mod:`opcli.spec`). Multiple named *profiles* let
one operator point the CLI at several OpenProject instances (e.g. ``prod`` and
``staging``).

Environment overrides (useful for CI and the test-suite):

* ``OPCLI_BASE_URL`` — overrides the active profile's base URL.
* ``OPCLI_PROFILE``  — selects the active profile.
* ``OPCLI_TOKEN``    — supplies the token directly.
* ``OPCLI_CONFIG_DIR`` / ``XDG_CONFIG_HOME`` — relocate the config directory.

All of those names, and the directory itself, come from :data:`opcli.spec.SPEC`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentcli.errors import ConfigError

from .spec import SPEC

DEFAULT_PROFILE = "default"


# Thin wrappers over the single source of truth in SPEC. Before the extraction
# this logic existed TWICE — here and in credentials.py — with nothing forcing
# the two copies to agree, so relocating the config dir could put the token and
# the profile in different directories.
def config_dir() -> Path:
    return SPEC.config_dir()


def config_path() -> Path:
    return SPEC.config_file()


@dataclass
class Profile:
    name: str
    base_url: str
    username: str | None = None  # informational; the login of the API user
    verify_ssl: bool = True

    def api_root(self) -> str:
        return self.base_url.rstrip("/") + "/api/v3"


@dataclass
class Config:
    current_profile: str = DEFAULT_PROFILE
    profiles: dict[str, Profile] = field(default_factory=dict)
    default_format: str | None = None  # json | table | markdown; None = not yet chosen
    claude_prompted: bool = False  # have we offered the Claude Code skill install yet?
    # `cost open` needs to know which instance-specific project attributes hold the
    # last-billed date and the billable flag; they are named per instance.
    cost_cutoff_field: str | None = None
    cost_billable_field: str | None = None
    # sticky session context: option-name -> default value, applied to later
    # commands (see `openproject context`). `contexts` holds named, saved ones.
    context: dict = field(default_factory=dict)
    contexts: dict = field(default_factory=dict)

    # ---- persistence -------------------------------------------------
    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text())
            profiles = {
                name: Profile(
                    name=name,
                    base_url=p["base_url"],
                    username=p.get("username"),
                    verify_ssl=p.get("verify_ssl", True),
                )
                for name, p in raw.get("profiles", {}).items()
            }
            return cls(
                current_profile=raw.get("current_profile", DEFAULT_PROFILE),
                profiles=profiles,
                default_format=raw.get("default_format"),
                claude_prompted=bool(raw.get("claude_prompted", False)),
                cost_cutoff_field=raw.get("cost_cutoff_field"),
                cost_billable_field=raw.get("cost_billable_field"),
                context=raw.get("context") or {},
                contexts=raw.get("contexts") or {},
            )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ConfigError(f"malformed config at {path}: {exc}") from exc

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "current_profile": self.current_profile,
            "default_format": self.default_format,
            "claude_prompted": self.claude_prompted,
            "cost_cutoff_field": self.cost_cutoff_field,
            "cost_billable_field": self.cost_billable_field,
            "context": self.context,
            "contexts": self.contexts,
            "profiles": {
                name: {
                    "base_url": p.base_url,
                    "username": p.username,
                    "verify_ssl": p.verify_ssl,
                }
                for name, p in self.profiles.items()
            },
        }
        path.write_text(json.dumps(data, indent=2) + "\n")

    # ---- resolution --------------------------------------------------
    def active_profile_name(self) -> str:
        return SPEC.getenv("PROFILE") or self.current_profile

    def resolve(self) -> Profile:
        """Return the effective profile, applying env overrides.

        A profile can be fully synthesised from the environment even with no
        config file on disk, so ``OPCLI_BASE_URL`` + ``OPCLI_TOKEN`` are enough
        to run the CLI headless.
        """
        name = self.active_profile_name()
        env_url = SPEC.getenv("BASE_URL")

        prof = self.profiles.get(name)
        if prof is None:
            if env_url:
                return Profile(name=name, base_url=env_url)
            raise ConfigError(
                f"no profile '{name}' configured. Run `openproject auth login` or set OPCLI_BASE_URL."
            )
        if env_url:
            return Profile(
                name=prof.name,
                base_url=env_url,
                username=prof.username,
                verify_ssl=prof.verify_ssl,
            )
        return prof

    def upsert_profile(self, prof: Profile, make_current: bool = True) -> None:
        self.profiles[prof.name] = prof
        if make_current:
            self.current_profile = prof.name
