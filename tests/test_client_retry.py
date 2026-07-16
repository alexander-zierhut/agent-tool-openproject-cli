"""Unit tests for client retry/backoff and dry-run (mocked transport)."""

from __future__ import annotations

import httpx
import pytest

from opcli.client import Client
from agentcli.errors import ApiError, DryRun, NotFoundError


def _client(handler, **kw):
    c = Client("http://example", "tok", backoff=0.0, **kw)
    c._http.close()
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_retry_on_429_then_success():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"_type": "Error"})
        return httpx.Response(200, json={"ok": True})

    assert _client(handler, max_retries=3).get("work_packages") == {"ok": True}
    assert calls["n"] == 2  # one retry


def test_no_retry_on_404():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(404, json={"_type": "Error", "message": "nope"})

    with pytest.raises(NotFoundError):
        _client(handler, max_retries=3).get("work_packages/999")
    assert calls["n"] == 1  # 4xx (not 429) is not retried


def test_get_5xx_retries_then_gives_up():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(503)

    with pytest.raises(ApiError):
        _client(handler, max_retries=2).get("x")
    assert calls["n"] == 3  # initial + 2 retries


def test_post_5xx_not_retried():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(503)

    with pytest.raises(ApiError):
        _client(handler, max_retries=3).post("x", json={})
    assert calls["n"] == 1  # non-idempotent write not retried on 5xx


def test_post_429_is_retried():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(429) if calls["n"] == 1 else httpx.Response(201, json={"id": 1})

    assert _client(handler, max_retries=3).post("x", json={}) == {"id": 1}
    assert calls["n"] == 2  # 429 means rejected -> safe to retry


def test_dry_run_intercepts_writes():
    c = Client("http://example", "tok", dry_run=True)
    with pytest.raises(DryRun) as exc:
        c.post("work_packages", json={"subject": "x"})
    assert exc.value.request["method"] == "POST"
    assert exc.value.request["body"] == {"subject": "x"}
    with pytest.raises(DryRun):
        c.delete("work_packages/1")
    with pytest.raises(DryRun):
        c.patch("work_packages/1", json={"a": 1})
