"""Pure-unit tests (no network) for the helper modules."""

from __future__ import annotations

import pytest

import datetime as dt

from opcli import hal, searchspec
from opcli.duration import hours_to_iso, iso_to_hours, parse_hours_input
from opcli.errors import OpError
from opcli.output import OutputFormat


@pytest.mark.parametrize(
    "hours,iso",
    [
        (2.5, "PT2H30M"),
        (8, "PT8H"),
        (0.25, "PT15M"),
        (1.75, "PT1H45M"),
        (0, "PT0S"),
        (0.5, "PT30M"),
    ],
)
def test_hours_to_iso(hours, iso):
    assert hours_to_iso(hours) == iso


@pytest.mark.parametrize(
    "iso,hours",
    [
        ("PT2H30M", 2.5),
        ("PT8H", 8.0),
        ("PT15M", 0.25),
        ("P1DT2H", 26.0),
        ("PT0S", 0.0),
    ],
)
def test_iso_to_hours(iso, hours):
    assert iso_to_hours(iso) == pytest.approx(hours)


def test_iso_roundtrip():
    for h in (0.25, 1.0, 2.5, 3.75, 40.0):
        assert iso_to_hours(hours_to_iso(h)) == pytest.approx(h)


def test_parse_hours_input_accepts_both():
    assert parse_hours_input("2.5") == "PT2H30M"
    assert parse_hours_input("PT2H30M") == "PT2H30M"
    assert parse_hours_input("pt1h") == "pt1h"  # already ISO, passed through


def test_iso_to_hours_none():
    assert iso_to_hours(None) is None
    assert iso_to_hours("") is None


def test_id_from_href():
    assert hal.id_from_href("/api/v3/work_packages/42") == 42
    assert hal.id_from_href("/api/v3/projects/1/work_packages") == 1
    assert hal.id_from_href(None) is None
    assert hal.id_from_href("/api/v3/statuses/7") == 7


def test_link_helpers():
    doc = {"_links": {"status": {"href": "/api/v3/statuses/7", "title": "In progress"}}}
    assert hal.link_href(doc, "status") == "/api/v3/statuses/7"
    assert hal.link_title(doc, "status") == "In progress"
    assert hal.link_id(doc, "status") == 7
    assert hal.link_href(doc, "missing") is None


def test_ref():
    assert hal.ref("projects", 3) == {"href": "/api/v3/projects/3"}


# ---- searchspec: date specs ----
def test_to_date_keywords():
    today = dt.date.today()
    assert searchspec.to_date("today") == today
    assert searchspec.to_date("yesterday") == today - dt.timedelta(days=1)
    assert searchspec.to_date("tomorrow") == today + dt.timedelta(days=1)


def test_to_date_relative():
    today = dt.date.today()
    assert searchspec.to_date("7d") == today - dt.timedelta(days=7)
    assert searchspec.to_date("2w") == today - dt.timedelta(weeks=2)
    assert searchspec.to_date("+30d") == today + dt.timedelta(days=30)


def test_to_date_iso():
    assert searchspec.to_date("2026-07-01") == dt.date(2026, 7, 1)


def test_to_date_invalid():
    with pytest.raises(OpError):
        searchspec.to_date("nonsense")


# ---- searchspec: --where parsing ----
@pytest.mark.parametrize(
    "expr,field,sym,values",
    [
        ("status = open", "status", "=", ["open"]),
        ("updated>7d", "updated", ">", ["7d"]),
        ("assignee:none", "assignee", ":none", []),
        ("subject ~ bug", "subject", "~", ["bug"]),
        ("id = 1,2,3", "id", "=", ["1", "2", "3"]),
        ("percentageDone>=50", "percentageDone", ">=", ["50"]),
    ],
)
def test_parse_where(expr, field, sym, values):
    assert searchspec.parse_where(expr) == (field, sym, values)


def test_parse_where_invalid():
    with pytest.raises(OpError):
        searchspec.parse_where("garbage expression")


def test_canonical_field_aliases():
    assert searchspec.canonical_field("updated") == "updatedAt"
    assert searchspec.canonical_field("due") == "dueDate"
    assert searchspec.canonical_field("status") == "status"


# ---- output format coercion ----
def test_output_format_coerce():
    assert OutputFormat.coerce("md") == OutputFormat.markdown
    assert OutputFormat.coerce("json") == OutputFormat.json
    assert OutputFormat.coerce("table") == OutputFormat.table
    assert OutputFormat.coerce(None) is None
    with pytest.raises(ValueError):
        OutputFormat.coerce("xml")
