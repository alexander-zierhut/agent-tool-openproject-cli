"""Predefined filters, --where, presets, and discoverability commands."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def scenario(op):
    """A dedicated project with a controlled set of work packages:
    A=open+mine, B=open+unassigned, C=open+mine+overdue, D=closed+mine."""
    ident = f"op-search-{uuid.uuid4().hex[:8]}"
    op(["project", "create", "Search " + ident, "--identifier", ident]).ok()
    for role in ("Project admin", "Member"):
        if op(["member", "add", "--project", ident, "--user", "me", "--role", role]).code == 0:
            break
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    A = op(["wp", "create", "alpha", "--project", ident, "--assignee", "me"]).ok().json["id"]
    B = op(["wp", "create", "beta", "--project", ident]).ok().json["id"]
    C = op(["wp", "create", "gamma late", "--project", ident, "--assignee", "me", "--due-date", yesterday]).ok().json["id"]
    D = op(["wp", "create", "delta", "--project", ident, "--assignee", "me"]).ok().json["id"]
    op(["wp", "update", str(D), "--status", "Closed"]).ok()
    data = {"ident": ident, "A": A, "B": B, "C": C, "D": D}
    yield data
    op(["project", "delete", ident, "-y"])


def _ids(rows):
    return {r["id"] for r in rows}


# ---- predefined flags ----
def test_mine(op, scenario):
    got = _ids(op(["search", "wp", "--project", scenario["ident"], "--mine"]).ok().json)
    assert scenario["A"] in got and scenario["C"] in got
    assert scenario["B"] not in got and scenario["D"] not in got  # unassigned / closed excluded


def test_unassigned(op, scenario):
    got = _ids(op(["search", "wp", "--project", scenario["ident"], "--unassigned"]).ok().json)
    assert scenario["B"] in got and scenario["A"] not in got


def test_overdue(op, scenario):
    got = _ids(op(["search", "wp", "--project", scenario["ident"], "--overdue"]).ok().json)
    assert got == {scenario["C"]}


def test_closed_and_all(op, scenario):
    closed = _ids(op(["search", "wp", "--project", scenario["ident"], "--closed"]).ok().json)
    assert scenario["D"] in closed
    every = _ids(op(["search", "wp", "--project", scenario["ident"], "--all"]).ok().json)
    assert {scenario["A"], scenario["B"], scenario["C"], scenario["D"]} <= every


def test_id_filter(op, scenario):
    got = _ids(op(["search", "wp", "--id", f"{scenario['A']},{scenario['B']}", "--all"]).ok().json)
    assert got == {scenario["A"], scenario["B"]}


def test_updated_since_relative(op, scenario):
    got = _ids(op(["search", "wp", "--project", scenario["ident"], "--updated-since", "1d", "--all"]).ok().json)
    assert scenario["A"] in got  # created today -> updated within 1d


# ---- --where ----
def test_where_status_open(op, scenario):
    got = _ids(op(["search", "wp", "--project", scenario["ident"], "--where", "status:open"]).ok().json)
    assert scenario["D"] not in got and scenario["A"] in got


def test_where_assignee_none(op, scenario):
    got = _ids(op(["search", "wp", "--project", scenario["ident"], "--where", "assignee:none"]).ok().json)
    assert scenario["B"] in got


def test_where_subject_contains(op, scenario):
    got = _ids(op(["search", "wp", "--project", scenario["ident"], "--where", "subject ~ late", "--all"]).ok().json)
    assert got == {scenario["C"]}


def test_where_alias_updated(op, scenario):
    # 'updated' alias -> updatedAt
    got = _ids(op(["search", "wp", "--project", scenario["ident"], "--where", "updated > 1d", "--all"]).ok().json)
    assert scenario["A"] in got


# ---- presets ----
def test_preset_mine(op, scenario):
    got = _ids(op(["search", "mine", "--project", scenario["ident"]]).ok().json)
    assert {scenario["A"], scenario["C"]} <= got


def test_preset_overdue(op, scenario):
    got = _ids(op(["search", "overdue", "--project", scenario["ident"]]).ok().json)
    assert got == {scenario["C"]}


def test_preset_unassigned(op, scenario):
    got = _ids(op(["search", "unassigned", "--project", scenario["ident"]]).ok().json)
    assert scenario["B"] in got


def test_count(op, scenario):
    res = op(["search", "wp", "--project", scenario["ident"], "--all", "--count"]).ok().json
    assert res["total"] >= 4


# ---- discoverability ----
def test_fields(op, scenario):
    fields = op(["search", "fields", "--project", scenario["ident"]]).ok().json
    names = {f["field"] for f in fields}
    assert {"status", "assignee", "dueDate", "priority"} <= names
    assert any(f["field"].startswith("customField") for f in fields)


def test_operators(op):
    ops = {o["operator"] for o in op(["search", "operators"]).ok().json}
    assert {"o", "c", "!*", "<>d"} <= ops


def test_values_status(op):
    vals = op(["search", "values", "status"]).ok().json
    assert any(v["name"] == "Closed" for v in vals)


def test_values_type(op):
    vals = op(["search", "values", "type"]).ok().json
    assert any(v["name"] == "Task" for v in vals)
