"""Non-secret configuration: connection profiles.

Config lives in a plain JSON file (``~/.config/op-cli/config.json`` by
default). It never contains the API token — that is kept in the OS keyring by
:mod:`opcli.credentials`. Multiple named *profiles* let one operator point the
CLI at several OpenProject instances (e.g. ``prod`` and ``staging``).

Environment overrides (useful for CI and the test-suite):

* ``OPCLI_BASE_URL`` — overrides the active profile's base URL.
* ``OPCLI_PROFILE``  — selects the active profile.
* ``OPCLI_TOKEN``    — supplies the token directly (see :mod:`credentials`).
* ``OPCLI_CONFIG_DIR`` / ``XDG_CONFIG_HOME`` — relocate the config directory.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigError

DEFAULT_PROFILE = "default"


def config_dir() -> Path:
    base = os.environ.get("OPCLI_CONFIG_DIR")
    if base:
        return Path(base)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    root = Path(xdg) if xdg else Path.home() / ".config"
    return root / "op-cli"


def config_path() -> Path:
    return config_dir() / "config.json"


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
            )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ConfigError(f"malformed config at {path}: {exc}") from exc

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "current_profile": self.current_profile,
            "default_format": self.default_format,
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
        return os.environ.get("OPCLI_PROFILE") or self.current_profile

    def resolve(self) -> Profile:
        """Return the effective profile, applying env overrides.

        A profile can be fully synthesised from the environment even with no
        config file on disk, so ``OPCLI_BASE_URL`` + ``OPCLI_TOKEN`` are enough
        to run the CLI headless.
        """
        name = self.active_profile_name()
        env_url = os.environ.get("OPCLI_BASE_URL")

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
