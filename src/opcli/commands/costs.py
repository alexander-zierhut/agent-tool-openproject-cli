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
from datetime import date, timedelta
from pathlib import Path

import typer

from .. import hal, resolve, serialize
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


def _infos(client):
    """Return (user_info, project_info) lookups backed by per-call caches, so rate
    keys can match login/name/id and identifier/name/id without refetching."""
    user_cache: dict = {}
    project_cache: dict = {}

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

    return user_info, project_info


def _rate_for_entry(rate_table, user_info, project_info, e) -> float | None:
    if not rate_table:
        return None
    info = user_info(e)
    pinfo = project_info(e)
    user_keys = [str(k) for k in (info.get("login"), info.get("name"), info["id"]) if k is not None]
    project_keys = [str(k) for k in (pinfo.get("identifier"), pinfo["name"], pinfo["id"]) if k is not None]
    return _rate_for(rate_table, user_keys, project_keys)


def _aggregate(entries, *, rate_table, user_info, project_info, by_project=True, by_activity=False) -> dict:
    """Group time entries per person, summing hours (and amount when a rate table
    is given), optionally broken down per project and/or per activity. Returns
    ``{"byUser": [...], "totals": {...}}`` — the shape `cost report` already emits."""
    people: dict = {}
    grand_hours = 0.0
    grand_amount = 0.0
    for e in entries:
        info = user_info(e)
        uid = info["id"]
        hours = iso_to_hours(e.get("hours")) or 0.0
        pinfo = project_info(e)
        proj_name = pinfo["name"]
        rate = _rate_for_entry(rate_table, user_info, project_info, e)
        amount = hours * rate if rate is not None else None
        person = people.setdefault(
            uid,
            {"user": info, "hours": 0.0, "entries": 0, "amount": 0.0 if rate_table else None,
             "projects": {}, "activities": {}},
        )
        person["hours"] += hours
        person["entries"] += 1
        if amount is not None:
            person["amount"] = (person["amount"] or 0.0) + amount
        if by_project:
            pj = person["projects"].setdefault(
                proj_name, {"project": proj_name, "hours": 0.0, "amount": 0.0 if rate_table else None, "rate": rate})
            pj["hours"] += hours
            if amount is not None:
                pj["amount"] = (pj["amount"] or 0.0) + amount
        if by_activity:
            act = hal.link_title(e, "activity") or "(none)"
            ab = person["activities"].setdefault(
                act, {"activity": act, "hours": 0.0, "amount": 0.0 if rate_table else None})
            ab["hours"] += hours
            if amount is not None:
                ab["amount"] = (ab["amount"] or 0.0) + amount
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
        if by_activity:
            row["activities"] = [
                {"activity": ab["activity"], "hours": round(ab["hours"], 2),
                 "amount": round(ab["amount"], 2) if ab["amount"] is not None else None}
                for ab in p["activities"].values()
            ]
        by_user.append(row)
    by_user.sort(key=lambda r: r["hours"], reverse=True)

    return {
        "byUser": by_user,
        "totals": {
            "hours": round(grand_hours, 2),
            "amount": round(grand_amount, 2) if rate_table is not None else None,
            "entries": sum(p["entries"] for p in people.values()),
            "people": len(people),
        },
    }


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

    # user/project detail lookups (cached) shared by the detailed and summary paths
    user_info, project_info = _infos(client)

    def rate_for_entry(e) -> float | None:
        return _rate_for_entry(rate_table, user_info, project_info, e)

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

    agg = _aggregate(entries, rate_table=rate_table, user_info=user_info,
                     project_info=project_info, by_project=by_project)
    result = {
        "period": {"month": month, "from": frm, "to": to},
        "currency": (rate_table or {}).get("currency"),
        "billable": rate_table is not None,
        "byUser": agg["byUser"],
        "totals": agg["totals"],
    }

    if obj.output.value == "table":
        cols = [
            ("User", lambda r: r["user"].get("name")),
            ("Login", lambda r: r["user"].get("login")),
            ("Hours", "hours"),
            ("Entries", "entries"),
            ("Amount", "amount"),
        ]
        obj.emitter.emit(result["byUser"], columns=cols, title=f"Time report {month or (frm or '') + '..' + (to or '')}")
        obj.emitter.message(f"TOTAL: {result['totals']['hours']}h" + (f", {result['currency'] or ''} {result['totals']['amount']}" if rate_table else ""))
    else:
        obj.emitter.emit(result)


def _open_for_project(client, doc, *, cutoff_key, cutoff_name, to_date, rate_table, by_activity):
    """Compute the open (unbilled) hours for one project, or None if it has no
    cut-off date recorded. Window = day after the cut-off .. --to."""
    pid = doc.get("id")
    cutoff = serialize.custom_fields(doc).get(cutoff_key)
    if not cutoff:
        return None
    cutoff = str(cutoff)[:10]
    frm = (date.fromisoformat(cutoff) + timedelta(days=1)).isoformat()
    entries = query_time_entries(client, project=pid, frm=frm, to=to_date, desc=False, limit=None)
    user_info, project_info = _infos(client)
    agg = _aggregate(entries, rate_table=rate_table, user_info=user_info,
                     project_info=project_info, by_project=False, by_activity=by_activity)
    return {
        "project": {"id": pid, "name": doc.get("name"), "identifier": doc.get("identifier")},
        "cutoffField": cutoff_name,
        "cutoffDate": cutoff,
        "from": frm,
        "to": to_date,
        "openHours": agg["totals"]["hours"],
        "amount": agg["totals"]["amount"],
        "entries": agg["totals"]["entries"],
        "byUser": agg["byUser"],
    }


