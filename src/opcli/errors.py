"""Exception types for the OpenProject CLI.

Every user-facing failure funnels through :class:`OpError` so the CLI entry
point can render a single, clean error line (and a JSON error object when
``--output json`` is active) instead of a Python traceback.
"""

from __future__ import annotations

from typing import Any


class OpError(Exception):
    """Base class for all expected, user-facing errors."""

    exit_code = 1

    def __init__(self, message: str, *, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.message}
        if self.detail is not None:
            out["detail"] = self.detail
        return out


class ConfigError(OpError):
    """Something is wrong with configuration or stored credentials."""

    exit_code = 3


class AuthError(OpError):
    """Authentication/authorization failed (401/403)."""

    exit_code = 4


class NotFoundError(OpError):
    """A requested resource does not exist (404)."""

    exit_code = 5


class ConflictError(OpError):
    """Optimistic-locking or uniqueness conflict (409/422 stale lockVersion)."""

    exit_code = 6


class ValidationError(OpError):
    """The server rejected the request payload (422)."""

    exit_code = 7

    def __init__(self, message: str, *, detail: Any = None, field_errors: Any = None):
        super().__init__(message, detail=detail)
        self.field_errors = field_errors

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        if self.field_errors:
            out["fieldErrors"] = self.field_errors
        return out


class ApiError(OpError):
    """A non-specific API error carrying the HTTP status and server payload."""

    def __init__(self, message: str, *, status: int | None = None, detail: Any = None):
        super().__init__(message, detail=detail)
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        if self.status is not None:
            out["status"] = self.status
        return out
