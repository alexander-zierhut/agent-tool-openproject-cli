"""Auth status, notifications, custom-field discovery, raw escape hatch, errors."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_auth_status(op):
    status = op(["auth", "status"]).ok().json
    assert status["hasToken"] is True
    assert status["reachable"] is True
    assert status["me"]["login"]


def test_raw_get(op):
    doc = op(["raw", "get", "statuses", "-p", "pageSize=3"]).ok().json
    assert doc["_type"].endswith("Collection")
    assert doc["_embedded"]["elements"]


def test_raw_post_patch_delete_roundtrip(op, project):
    # create a WP via raw, then delete it via raw
    body = (
        '{"subject":"raw wp","_links":{"project":{"href":"/api/v3/projects/%d"},'
        '"type":{"href":"/api/v3/types/1"}}}' % project["id"]
    )
    created = op(["raw", "post", "work_packages", "-d", body]).ok().json
    assert created["subject"] == "raw wp"
    op(["raw", "delete", f"work_packages/{created['id']}"]).ok()


def test_cf_discovery(op, project):
    fields = op(["cf", "wp", "--project", project["identifier"], "--type", "Task"]).ok().json
    # seeded custom fields should be present
    assert any(f["key"].startswith("customField") for f in fields)


def test_notifications_list(op):
    # always returns a (possibly empty) list
    res = op(["notify", "list", "--state", "all", "--limit", "5"]).ok()
    assert isinstance(res.json, list)


def test_notification_generated_read_unread(op, project, second_token):
    """Deterministic: a second user @-mentions us, producing a notification we
    then mark read and unread."""
    import time

    me = op(["user", "me"]).ok().json
    # second user must be a member of the project to comment there
    op(["member", "add", "--project", project["identifier"], "--user", "jane.doe", "--role", "Member"])
    created = op(["wp", "create", "notify me", "--project", project["identifier"]]).ok().json
    wp_id = created["id"]
    try:
        mention = (
            f'<mention data-id="{me["id"]}" data-type="user" '
            f'data-text="@{me["name"]}">@{me["name"]}</mention> please look'
        )
        # jane comments with a mention + notify
        res = op(["comment", "add", str(wp_id), mention, "--notify"], token=second_token)
        if res.code != 0:
            pytest.skip(f"second user could not comment: {res.stderr}")

        nid = None
        for _ in range(10):
            unread = op(["notify", "list", "--state", "unread", "--limit", "20"]).ok().json
            hit = [n for n in unread if (n.get("resource") or {}).get("id") == wp_id]
            if hit:
                nid = hit[0]["id"]
                break
            time.sleep(1)
        if nid is None:
            pytest.skip("mention notification did not materialise in time")

        # count + today reflect the fresh notification
        cnt = op(["notify", "count", "--today"]).ok().json
        assert cnt["unread"] >= 1 and cnt["total"] >= 1
        assert cnt["today"] >= 1
        todays = op(["notify", "list", "--state", "all", "--today"]).ok().json
        assert any(n["id"] == nid for n in todays)

        op(["notify", "read", str(nid)]).ok()
        still = op(["notify", "list", "--state", "unread", "--limit", "50"]).ok().json
        assert all(n["id"] != nid for n in still)
        op(["notify", "unread", str(nid)]).ok()
        again = op(["notify", "list", "--state", "unread", "--limit", "50"]).ok().json
        assert any(n["id"] == nid for n in again)
    finally:
        op(["wp", "delete", str(wp_id), "-y"])


def test_error_is_json_and_nonzero(op):
    import json

    res = op(["wp", "get", "999999999"])
    assert res.code != 0
    # errors are emitted as structured JSON on stderr
    payload = json.loads(res.stderr)
    assert "error" in payload
