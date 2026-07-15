"""Secure storage of OpenProject API tokens.

Order of preference for reading a token:

1. The ``OPCLI_TOKEN`` environment variable (used by CI / the test suite and
   handy for one-off scripting).
2. The operating-system keyring (Secret Service / macOS Keychain / Windows
   Credential Locker) via the :mod:`keyring` library — the safe default.
3. A ``0600`` fallback file in the config directory, used only when no real
   keyring backend is available (headless boxes without a Secret Service).
   We warn loudly in that case because the token is stored in clear text.

The token is the only secret we persist. Everything else (base URL, the API
username, TLS options) lives in the plain-text config file.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

KEYRING_SERVICE = "op-cli"
ENV_TOKEN = "OPCLI_TOKEN"


def _config_dir() -> Path:
    base = os.environ.get("OPCLI_CONFIG_DIR")
    if base:
        return Path(base)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    root = Path(xdg) if xdg else Path.home() / ".config"
    return root / "op-cli"


def _fallback_file() -> Path:
    return _config_dir() / "credentials.json"


def _keyring_available() -> bool:
    try:
        import keyring
        from keyring.backends import fail

        return not isinstance(keyring.get_keyring(), fail.Keyring)
    except Exception:
        return False


def _read_fallback() -> dict[str, str]:
    path = _fallback_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _write_fallback(data: dict[str, str]) -> None:
    path = _fallback_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create with 0600 from the start so the plaintext token is never briefly
    # world-readable (mode 0o600 has no group/other bits, so umask can't widen it).
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600 (also fixes a pre-existing file)
    except OSError:
        pass


def backend_name() -> str:
    """Human-readable name of the active secret backend (for `auth status`)."""
    if os.environ.get(ENV_TOKEN):
        return f"environment variable ${ENV_TOKEN}"
    if _keyring_available():
        try:
            import keyring

            return f"OS keyring ({keyring.get_keyring().__class__.__name__})"
        except Exception:
            pass
    return f"plaintext fallback file ({_fallback_file()})"


def store_token(profile: str, token: str) -> str:
    """Persist *token* for *profile*. Returns the backend used."""
    if _keyring_available():
        try:
            import keyring

            keyring.set_password(KEYRING_SERVICE, profile, token)
            return "keyring"
        except Exception as exc:  # pragma: no cover - depends on host
            print(f"warning: keyring store failed ({exc}); using fallback file", file=sys.stderr)
    data = _read_fallback()
    data[profile] = token
    _write_fallback(data)
    print(
        f"warning: no OS keyring available — token stored in clear text at {_fallback_file()} (0600)",
        file=sys.stderr,
    )
    return "file"


def get_token(profile: str) -> str | None:
    """Resolve the token for *profile*, honouring the env override first."""
    env = os.environ.get(ENV_TOKEN)
    if env:
        return env
    if _keyring_available():
        try:
            import keyring

            tok = keyring.get_password(KEYRING_SERVICE, profile)
            if tok:
                return tok
        except Exception:
            pass
    return _read_fallback().get(profile)


def delete_token(profile: str) -> None:
    """Remove any stored token for *profile* from every backend."""
    if _keyring_available():
        try:
            import keyring

            keyring.delete_password(KEYRING_SERVICE, profile)
        except Exception:
            pass
    data = _read_fallback()
    if profile in data:
        del data[profile]
        _write_fallback(data)
