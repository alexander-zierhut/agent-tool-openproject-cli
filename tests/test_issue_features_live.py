"""Integration tests for the issue-driven features, against the live instance.

Feature ↔ issue: time --sum/--group-by (#3) and hoursDecimal (#2), member
name/login (#6), project --attributes (#4), cf project -P (#5), cost open (#1).
The project custom fields these rely on are created by scripts/seed_test_data.rb.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_time_decimal_sum_and_group_by(op, wp):
    op(["time", "add", "2", "--work-package", str(wp["id"]), "--activity", "Development"]).ok()
    op(["time", "add", "1.5", "--work-package", str(wp["id"]), "--activity", "Development"]).ok()

    listing = op(["time", "list", "--work-package", str(wp["id"])]).ok().json
    assert all("hoursDecimal" in r for r in listing)  # #2
    assert {r["hoursDecimal"] for r in listing} >= {2.0, 1.5}

    total = op(["time", "list", "--work-package", str(wp["id"]), "--sum"]).ok().json  # #3
    assert total["totalHours"] == pytest.approx(3.5)
    assert total["entries"] >= 2

    by_user = op(["time", "list", "--work-package", str(wp["id"]), "--group-by", "user"]).ok().json
    assert isinstance(by_user, list) and by_user
    assert sum(g["hours"] for g in by_user) == pytest.approx(3.5)

    both = op(["time", "list", "--work-package", str(wp["id"]), "--group-by", "activity", "--sum"]).ok().json
    assert both["groupBy"] == "activity"
    assert both["totalHours"] == pytest.approx(3.5)

    bad = op(["time", "list", "--group-by", "nonsense"])
    assert bad.code != 0 and "group-by" in (bad.stderr + bad.stdout)


def test_hours_decimal_uses_calendar_day_end_to_end(op, wp):
    # A P1D entry (24 real hours) must read back as 24.0, not an 8h "working day" —
    # the regression the review caught. Log it via ISO so the server keeps P1D.
    op(["time", "add", "P1D", "--work-package", str(wp["id"]), "--activity", "Development"]).ok()
    row = next(r for r in op(["time", "list", "--work-package", str(wp["id"])]).ok().json
               if r["hours"] in ("P1D", "PT24H"))
    assert row["hoursDecimal"] == 24.0


def test_member_list_resolves_name_and_login(op, project):
    rows = op(["member", "list", "--project", project["identifier"]]).ok().json
    assert rows, "project should have at least the current user as a member"
    # #6: name is no longer null, and the principal carries a login
    assert all(r["name"] for r in rows)
    assert any((r.get("principal") or {}).get("login") for r in rows)
    # --fields name (top-level projection) now resolves
    named = op(["member", "list", "--project", project["identifier"], "--fields", "id,name"]).ok().json
    assert all(r.get("name") for r in named)


def test_member_add_returns_name_and_login(op, project):
    # add/update should resolve name + login too, not just list. Self-cleaning so
    # it doesn't leave jane on the shared project (which would skip sibling tests).
    added = op(["member", "add", "--project", project["identifier"], "--user", "jane.doe", "--role", "Member"])
    if added.code != 0:
        pytest.skip(f"could not add membership: {added.stderr}")
    try:
        assert added.json["name"] == "Jane Doe"
        assert (added.json.get("principal") or {}).get("login") == "jane.doe"
    finally:
        op(["member", "remove", str(added.json["id"]), "-y"])


def test_project_get_attributes_resolves_names(op):
    doc = op(["project", "get", "demo-project", "--attributes"]).ok().json  # #4
    attrs = {a["name"]: a for a in doc.get("attributes", [])}
    assert "Billed through" in attrs
    assert attrs["Billed through"]["type"] == "Date"
    assert attrs["Billed through"]["value"] == "2020-01-01"
    # CustomOption value resolved to its title, not an href
    assert attrs.get("Billing Plan", {}).get("value") == "Quarterly"


def test_cf_project_accepts_dash_p(op):
    scoped = op(["cf", "project", "-P", "demo-project"]).ok().json  # #5
    assert any(f["name"] == "Billed through" for f in scoped)
    # the global listing (no -P) still works
    op(["cf", "project"]).ok()


def test_cost_open_reads_cutoff_and_sweeps_billable(op):
    # single project, cut-off field named explicitly (avoids touching stored config)
    res = op(["cost", "open", "-P", "demo-project", "--cutoff-field", "Billed through"]).ok().json  # #1
    assert res["cutoffField"] == "Billed through"
    assert res["cutoffDate"] == "2020-01-01"
    assert res["from"] == "2020-01-02"
    assert isinstance(res["openHours"], (int, float))
    assert isinstance(res["byUser"], list)

    # sweep every billable project
    sweep = op(["cost", "open", "--cutoff-field", "Billed through", "--billable-field", "Billable"]).ok().json
    names = [p["project"]["identifier"] for p in sweep["projects"]]
    assert "demo-project" in names
    assert sweep["totals"]["projects"] >= 1
    # your-scrum-project is billable but has NO cut-off date -> it lands in `skipped`
    skipped_ids = [s["project"]["name"] for s in sweep["skipped"]]
    assert any("Scrum" in n for n in skipped_ids), f"expected a billable-but-no-cutoff project in skipped, got {sweep['skipped']}"


def test_cost_open_table_output(op):
    # -o table must not error and must surface the open hours (contract parity with `cost report`).
    res = op(["cost", "open", "-P", "demo-project", "--cutoff-field", "Billed through", "-o", "table"])
    res.ok()
    assert "OPEN:" in (res.stdout + res.stderr)
