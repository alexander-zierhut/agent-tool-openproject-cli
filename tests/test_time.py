"""Time entries: add, list, edit, delete, activities."""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = pytest.mark.integration


def test_activities_listed(op, project):
    acts = op(["time", "activities", "--project", project["identifier"]]).ok().json
    names = {a["name"] for a in acts}
    assert "Development" in names


def test_add_list_edit_delete(op, wp):
    today = dt.date.today().isoformat()
    added = op(
        ["time", "add", "2.5", "--work-package", str(wp["id"]), "--comment", "worked", "--activity", "Development"]
    ).ok().json
    assert added["hours"] == "PT2H30M"
    assert added["activity"] == "Development"
    entry_id = added["id"]

    listed = op(["time", "list", "--work-package", str(wp["id"])]).ok().json
    assert any(e["id"] == entry_id for e in listed)

    edited = op(["time", "edit", str(entry_id), "--hours", "3", "--comment", "updated"]).ok().json
    assert edited["hours"] == "PT3H"
    assert edited["comment"] == "updated"

    op(["time", "delete", str(entry_id), "-y"]).ok()
    gone = op(["time", "get", str(entry_id)])
    assert gone.code != 0


def test_add_decimal_conversion(op, wp):
    added = op(["time", "add", "1.25", "--work-package", str(wp["id"])]).ok().json
    assert added["hours"] == "PT1H15M"
    op(["time", "delete", str(added["id"]), "-y"])


def test_single_sided_date_filters(op, wp):
    """`--from`-only and `--to`-only must use a valid operator (regression)."""
    op(["time", "add", "1", "--work-package", str(wp["id"]), "--activity", "Development"]).ok()
    from_only = op(["time", "list", "--work-package", str(wp["id"]), "--from", "2000-01-01"]).ok().json
    assert len(from_only) >= 1
    to_only = op(["time", "list", "--work-package", str(wp["id"]), "--to", "2099-12-31"]).ok().json
    assert len(to_only) >= 1


def test_log_on_project(op, project):
    res = op(["time", "add", "1", "--project", project["identifier"], "--comment", "planning"])
    if res.code != 0 and "logged for" in (res.stderr or "").lower():
        # OpenProject 16+ requires a work package ("entity") for time entries;
        # project-only logging is no longer accepted.
        pytest.skip("this OpenProject version requires a work package for time entries")
    added = res.ok().json
    assert added["hours"] == "PT1H"
    assert added["project"]["id"] == project["id"]
    op(["time", "delete", str(added["id"]), "-y"])
