"""Work-package comments: add, list, edit."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_add_list_edit(op, wp):
    added = op(["comment", "add", str(wp["id"]), "first note"]).ok().json
    assert added["comment"] == "first note"
    activity_id = added["id"]

    op(["comment", "add", str(wp["id"]), "second **note**"]).ok()

    listed = op(["comment", "list", str(wp["id"])]).ok().json
    texts = [c["comment"] for c in listed]
    assert "first note" in texts
    assert any("second" in t for t in texts)

    edited = op(["comment", "edit", str(activity_id), "first note (edited)"]).ok().json
    assert edited["comment"] == "first note (edited)"


def test_list_comments_have_user(op, wp):
    op(["comment", "add", str(wp["id"]), "who am i"]).ok()
    listed = op(["comment", "list", str(wp["id"])]).ok().json
    assert listed
    assert listed[-1]["user"]["name"]  # enriched user name present
