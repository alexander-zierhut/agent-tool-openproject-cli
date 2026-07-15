"""Per-person time & cost reporting (invoicing)."""

from __future__ import annotations

import datetime as dt
import json

import pytest

pytestmark = pytest.mark.integration


def test_cost_report_sums_and_bills(op, wp, tmp_path):
    # log two entries against the fixture WP
    op(["time", "add", "2", "--work-package", str(wp["id"]), "--activity", "Development"]).ok()
    op(["time", "add", "1.5", "--work-package", str(wp["id"]), "--activity", "Development"]).ok()

    me = op(["user", "me"]).ok().json
    rates = {"currency": "EUR", "default": 100, "users": {me["login"]: 120}}
    rates_file = tmp_path / "rates.json"
    rates_file.write_text(json.dumps(rates))

    month = dt.date.today().strftime("%Y-%m")
    report = op(["cost", "report", "--month", month, "--user", "me", "--rates", str(rates_file)]).ok().json

    assert report["billable"] is True
    assert report["currency"] == "EUR"
    assert report["totals"]["hours"] >= 3.5
    mine = [u for u in report["byUser"] if u["user"]["login"] == me["login"]]
    assert mine, "current user missing from report"
    person = mine[0]
    # rate 120 applied
    assert person["amount"] == pytest.approx(person["hours"] * 120, abs=0.01)


def test_cost_report_detailed_with_custom_fields(op, wp):
    # requires a time-entry custom field (seeded as "Cost Center")
    cfs = op(["cf", "time"]).ok().json
    cc = next((c for c in cfs if c.get("name") == "Cost Center"), None)
    if not cc:
        pytest.skip("time-entry custom field 'Cost Center' not seeded")
    key = cc["key"]
    op(
        ["time", "add", "2", "--work-package", str(wp["id"]), "--activity", "Development",
         "--custom-fields", json.dumps({key: "CC-TEST-9"})]
    ).ok()
    month = dt.date.today().strftime("%Y-%m")
    rows = op(["cost", "report", "--month", month, "--user", "me", "--detailed"]).ok().json
    assert isinstance(rows, list) and rows
    # the custom field appears (by its friendly name) with our value
    assert any(r.get("Cost Center") == "CC-TEST-9" for r in rows)
    assert all("hours" in r and "activity" in r for r in rows)


def test_cost_report_hours_only_without_rates(op, wp):
    op(["time", "add", "1", "--work-package", str(wp["id"]), "--activity", "Development"]).ok()
    month = dt.date.today().strftime("%Y-%m")
    report = op(["cost", "report", "--month", month, "--user", "me"]).ok().json
    assert report["billable"] is False
    assert report["totals"]["amount"] is None
    assert report["totals"]["hours"] >= 1
