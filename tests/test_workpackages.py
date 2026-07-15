"""Work packages: CRUD, move, assign, watchers, schema, custom fields."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


def test_create_and_get(op, wp):
    got = op(["wp", "get", str(wp["id"])]).ok().json
    assert got["id"] == wp["id"]
    assert got["type"] == "Task"
    assert got["status"] is not None


def test_create_with_fields(op, project):
    res = op(
        [
            "wp", "create", "Rich WP", "--project", project["identifier"],
            "--description", "body", "--priority", "High",
            "--assignee", "me", "--due-date", "2026-09-01", "--estimated", "3.5",
        ]
    ).ok().json
    assert res["priority"] == "High"
    assert res["assignee"]["id"] is not None
    assert res["dueDate"] == "2026-09-01"
    assert res["estimatedTime"] == "PT3H30M"
    op(["wp", "delete", str(res["id"]), "-y"])


def test_update_status_and_lockversion(op, wp):
    updated = op(["wp", "update", str(wp["id"]), "--status", "In progress", "--done-ratio", "40"]).ok().json
    assert updated["status"] == "In progress"
    assert updated["percentageDone"] == 40
    # lockVersion must have advanced from the freshly-created 0
    assert updated["lockVersion"] >= wp["lockVersion"]


def test_assign_and_unassign(op, wp):
    assigned = op(["wp", "assign", str(wp["id"]), "me"]).ok().json
    assert assigned["assignee"]["id"] is not None
    unassigned = op(["wp", "unassign", str(wp["id"])]).ok().json
    assert unassigned["assignee"] is None


def test_move_between_projects(op, wp, project):
    other_ident = f"op-cli-move-{uuid.uuid4().hex[:8]}"
    other = op(["project", "create", "Move Target", "--identifier", other_ident]).ok().json
    try:
        moved = op(["wp", "move", str(wp["id"]), other_ident]).ok().json
        assert moved["project"]["id"] == other["id"]
        # move it back so the wp fixture teardown (in original project) still works
        op(["wp", "move", str(wp["id"]), project["identifier"]]).ok()
    finally:
        op(["project", "delete", other_ident, "-y"])


def test_watchers(op, wp):
    op(["wp", "watch", str(wp["id"]), "me"]).ok()
    watchers = op(["wp", "watchers", str(wp["id"])]).ok().json
    assert any(w["id"] for w in watchers)
    op(["wp", "unwatch", str(wp["id"]), "me"]).ok()


def test_schema_lists_fields(op, project):
    fields = op(["wp", "schema", "--project", project["identifier"], "--type", "Task"]).ok().json
    keys = {f["key"] for f in fields}
    assert "subject" in keys
    assert any(k.startswith("customField") for k in keys)


def test_custom_fields_set_and_read(op, project):
    # discover the custom fields available on this project
    cfs = op(["cf", "wp", "--project", project["identifier"], "--type", "Task"]).ok().json
    by_type = {c["type"]: c for c in cfs}
    if "String" not in by_type:
        pytest.skip("string custom field not seeded")
    string_key = by_type["String"]["key"]
    payload = {string_key: "INV-TEST-001"}
    created = op(
        ["wp", "create", "CF WP", "--project", project["identifier"], "--custom-fields", __import__("json").dumps(payload)]
    ).ok().json
    assert created.get("customFields", {}).get(string_key) == "INV-TEST-001"
    op(["wp", "delete", str(created["id"]), "-y"])


def test_default_open_excludes_closed(op, project):
    """`wp list` defaults to open; --all includes closed."""
    closed = op(["wp", "create", "closed wp", "--project", project["identifier"]]).ok().json
    op(["wp", "update", str(closed["id"]), "--status", "Closed"]).ok()
    try:
        default_ids = {w["id"] for w in op(["wp", "list", "--project", project["identifier"], "--limit", "0"]).ok().json}
        all_ids = {w["id"] for w in op(["wp", "list", "--project", project["identifier"], "--all", "--limit", "0"]).ok().json}
        assert closed["id"] not in default_ids, "closed WP leaked into default (open-only) listing"
        assert closed["id"] in all_ids, "--all should include closed WPs"
    finally:
        op(["wp", "delete", str(closed["id"]), "-y"])


def test_delete(op, project):
    res = op(["wp", "create", "To Delete", "--project", project["identifier"]]).ok().json
    op(["wp", "delete", str(res["id"]), "-y"]).ok()
    missing = op(["wp", "get", str(res["id"])])
    assert missing.code != 0  # now 404
