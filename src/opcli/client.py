"""Thin, robust HTTP client for the OpenProject API v3 (HAL+JSON).

Responsibilities:

* Basic-auth with ``apikey:<token>`` (the standard OpenProject API-key scheme).
* Normalising paths so callers may pass ``"work_packages"``,
  ``"/api/v3/work_packages/1"`` or a full URL interchangeably (following the
  ``href`` values the API returns "just works").
* Turning HAL error bodies into typed :class:`opcli.errors.OpError` subclasses.
* Auto-pagination of collection endpoints.
* Optimistic-locking updates (fetch ``lockVersion`` → PATCH → retry on 409).
* JSON *and* multipart requests (the latter for attachment uploads).
"""

from __future__ import annotations

import json as jsonlib
from typing import Any, Callable, Iterator

import httpx

from . import hal
from .errors import (
    ApiError,
    AuthError,
    ConflictError,
    NotFoundError,
    OpError,
    ValidationError,
)

Json = dict[str, Any]

USER_AGENT = "openproject-cli/0.1"


class Client:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        verify_ssl: bool = True,
        timeout: float = 60.0,
    ):
        self.base = base_url.rstrip("/")
        self.api_root = self.base + "/api/v3"
        self._http = httpx.Client(
            auth=httpx.BasicAuth("apikey", token),
            verify=verify_ssl,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    # ---- lifecycle ---------------------------------------------------
    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ---- url handling ------------------------------------------------
    def url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/"):
            return self.base + path
        return self.api_root + "/" + path

    # ---- low-level request -------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: dict[str, Any] | None = None,
        files: Any = None,
        headers: dict[str, str] | None = None,
        parse: bool = True,
    ) -> Any:
        url = self.url(path)
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        # OpenProject rejects body-less writes with 406 unless a JSON content-type
        # is present. Set it for JSON writes (but never for multipart uploads,
        # where httpx must supply the multipart boundary itself).
        eff_headers = dict(headers or {})
        if files is None and method.upper() in ("POST", "PATCH", "PUT"):
            eff_headers.setdefault("Content-Type", "application/json")
        try:
            resp = self._http.request(
                method,
                url,
                params=clean_params or None,
                json=json,
                data=data,
                files=files,
                headers=eff_headers or None,
            )
        except httpx.ConnectError as exc:
            raise ApiError(f"cannot connect to {self.base}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ApiError(f"request to {url} failed: {exc}") from exc

        if resp.status_code >= 400:
            self._raise_for_error(resp)

        if not parse:
            return resp
        if resp.status_code == 204 or not resp.content:
            return {}
        ctype = resp.headers.get("content-type", "")
        if "json" in ctype:
            return resp.json()
        return resp.content

    # ---- error mapping -----------------------------------------------
    def _raise_for_error(self, resp: httpx.Response) -> None:
        status = resp.status_code
        payload: Any = None
        message = f"HTTP {status}"
        field_errors = None
        try:
            payload = resp.json()
        except Exception:
            payload = resp.text or None

        if isinstance(payload, dict) and payload.get("_type") == "Error":
            message = payload.get("message", message)
            embedded = (payload.get("_embedded") or {}).get("errors")
            if isinstance(embedded, list) and embedded:
                field_errors = [e.get("message") for e in embedded if isinstance(e, dict)]
                message = "; ".join(m for m in field_errors if m) or message

        if status in (401,):
            raise AuthError(
                message if message != f"HTTP {status}" else "authentication failed — check your API token",
                detail=payload,
            )
        if status in (403,):
            raise AuthError(
                message if message != f"HTTP {status}" else "forbidden — the API user lacks permission",
                detail=payload,
            )
        if status == 404:
            raise NotFoundError(message if message != f"HTTP {status}" else "resource not found", detail=payload)
        if status == 409:
            raise ConflictError(message, detail=payload)
        if status == 422:
            raise ValidationError(message, detail=payload, field_errors=field_errors)
        raise ApiError(message, status=status, detail=payload)

    # ---- verb helpers ------------------------------------------------
    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Json:
        return self.request("GET", path, params=params)

    def post(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Json:
        return self.request("POST", path, json=json, params=params)

    def patch(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Json:
        return self.request("PATCH", path, json=json, params=params)

    def delete(self, path: str, *, params: dict[str, Any] | None = None) -> Json:
        return self.request("DELETE", path, params=params)

    # ---- collections / pagination ------------------------------------
    def paginate(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        page_size: int = 100,
        limit: int | None = None,
    ) -> Iterator[Json]:
        """Yield every element of a collection endpoint, following pages.

        OpenProject paginates with 1-based ``offset`` (page number) and
        ``pageSize``. We stop when we've seen ``total`` items, an empty page,
        or reached ``limit``.

        Note: the server may cap ``pageSize`` below what we ask for, so we must
        NOT stop merely because a page came back shorter than requested — we
        rely on the authoritative ``total`` and on an empty page instead.
        """
        offset = 1
        seen = 0
        # guard against a server that never advances (pathological) — bounded by total
        while True:
            page_params = dict(params or {})
            page_params["offset"] = offset
            page_params["pageSize"] = page_size
            doc = self.get(path, params=page_params)
            batch = hal.elements(doc)
            if not batch:
                break
            for el in batch:
                yield el
                seen += 1
                if limit is not None and seen >= limit:
                    return
            if seen >= hal.total(doc):
                break
            offset += 1

    def collect(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        page_size: int = 100,
        limit: int | None = None,
    ) -> list[Json]:
        return list(self.paginate(path, params=params, page_size=page_size, limit=limit))

    # ---- optimistic-locking update -----------------------------------
    def update_locked(
        self,
        path: str,
        patch: Json | Callable[[Json], Json],
        *,
        params: dict[str, Any] | None = None,
        retries: int = 2,
    ) -> Json:
        """PATCH a resource, supplying the current ``lockVersion`` automatically.

        ``patch`` may be a dict, or a callable receiving the freshly-fetched
        resource and returning the patch body (useful when the new value
        depends on the old one). Retries on 409 conflicts.
        """
        last_exc: OpError | None = None
        for _ in range(retries + 1):
            current = self.get(path)
            body = patch(current) if callable(patch) else jsonlib.loads(jsonlib.dumps(patch))
            lv = current.get("lockVersion")
            if lv is not None:
                body.setdefault("lockVersion", lv)
            try:
                return self.patch(path, json=body, params=params)
            except ConflictError as exc:
                last_exc = exc
                continue
        assert last_exc is not None
        raise last_exc

    # ---- convenience -------------------------------------------------
    def me(self) -> Json:
        return self.get("users/me")
