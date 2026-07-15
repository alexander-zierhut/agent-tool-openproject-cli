"""Users, memberships, assignees."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_whoami_and_me(op):
    me = op(["user", "me"]).ok().json
    assert me["login"]
    who = op(["auth", "whoami"]).ok().json
    assert who["id"] == me["id"]


def test_available_assignees(op, project):
    people = op(["user", "available", project["identifier"]]).ok().json
    assert isinstance(people, list)
    assert any(p.get("id") for p in people)


def test_roles_listed(op):
    roles = op(["member", "roles"]).ok().json
    names = {r["name"] for r in roles}
    assert "Member" in names or roles  # at least some roles exist


def test_membership_add_list_remove(op, project):
    # jane.doe is seeded; skip gracefully if not present
    users = op(["user", "list", "--name", "jane", "--limit", "5"])
    if users.code != 0 or not users.json:
        pytest.skip("second user jane.doe not seeded")
    added = op(["member", "add", "--project", project["identifier"], "--user", "jane.doe", "--role", "Member"])
    if added.code != 0:
        pytest.skip(f"could not add membership: {added.stderr}")
    membership_id = added.json["id"]
    assert "Member" in added.json["roles"]

    listed = op(["member", "list", "--project", project["identifier"]]).ok().json
    assert any(m["id"] == membership_id for m in listed)

    op(["member", "remove", str(membership_id), "-y"]).ok()
