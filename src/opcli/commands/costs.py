"""Per-person time & cost reporting for monthly invoicing.

Reality check (from the API research): OpenProject's API v3 exposes **no**
hourly rates and **no** cost-report endpoints. The only reliable, per-person
figures come from summing ``time_entries`` client-side. So this report pulls the
time bookings for a period, groups them by person (and project), sums the hours,
and — if you supply a rate table — multiplies to get billable amounts.

Rate table (JSON) format::

    {
      "currency": "EUR",
      "default": 90,
      "users":    { "admin": 120, "jane.doe": 100 },
      "projects": { "demo-project": { "default": 100, "admin": 110 } }
    }

User keys may be a login, a full name, or a numeric id. Project keys may be an
identifier or name. Most specific wins: project+user → project default → user → default.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .. import hal, serialize
from ..duration import iso_to_hours
from agentcli.errors import OpError
from ._shared import ctx_obj
from .time_entries import query_time_entries

app = typer.Typer(no_args_is_help=True)


def _time_entry_cf_names(client, entries: list) -> dict[str, str]:
    """Map customFieldN -> friendly name for time entries, from the schema."""
    pid = None
    for e in entries:
        pid = hal.link_id(e, "project")
        if pid:
            break
    if pid is None:
        return {}
    try:
        form = client.post("time_entries/form", json={"_links": {"project": {"href": f"/api/v3/projects/{pid}"}}})
    except OpError:
        return {}
    schema = (form.get("_embedded") or {}).get("schema") or {}
    return {k: (schema[k].get("name") or k) for k in schema if k.startswith("customField")}


def _load_rates(path: Path | None) -> dict | None:
    if path is None:
        return None
    if not path.exists():
        raise OpError(f"rates file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise OpError(f"invalid rates JSON: {exc}") from exc


def _rate_for(rates: dict, user_keys: list[str], project_keys: list[str]) -> float | None:
    # Keys are ordered by priority (most specific first) so the result is
    # deterministic when a rate table has overlapping keys.
    if not rates:
        return None
    projects = rates.get("projects", {})
    for pk in project_keys:
        if pk in projects:
            pconf = projects[pk]
            if isinstance(pconf, dict):
                for uk in user_keys:
                    if uk in pconf:
                        return float(pconf[uk])
                if "default" in pconf:
                    return float(pconf["default"])
            else:
                return float(pconf)
    users = rates.get("users", {})
    for uk in user_keys:
        if uk in users:
            return float(users[uk])
    if "default" in rates:
        return float(rates["default"])
    return None


@app.command()
def report(
    ctx: typer.Context,
    month: str = typer.Option(None, "--month", help="Month YYYY-MM (sets the date range)."),
    frm: str = typer.Option(None, "--from", help="Start date YYYY-MM-DD."),
    to: str = typer.Option(None, "--to", help="End date YYYY-MM-DD."),
    user: str = typer.Option(None, "--user", "-u", help="Restrict to one user (login/name/id or 'me')."),
    project: str = typer.Option(None, "--project", "-P", help="Restrict to one project."),
    rates: Path = typer.Option(None, "--rates", help="JSON rate table for billable amounts."),
    by_project: bool = typer.Option(True, "--by-project/--no-by-project", help="Break each person down by project."),
    detailed: bool = typer.Option(
        False, "--detailed", help="One row per time entry INCLUDING its custom fields (great with -o csv)."
    ),
) -> None:
    """Summarise hours (and billable cost) per person for a period — for invoicing.

    `--detailed` emits one row per time entry with its custom fields included —
    something OpenProject's own reports can't export. Pair with `-o csv`.
    """
    obj = ctx_obj(ctx)
    client = obj.client()
    rate_table = _load_rates(rates)

    entries = query_time_entries(client, user=user, project=project, frm=frm, to=to, month=month, desc=False, limit=None)

    # cache user + project details so rate keys can match login/name/id and
    # project identifier/name/id (the rate table may key by any of them).
    user_cache: dict[int, dict] = {}
    project_cache: dict[int, dict] = {}

    def user_info(entry) -> dict:
        uid = hal.link_id(entry, "user")
        if uid not in user_cache:
            name = hal.link_title(entry, "user")
            info = {"id": uid, "name": name, "login": None}
            try:
                u = client.get(f"users/{uid}")
                info["login"] = u.get("login")
                info["name"] = u.get("name") or name
            except OpError:
                pass
            user_cache[uid] = info
        return user_cache[uid]

    def project_info(entry) -> dict:
        pid = hal.link_id(entry, "project")
        name = hal.link_title(entry, "project") or "(none)"
        if pid is None:
            return {"id": None, "name": name, "identifier": None}
        if pid not in project_cache:
            info = {"id": pid, "name": name, "identifier": None}
            try:
                p = client.get(f"projects/{pid}")
                info["identifier"] = p.get("identifier")
                info["name"] = p.get("name") or name
            except OpError:
                pass
            project_cache[pid] = info
        return project_cache[pid]

    def rate_for_entry(e) -> float | None:
        info = user_info(e)
        pinfo = project_info(e)
        user_keys = [str(k) for k in (info.get("login"), info.get("name"), info["id"]) if k is not None]
        project_keys = [str(k) for k in (pinfo.get("identifier"), pinfo["name"], pinfo["id"]) if k is not None]
        return _rate_for(rate_table, user_keys, project_keys) if rate_table else None

    # ---- detailed: one row per time entry, INCLUDING time-entry custom fields ----
    if detailed:
        cf_names = _time_entry_cf_names(client, entries)
        rows = []
        for e in entries:
            te = serialize.time_entry(e)
            info = user_info(e)
            hours = iso_to_hours(e.get("hours")) or 0.0
            rate = rate_for_entry(e)
            row = {
                "date": te["spentOn"],
                "user": info.get("login") or info.get("name"),
                "userName": info.get("name"),
                "project": project_info(e)["name"],
                "workPackage": (te.get("workPackage") or {}).get("id"),
                "activity": te.get("activity"),
                "hours": round(hours, 2),
                "rate": rate,
                "amount": round(hours * rate, 2) if rate is not None else None,
                "comment": te.get("comment"),
            }
            for key, val in (te.get("customFields") or {}).items():
                row[cf_names.get(key, key)] = val
            rows.append(row)
        base = ["date", "user", "userName", "project", "workPackage", "activity", "hours", "rate", "amount", "comment"]
        cf_cols = [n for n in cf_names.values() if any(n in r for r in rows)]
        columns = [(c, c) for c in base + cf_cols]
        obj.emitter.emit(rows, columns=columns, empty="(no time entries)")
        return

    people: dict[int, dict] = {}
    grand_hours = 0.0
    grand_amount = 0.0
    for e in entries:
        info = user_info(e)
        uid = info["id"]
        hours = iso_to_hours(e.get("hours")) or 0.0
        pinfo = project_info(e)
        proj_name = pinfo["name"]
        proj_id = pinfo["id"]

        # ordered by specificity -> deterministic matching
        user_keys = [str(k) for k in (info.get("login"), info.get("name"), uid) if k is not None]
        project_keys = [str(k) for k in (pinfo.get("identifier"), proj_name, proj_id) if k is not None]
        rate = _rate_for(rate_table, user_keys, project_keys) if rate_table else None
        # accumulate unrounded; round only at output to avoid cent drift
        amount = hours * rate if rate is not None else None

        person = people.setdefault(
            uid,
            {"user": info, "hours": 0.0, "entries": 0, "amount": 0.0 if rate_table else None, "projects": {}},
        )
        person["hours"] += hours
        person["entries"] += 1
        if amount is not None:
            person["amount"] = (person["amount"] or 0.0) + amount
        if by_project:
            pj = person["projects"].setdefault(proj_name, {"project": proj_name, "hours": 0.0, "amount": 0.0 if rate_table else None, "rate": rate})
            pj["hours"] += hours
            if amount is not None:
                pj["amount"] = (pj["amount"] or 0.0) + amount

        grand_hours += hours
        if amount is not None:
            grand_amount += amount

    by_user = []
    for p in people.values():
        row = {
            "user": p["user"],
            "hours": round(p["hours"], 2),
            "entries": p["entries"],
            "amount": round(p["amount"], 2) if p["amount"] is not None else None,
        }
        if by_project:
            row["projects"] = [
                {"project": pj["project"], "hours": round(pj["hours"], 2),
                 "rate": pj["rate"], "amount": round(pj["amount"], 2) if pj["amount"] is not None else None}
                for pj in p["projects"].values()
            ]
        by_user.append(row)
    by_user.sort(key=lambda r: r["hours"], reverse=True)

    result = {
        "period": {"month": month, "from": frm, "to": to},
        "currency": (rate_table or {}).get("currency"),
        "billable": rate_table is not None,
        "byUser": by_user,
        "totals": {
            "hours": round(grand_hours, 2),
            "amount": round(grand_amount, 2) if rate_table is not None else None,
            "entries": sum(p["entries"] for p in people.values()),
            "people": len(people),
        },
    }

    if obj.output.value == "table":
        cols = [
            ("User", lambda r: r["user"].get("name")),
            ("Login", lambda r: r["user"].get("login")),
            ("Hours", "hours"),
            ("Entries", "entries"),
            ("Amount", "amount"),
        ]
        obj.emitter.emit(by_user, columns=cols, title=f"Time report {month or (frm or '') + '..' + (to or '')}")
        obj.emitter.message(f"TOTAL: {result['totals']['hours']}h" + (f", {result['currency'] or ''} {result['totals']['amount']}" if rate_table else ""))
    else:
        obj.emitter.emit(result)
