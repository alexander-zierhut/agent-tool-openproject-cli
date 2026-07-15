"""Additional integration coverage across command groups."""

from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.integration


# ---- work-package field updates ----
def test_update_subject(op, wp):
    r = op(["wp", "update", str(wp["id"]), "--subject", "renamed"]).ok().json
    assert r["subject"] == "renamed"


def test_update_priority(op, wp):
    r = op(["wp", "update", str(wp["id"]), "--priority", "High"]).ok().json
    assert r["priority"] == "High"


def test_update_description(op, wp):
    r = op(["wp", "update", str(wp["id"]), "--description", "new body"]).ok().json
    assert r["description"] == "new body"


def test_update_dates_and_done(op, wp):
    r = op(["wp", "update", str(wp["id"]), "--start-date", "2026-07-01", "--due-date", "2026-07-20", "--done-ratio", "60"]).ok().json
    assert r["startDate"] == "2026-07-01" and r["dueDate"] == "2026-07-20" and r["percentageDone"] == 60


def test_update_parent_and_detach(op, project, wp):
    parent = op(["wp", "create", "the parent", "--project", project["identifier"]]).ok().json
    try:
        r = op(["wp", "update", str(wp["id"]), "--parent", str(parent["id"])]).ok().json
        assert r["parent"]["id"] == parent["id"]
        r2 = op(["wp", "update", str(wp["id"]), "--parent", "none"]).ok().json
        assert r2["parent"] is None
    finally:
        op(["wp", "delete", str(parent["id"]), "-y"])


def test_update_custom_field(op, wp):
    cfs = op(["cf", "wp", "--project", "demo-project", "--type", "Task"]).ok().json
    string_cf = next((c for c in cfs if c["type"] == "String"), None)
    if not string_cf:
        pytest.skip("no string custom field seeded")
    r = op(["wp", "update", str(wp["id"]), "--custom-fields", json.dumps({string_cf["key"]: "CF-VALUE"})]).ok().json
    assert r.get("customFields", {}).get(string_cf["key"]) == "CF-VALUE"


def test_wp_schema_has_custom_fields(op, project):
    fields = op(["wp", "schema", "--project", project["identifier"], "--type", "Task"]).ok().json
    keys = {f["key"] for f in fields}
    assert "subject" in keys and any(k.startswith("customField") for k in keys)


# ---- projects ----
def test_project_update_multiple(op):
    ident = f"op-upd-{uuid.uuid4().hex[:8]}"
    op(["project", "create", "Upd", "--identifier", ident]).ok()
    try:
        r = op(["project", "update", ident, "--description", "changed", "--public"]).ok().json
        assert r["description"] == "changed" and r["public"] is True
    finally:
        op(["project", "delete", ident, "-y"])


# ---- time reporting ----
def test_time_report_by_project(op, wp):
    op(["time", "add", "2", "--work-package", str(wp["id"]), "--activity", "Development"]).ok()
    import datetime as dt

    month = dt.date.today().strftime("%Y-%m")
    rep = op(["cost", "report", "--month", month, "--user", "me"]).ok().json
    assert rep["totals"]["hours"] >= 2
    # each person breaks down by project
    assert any("projects" in u for u in rep["byUser"])


def test_time_activities_by_project(op, project):
    acts = op(["time", "activities", "--project", project["identifier"]]).ok().json
    assert any(a["name"] == "Development" for a in acts)


# ---- raw + lockVersion ----
def test_raw_patch_with_lockversion(op, project):
    body = json.dumps({"subject": "raw lock", "_links": {"project": {"href": f"/api/v3/projects/{project['id']}"}, "type": {"href": "/api/v3/types/1"}}})
    created = op(["raw", "post", "work_packages", "-d", body]).ok().json
    try:
        patch = json.dumps({"lockVersion": created["lockVersion"], "subject": "raw lock 2"})
        updated = op(["raw", "patch", f"work_packages/{created['id']}", "-d", patch]).ok().json
        assert updated["subject"] == "raw lock 2"
    finally:
        op(["raw", "delete", f"work_packages/{created['id']}"])


# ---- users / members ----
def test_user_get_by_login(op):
    u = op(["user", "get", "admin"]).ok().json
    assert u["login"] == "admin"


def test_user_list(op):
    users = op(["user", "list", "--limit", "50"]).ok().json
    assert any(u["login"] == "admin" for u in users)


def test_groups_list(op):
    res = op(["user", "groups"]).ok()
    assert isinstance(res.json, list)


def test_member_update_roles(op, project):
    users = op(["user", "list", "--name", "jane", "--limit", "5"])
    if users.code != 0 or not users.json:
        pytest.skip("jane.doe not seeded")
    added = op(["member", "add", "--project", project["identifier"], "--user", "jane.doe", "--role", "Member"])
    if added.code != 0:
        pytest.skip("could not add membership")
    mid = added.json["id"]
    try:
        updated = op(["member", "update", str(mid), "--role", "Reader"])
        if updated.code != 0:
            pytest.skip("Reader role not present")
        assert "Reader" in updated.json["roles"]
    finally:
        op(["member", "remove", str(mid), "-y"])


# ---- custom-field discovery ----
def test_cf_project_discovery(op):
    res = op(["cf", "project"]).ok()
    assert isinstance(res.json, list)


def test_cf_time_discovery(op):
    res = op(["cf", "time"]).ok()
    assert isinstance(res.json, list)


# ---- wiki / filelinks ----
def test_wiki_get(op):
    res = op(["wiki", "get", "1"])
    if res.code != 0:
        pytest.skip("no wiki page 1")
    assert "title" in res.json


def test_filelink_storages(op):
    res = op(["filelink", "storages"]).ok()
    assert isinstance(res.json, list)  # empty when no Nextcloud configured


# ---- notifications ----
def test_notify_states(op):
    for state in ("unread", "read", "all"):
        assert isinstance(op(["notify", "list", "--state", state, "--limit", "3"]).ok().json, list)


# ---- search extras ----
def test_search_sort_asc_and_raw(op, project, wp):
    raw = op(["search", "wp", "--project", project["identifier"], "--all", "--sort", "id", "--asc", "--raw"]).ok().json
    assert isinstance(raw, list)
    if raw:
        assert "_links" in raw[0]  # raw HAL elements


def test_search_group_by(op, project, wp):
    rows = op(["search", "wp", "--project", project["identifier"], "--all", "--group-by", "status"]).ok().json
    assert isinstance(rows, list)


def test_wp_list_where(op, project, wp):
    rows = op(["wp", "list", "--project", project["identifier"], "--where", "status:open", "--limit", "0"]).ok().json
    assert any(r["id"] == wp["id"] for r in rows)
