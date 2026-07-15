"""Projects: create, list, get, update, archive/unarchive, delete."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


def test_project_appears_in_list(op, project):
    idents = [p["identifier"] for p in op(["project", "list", "--limit", "0"]).ok().json]
    assert project["identifier"] in idents


def test_get_project_by_identifier_and_id(op, project):
    by_ident = op(["project", "get", project["identifier"]]).ok().json
    by_id = op(["project", "get", str(project["id"])]).ok().json
    assert by_ident["id"] == by_id["id"] == project["id"]


def test_update_project_description(op, project):
    updated = op(["project", "update", project["identifier"], "--description", "changed by test"]).ok().json
    assert updated["description"] == "changed by test"


def test_archive_unarchive_delete_cycle(op):
    ident = f"op-cli-arch-{uuid.uuid4().hex[:8]}"
    created = op(["project", "create", "Archive Test", "--identifier", ident]).ok().json
    assert created["active"] is True

    archived = op(["project", "archive", ident]).ok().json
    assert archived["active"] is False

    archived_idents = [p["identifier"] for p in op(["project", "list", "--archived", "--limit", "0"]).ok().json]
    assert ident in archived_idents

    restored = op(["project", "unarchive", ident]).ok().json
    assert restored["active"] is True

    op(["project", "delete", ident, "-y"]).ok()


def test_create_with_parent(op, project):
    ident = f"op-cli-child-{uuid.uuid4().hex[:8]}"
    child = op(
        ["project", "create", "Child", "--identifier", ident, "--parent", project["identifier"]]
    ).ok().json
    assert child["parent"]["id"] == project["id"]
    op(["project", "delete", ident, "-y"])
