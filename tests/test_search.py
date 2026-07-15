"""Work-package search: full text, filters, count, sort."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


def test_full_text_search(op, project):
    token = f"needle{uuid.uuid4().hex[:8]}"
    created = op(["wp", "create", f"Find this {token}", "--project", project["identifier"]]).ok().json
    try:
        found = op(["search", "wp", token, "--limit", "10"]).ok().json
        assert any(w["id"] == created["id"] for w in found)
    finally:
        op(["wp", "delete", str(created["id"]), "-y"])


def test_filter_by_project_and_count(op, project, wp):
    count = op(["search", "wp", "--project", project["identifier"], "--all", "--count"]).ok().json
    assert count["total"] >= 1


def test_filter_by_status_open(op, project, wp):
    # wp is freshly created -> open. Restrict to this project to avoid noise.
    results = op(["search", "wp", "--project", project["identifier"], "--status", "open", "--limit", "0"]).ok().json
    assert any(w["id"] == wp["id"] for w in results)


def test_list_command(op, project, wp):
    rows = op(["wp", "list", "--project", project["identifier"], "--all", "--limit", "0"]).ok().json
    assert any(w["id"] == wp["id"] for w in rows)


def test_raw_filters_passthrough(op, project, wp):
    filt = __import__("json").dumps([{"project": {"operator": "=", "values": [str(project["id"])]}}])
    rows = op(["search", "wp", "--filters", filt, "--limit", "0"]).ok().json
    assert any(w["id"] == wp["id"] for w in rows)


def test_pagination_spans_multiple_pages(project):
    """Client.collect must return every item even when pageSize forces >1 page
    (regression: don't stop on a short page — the server may cap pageSize)."""
    import json
    import os

    from opcli.client import Client

    client = Client(os.environ["OPCLI_BASE_URL"], os.environ["OPCLI_TOKEN"])
    created = []
    try:
        for i in range(5):
            w = client.post(
                "work_packages",
                json={
                    "subject": f"page {i}",
                    "_links": {
                        "project": {"href": f"/api/v3/projects/{project['id']}"},
                        "type": {"href": "/api/v3/types/1"},
                    },
                },
            )
            created.append(w["id"])
        filt = json.dumps([{"project": {"operator": "=", "values": [str(project["id"])]}}])
        got = client.collect("work_packages", params={"filters": filt}, page_size=2)
        got_ids = {w["id"] for w in got}
        assert set(created) <= got_ids
    finally:
        for wid in created:
            client.delete(f"work_packages/{wid}")
        client.close()
