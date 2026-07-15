"""Unit tests for filter building (no network, via FakeClient)."""

from __future__ import annotations

import datetime as dt

from opcli import wpfilters
from support import FakeClient

STATUSES = [{"id": 7, "name": "In progress"}, {"id": 12, "name": "Closed"}]
TYPES = [{"id": 1, "name": "Task"}, {"id": 7, "name": "Bug"}]
PRIOS = [{"id": 8, "name": "Normal"}, {"id": 9, "name": "High"}]


def client():
    return FakeClient(collections={"statuses": STATUSES, "types": TYPES, "priorities": PRIOS})


def find(filters, key):
    for f in filters:
        if key in f:
            return f[key]
    return None


def test_default_adds_open_status():
    f = wpfilters.build(client())
    assert find(f, "status") == {"operator": "o", "values": None}


def test_all_statuses_no_status_filter():
    f = wpfilters.build(client(), all_statuses=True)
    assert find(f, "status") is None


def test_mine():
    f = wpfilters.build(client(), mine=True, all_statuses=True)
    assert find(f, "assignee") == {"operator": "=", "values": ["me"]}


def test_unassigned():
    f = wpfilters.build(client(), unassigned=True, all_statuses=True)
    assert find(f, "assignee") == {"operator": "!*", "values": None}


def test_watching():
    f = wpfilters.build(client(), watching=True, all_statuses=True)
    assert find(f, "watcher") == {"operator": "=", "values": ["me"]}


def test_status_open_closed_keywords():
    assert find(wpfilters.build(client(), status="open"), "status") == {"operator": "o", "values": None}
    assert find(wpfilters.build(client(), status="closed"), "status") == {"operator": "c", "values": None}


def test_status_by_name_resolves_id():
    f = wpfilters.build(client(), status="In progress")
    assert find(f, "status") == {"operator": "=", "values": ["7"]}


def test_type_and_priority_resolve():
    f = wpfilters.build(client(), type_="Bug", priority="High", all_statuses=True)
    assert find(f, "type") == {"operator": "=", "values": ["7"]}
    assert find(f, "priority") == {"operator": "=", "values": ["9"]}


def test_id_list():
    f = wpfilters.build(client(), id_list="1, 2 ,3", all_statuses=True)
    assert find(f, "id") == {"operator": "=", "values": ["1", "2", "3"]}


def test_query_and_subject():
    f = wpfilters.build(client(), query="payment", subject="timeout", all_statuses=True)
    assert find(f, "search") == {"operator": "**", "values": ["payment"]}
    assert find(f, "subject") == {"operator": "~", "values": ["timeout"]}


def test_updated_since_relative():
    f = wpfilters.build(client(), updated_since="7d", all_statuses=True)
    expected = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    assert find(f, "updatedAt") == {"operator": "<>d", "values": [expected, ""]}


def test_overdue_sets_due_and_open():
    f = wpfilters.build(client(), overdue=True)
    due = find(f, "dueDate")
    assert due["operator"] == "<>d" and due["values"][0] == ""
    assert find(f, "status") == {"operator": "o", "values": None}


def test_due_range():
    f = wpfilters.build(client(), due_after="2026-07-01", due_before="2026-07-31", all_statuses=True)
    assert find(f, "dueDate") == {"operator": "<>d", "values": ["2026-07-01", "2026-07-31"]}


def test_parent():
    f = wpfilters.build(client(), parent=40, all_statuses=True)
    assert find(f, "parent") == {"operator": "=", "values": ["40"]}


def test_project_filter():
    f = wpfilters.build(client(), project=5, all_statuses=True)
    assert find(f, "project") == {"operator": "=", "values": ["5"]}


def test_where_expression_merged():
    f = wpfilters.build(client(), where=["assignee:none"], all_statuses=True)
    assert find(f, "assignee") == {"operator": "!*", "values": None}


def test_encode_is_json():
    import json

    f = wpfilters.build(client(), all_statuses=True)
    assert json.loads(wpfilters.encode(f)) == f