@app.command("open")
def open_(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", "-P", help="One project (id/identifier). Omit to sweep every billable project."),
    rates: Path = typer.Option(None, "--rates", help="JSON rate table for billable amounts (same format as `cost report`)."),
    cutoff_field: str = typer.Option(None, "--cutoff-field", help='Project date attribute holding the last-billed date (overrides `settings set-cutoff-field`).'),
    billable_field: str = typer.Option(None, "--billable-field", help='Project bool attribute flagging billable projects (used without -P; overrides `settings set-billable-field`).'),
    to: str = typer.Option(None, "--to", help="End date YYYY-MM-DD (default: today)."),
    by_activity: bool = typer.Option(True, "--by-activity/--no-by-activity", help="Break each person down by activity."),
) -> None:
    """Unbilled hours since the last billing date — the join the API won't do.

    Reads a project's "billed through" date attribute, sums the time booked from
    the day AFTER it up to --to (today by default), and reports open hours per
    user (and amounts if --rates is given). Without -P it sweeps every project
    whose billable-flag attribute is true, so one call answers "where is anything
    outstanding?". Which attributes hold the cut-off date and the billable flag is
    instance-specific: set them once with `settings set-cutoff-field` /
    `settings set-billable-field`, or pass --cutoff-field / --billable-field.
    """
    obj = ctx_obj(ctx)
    client = obj.client()
    rate_table = _load_rates(rates)
    cutoff_name = cutoff_field or obj.config.cost_cutoff_field
    if not cutoff_name:
        raise OpError(
            'no billing cut-off field configured. Pass --cutoff-field "<name>" or run '
            '`openproject settings set-cutoff-field "<name>"`.'
        )
    to_date = to or date.today().isoformat()
    # customFieldNN is instance-wide, so resolve the name -> key once (global form).
    cutoff_key = resolve.project_cf_key(client, cutoff_name)

    if project:
        doc = resolve.project(client, project)
        res = _open_for_project(client, doc, cutoff_key=cutoff_key, cutoff_name=cutoff_name,
                                to_date=to_date, rate_table=rate_table, by_activity=by_activity)
        if res is None:
            raise OpError(
                f"project {doc.get('name')!r} has no value in cut-off field {cutoff_name!r} — "
                "nothing to compute an open balance from."
            )
        res["currency"] = (rate_table or {}).get("currency")
        res["billable"] = rate_table is not None
        if obj.output.value == "table":
            cols = [
                ("User", lambda r: r["user"].get("name")),
                ("Login", lambda r: r["user"].get("login")),
                ("Hours", "hours"),
                ("Entries", "entries"),
                ("Amount", "amount"),
            ]
            obj.emitter.emit(res["byUser"], columns=cols,
                             title=f"{res['project']['name']}: open since {res['from']} (billed through {res['cutoffDate']})")
            obj.emitter.message(
                f"OPEN: {res['openHours']}h" + (f", {res['currency'] or ''} {res['amount']}" if rate_table else ""))
        else:
            obj.emitter.emit(res)
        return

    # ---- sweep every project flagged billable ----
    billable_name = billable_field or obj.config.cost_billable_field
    if not billable_name:
        raise OpError(
            'without -P you must name the billable flag attribute: --billable-field "<name>" '
            'or `openproject settings set-billable-field "<name>"`.'
        )
    billable_key = resolve.project_cf_key(client, billable_name)

    projects_out: list = []
    skipped: list = []
    grand_hours = 0.0
    grand_amount = 0.0
    total_entries = 0
    for p in client.collect("projects", limit=None):
        if serialize.custom_fields(p).get(billable_key) is not True:
            continue
        res = _open_for_project(client, p, cutoff_key=cutoff_key, cutoff_name=cutoff_name,
                                to_date=to_date, rate_table=rate_table, by_activity=by_activity)
        if res is None:
            skipped.append({"project": {"id": p.get("id"), "name": p.get("name")}, "reason": f"no {cutoff_name!r} value"})
            continue
        projects_out.append(res)
        grand_hours += res["openHours"]
        total_entries += res["entries"]
        if res["amount"] is not None:
            grand_amount += res["amount"]
    projects_out.sort(key=lambda r: r["openHours"], reverse=True)
    payload = {
        "cutoffField": cutoff_name,
        "billableField": billable_name,
        "to": to_date,
        "currency": (rate_table or {}).get("currency"),
        "billable": rate_table is not None,
        "projects": projects_out,
        "skipped": skipped,
        "totals": {
            "openHours": round(grand_hours, 2),
            "amount": round(grand_amount, 2) if rate_table is not None else None,
            "entries": total_entries,
            "projects": len(projects_out),
        },
    }
    if obj.output.value == "table":
        cols = [
            ("Project", lambda r: r["project"].get("name")),
            ("Billed through", "cutoffDate"),
            ("Open hours", "openHours"),
            ("Entries", "entries"),
            ("Amount", "amount"),
        ]
        obj.emitter.emit(projects_out, columns=cols, title=f"Unbilled hours (to {to_date})")
        msg = f"TOTAL: {round(grand_hours, 2)}h across {len(projects_out)} project(s)"
        if rate_table is not None:
            msg += f", {(rate_table or {}).get('currency') or ''} {round(grand_amount, 2)}"
        if skipped:
            msg += f"; {len(skipped)} skipped (no cut-off)"
        obj.emitter.message(msg)
    else:
        obj.emitter.emit(payload)
