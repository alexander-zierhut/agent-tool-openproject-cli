"""Hermetic unit tests for the issue-driven features (no network).

Covers the pure logic behind: time --sum/--group-by (#3), member name/login (#6),
project --attributes (#4), cf project -P key resolution (#5, shared), and
cost open aggregation (#1).
"""

from __future__ import annotations

import pytest

from agentcli.errors import OpError
from opcli import serialize
from opcli.commands import costs, time_entries
from opcli import resolve


# ---- #3: time list --group-by / --sum helpers ----

def test_norm_group_by_accepts_aliases_and_rejects_junk():
    assert time_entries._norm_group_by("user") == "user"
    assert time_entries._norm_group_by("Activity") == "activity"
    assert time_entries._norm_group_by("work-package") == "workPackage"
    assert time_entries._norm_group_by("WP") == "workPackage"
    with pytest.raises(OpError):
        time_entries._norm_group_by("nonsense")


def _row(hours, *, user=None, activity=None, wp=None):
    return {"hoursDecimal": hours, "user": user, "activity": activity, "workPackage": wp}


def test_group_rows_by_user_sums_and_sorts_desc():
    rows = [
        _row(2.0, user={"id": 1, "name": "Ann"}),
        _row(1.0, user={"id": 2, "name": "Bo"}),
        _row(3.0, user={"id": 1, "name": "Ann"}),
    ]
    out = time_entries._group_rows(rows, "user")
    assert [r["user"]["name"] for r in out] == ["Ann", "Bo"]  # 5.0 before 1.0
    assert out[0]["hours"] == 5.0 and out[0]["entries"] == 2
    assert out[1]["hours"] == 1.0 and out[1]["entries"] == 1


def test_group_rows_by_activity_handles_none():
    rows = [_row(1.5, activity="Dev"), _row(0.5, activity=None), _row(2.0, activity="Dev")]
    out = time_entries._group_rows(rows, "activity")
    assert out[0] == {"activity": "Dev", "hours": 3.5, "entries": 2}
    assert out[1] == {"activity": None, "hours": 0.5, "entries": 1}


# ---- #6: membership serializer ----

def test_membership_name_resolves_and_login_slot_reserved():
    doc = {
        "id": 7,
        "_links": {
            "principal": {"href": "/api/v3/users/5", "title": "Jane Doe"},
            "project": {"href": "/api/v3/projects/1", "title": "Demo"},
            "roles": [{"href": "/api/v3/roles/3", "title": "Member"}],
        },
    }
    m = serialize.membership(doc)
    assert m["name"] == "Jane Doe"          # top-level, so --fields name works
    assert m["principal"]["id"] == 5
    assert m["principal"]["login"] is None  # slot reserved; filled by the command
    assert m["roles"] == ["Member"]


# ---- #4: project attributes ----

def test_project_attributes_resolve_name_type_value_ordered():
    doc = {
        "id": 1, "name": "Demo", "identifier": "demo",
        "customField6": "2026-06-30",
        "_links": {"customField9": {"href": "/api/v3/custom_options/2", "title": "Quarterly"}},
    }
    schema = {
        "customField6": {"name": "Billed through", "type": "Date"},
        "customField9": {"name": "Billing Plan", "type": "CustomOption"},
    }
    out = serialize.project(doc, schema=schema)
    attrs = out["attributes"]
    assert [a["key"] for a in attrs] == ["customField6", "customField9"]  # numeric order
    assert attrs[0] == {"key": "customField6", "name": "Billed through", "type": "Date", "value": "2026-06-30"}
    # CustomOption link resolved to its title by custom_fields()
    assert attrs[1]["value"] == "Quarterly" and attrs[1]["type"] == "CustomOption"


def test_project_without_schema_has_no_attributes_key():
    out = serialize.project({"id": 1, "name": "Demo"})
    assert "attributes" not in out


def test_project_attributes_include_unset_fields_with_null_value():
    # Schema defines a field the project has no value for -> it still appears,
    # name/type resolved, value None (the core of issue #4: don't hide it).
    doc = {"id": 1, "name": "Demo"}
    schema = {"customField6": {"name": "Billed through", "type": "Date"}}
    attrs = serialize.project(doc, schema=schema)["attributes"]
    assert attrs == [{"key": "customField6", "name": "Billed through", "type": "Date", "value": None}]


# ---- #5 / #1: project custom-field key resolution ----

class _FakeClient:
    def __init__(self, schema):
        self._schema = schema

    def post(self, path, json=None, params=None):
        return {"_embedded": {"schema": self._schema}}


def test_project_cf_key_prefers_exact_then_case_insensitive():
    schema = {
        "customField6": {"name": "Billed through", "type": "Date"},
        "customField8": {"name": "Billed Through", "type": "Date"},  # near-duplicate
        "type": {"name": "Type"},  # non-custom key ignored
    }
    c = _FakeClient(schema)
    assert resolve.project_cf_key(c, "Billed through") == "customField6"   # exact wins
    assert resolve.project_cf_key(c, "billed THROUGH") == "customField6"   # ci -> first match
    with pytest.raises(OpError):
        resolve.project_cf_key(c, "No Such Field")


# ---- #1: cost aggregation ----

def _te(uid, name, hours_iso, activity=None):
    links = {"user": {"href": f"/api/v3/users/{uid}", "title": name}}
    if activity:
        links["activity"] = {"href": "/api/v3/time_entries/activities/1", "title": activity}
    return {"hours": hours_iso, "_links": links}


def test_aggregate_by_activity_buckets_and_totals():
    entries = [
        _te(1, "Ann", "PT2H", "Dev"),
        _te(1, "Ann", "PT1H", "Review"),
        _te(2, "Bo", "P1D", "Dev"),  # P1D = 24h (calendar convention)
    ]

    def user_info(e):
        return {"id": e["_links"]["user"]["href"].split("/")[-1], "name": e["_links"]["user"]["title"], "login": None}

    def project_info(e):
        return {"id": None, "name": "(none)", "identifier": None}

    agg = costs._aggregate(entries, rate_table=None, user_info=user_info,
                           project_info=project_info, by_project=False, by_activity=True)
    assert agg["totals"]["hours"] == 27.0  # 2 + 1 + 24
    assert agg["totals"]["people"] == 2
    ann = next(u for u in agg["byUser"] if u["user"]["name"] == "Ann")
    acts = {a["activity"]: a["hours"] for a in ann["activities"]}
    assert acts == {"Dev": 2.0, "Review": 1.0}
    bo = next(u for u in agg["byUser"] if u["user"]["name"] == "Bo")
    assert bo["hours"] == 24.0  # P1D = 24h (calendar), the reverted correctness point
