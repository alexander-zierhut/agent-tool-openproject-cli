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


def test_cost_report_hours_only_without_rates(op, wp):
    op(["time", "add", "1", "--work-package", str(wp["id"]), "--activity", "Development"]).ok()
    month = dt.date.today().strftime("%Y-%m")
    report = op(["cost", "report", "--month", month, "--user", "me"]).ok().json
    assert report["billable"] is False
    assert report["totals"]["amount"] is None
    assert report["totals"]["hours"] >= 1
