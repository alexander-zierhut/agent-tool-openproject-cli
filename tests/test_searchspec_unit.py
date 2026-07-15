"""Unit tests for searchspec: --where compilation, live-field parsing, values."""

from __future__ import annotations

import datetime as dt

import pytest

from opcli import searchspec
from opcli.errors import OpError
from support import FakeClient

STATUSES = [{"id": 7, "name": "In progress"}, {"id": 12, "name": "Closed"}]
PRIN = [{"login": "jane", "name": "Jane Doe", "email": "j@x.y", "_links": {"self": {"href": "/api/v3/users/5"}}}]


def client():
    return FakeClient(collections={"statuses": STATUSES, "principals": PRIN})


def test_compile_where_status_name():
    f = searchspec.compile_where(client(), "status = In progress")
    assert f == {"status": {"operator": "=", "values": ["7"]}}


def test_compile_where_keyword_open():
    assert searchspec.compile_where(client(), "status:open") == {"status": {"operator": "o", "values": None}}
    assert searchspec.compile_where(client(), "assignee:none") == {"assignee": {"operator": "!*", "values": None}}
    assert searchspec.compile_where(client(), "version:any") == {"version": {"operator": "*", "values": None}}


def test_compile_where_user_me():
    assert searchspec.compile_where(client(), "assignee = me") == {"assignee": {"operator": "=", "values": ["me"]}}


def test_compile_where_user_name_resolves():
    f = searchspec.compile_where(client(), "assignee = jane")
    assert f == {"assignee": {"operator": "=", "values": ["5"]}}


def test_compile_where_alias_updated_date():
    f = searchspec.compile_where(client(), "updated > 7d")
    expected = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    assert f == {"updatedAt": {"operator": "<>d", "values": [expected, ""]}}


def test_compile_where_date_before():
    f = searchspec.compile_where(client(), "due < 2026-08-01")
    assert f == {"dueDate": {"operator": "<>d", "values": ["", "2026-08-01"]}}


def test_compile_where_date_on():
    f = searchspec.compile_where(client(), "due = 2026-08-01")
    assert f == {"dueDate": {"operator": "=d", "values": ["2026-08-01"]}}


def test_compile_where_contains():
    f = searchspec.compile_where(client(), "subject ~ bug")
    assert f == {"subject": {"operator": "~", "values": ["bug"]}}


def test_compile_where_numeric():
    f = searchspec.compile_where(client(), "percentageDone >= 50")
    assert f == {"percentageDone": {"operator": ">=", "values": ["50"]}}


def test_compile_where_multi_value():
    f = searchspec.compile_where(client(), "id = 1,2,3")
    assert f == {"id": {"operator": "=", "values": ["1", "2", "3"]}}


def test_compile_where_custom_field_passthrough():
    f = searchspec.compile_where(client(), "customField1 ~ INV")
    assert f == {"customField1": {"operator": "~", "values": ["INV"]}}


def test_parse_where_needs_value():
    with pytest.raises(OpError):
        searchspec.compile_where(client(), "status =")


def test_operators_reference_nonempty():
    codes = {c for c, _ in searchspec.OPERATORS}
    assert {"=", "!", "o", "c", "!*", "<>d", "~"} <= codes


def test_registry_has_common_fields():
    assert {"status", "assignee", "dueDate", "version", "search"} <= set(searchspec.REGISTRY)


def test_resolve_value_date():
    assert searchspec.resolve_value(client(), "date", "today") == dt.date.today().isoformat()


def test_live_fields_parsing():
    schemas = [
        {"_links": {"self": {"href": "/api/v3/queries/filter_instance_schemas/status"}}},
        {"_links": {"self": {"href": "/api/v3/queries/filter_instance_schemas/customField9"}}},
    ]
    c = FakeClient(collections={"queries/filter_instance_schemas": schemas})
    rows = searchspec.live_fields(c)
    keys = {r["field"] for r in rows}
    assert "status" in keys and "customField9" in keys
    status_row = next(r for r in rows if r["field"] == "status")
    assert status_row["kind"] == "status"  # enriched from registry
