"""`openproject guide` — a built-in operating manual.

The point of this command is self-sufficiency: an agent (or human) with only the
installed CLI and no other context can run `openproject guide` and learn the
output contract, how to authenticate, how to discover filters, and the gotchas —
without needing the README or any external docs.
"""

from __future__ import annotations

import typer

OVERVIEW = """\
openproject — operating guide (run `openproject guide <topic>` for details)

WHAT IT IS
  A CLI for OpenProject: work packages, projects, assignees, custom fields,
  comments, time entries, search, notifications, wiki, attachments, and
  per-person time/cost reporting for invoicing.

OUTPUT CONTRACT (important for scripting/agents)
  - stdout is JSON by default — parse it.
  - Errors go to stderr as JSON with a non-zero exit code: {"error": "...", "status": 404}.
  - Exit codes: 0 ok · 3 config · 4 auth · 5 not-found · 6 conflict(lockVersion) · 7 validation · 1 other.
  - Change format anywhere on the line: `-o table`, `-o markdown`, `-o csv` (or `-f ...`).
  - Trim output to what you need: `--fields id,subject,status,assignee.name` (dotted paths ok).
  - Get just a count: add `--count` to `search wp`.
  - Large result sets: add `--stream` for NDJSON (one JSON object per line).
  - PREVIEW a write without doing it: add `--dry-run` — prints the exact request and exits 0.

AUTHENTICATE
  Non-interactive (best for agents/CI — no keyring, never prompts):
    export OPCLI_BASE_URL=https://openproject.example.com
    export OPCLI_TOKEN=opapi-xxxxxxxx
  Or store in the OS keyring:  openproject auth login --url <URL> --token <TOKEN>
  Verify:  openproject auth whoami        (or `auth status`)

USE NAMES, NOT IDS
  Names are resolved for you: --status "In progress", --assignee jane.doe,
  --type Bug, --priority High, --project my-proj, --version "Sprint 3".
  `me` always means the authenticated user.

FIND THINGS — don't hand-write filter JSON
  Plain flags:   openproject search wp --mine --overdue --updated-since 7d
  Expressions:   openproject search wp --where "status = open" --where "updated > 7d"
  Presets:       openproject search mine | overdue | recent | unassigned | reported | watching
  Discover:      openproject search fields         # what you can filter on (live)
                 openproject search operators       # what =, o, !*, <>d, ~ mean
                 openproject search values status   # allowed values for a field

DISCOVER COMMANDS & OPTIONS
  openproject --help
  openproject <group> --help              e.g. `openproject wp --help`
  openproject <group> <command> --help    e.g. `openproject wp create --help`

KEY GOTCHAS (save yourself a round-trip)
  - `wp update` handles lockVersion automatically; `raw patch` does NOT (send it yourself).
  - Time `hours` accept decimals (2.5) or ISO-8601 (PT2H30M).
  - Assignees must be project members — a new project has none; add with `member add`.
  - `comment add` takes markdown; `comment edit` takes a plain string.
  - Wiki is read-only metadata over the API; costs have no rates, so `cost report`
    multiplies hours by a rate table you pass with --rates.
  - Anything not wrapped: `openproject raw {get,post,patch,delete} <path> [-d JSON]`.

TOPICS:  search · wp · time · comments · projects · costs · customfields · context · output · auth · notifications
"""

TOPICS: dict[str, str] = {
    "search": """\
SEARCH — three ways, easiest first

1) Flags:   openproject search wp --mine --overdue
            openproject search wp --project P --type Bug --priority High --updated-since 7d
            openproject search wp --unassigned --status open
            openproject search wp --id 42,57 --all
            Dates accept ISO (2026-08-01) or relative: 7d, 2w, 1m, +30d, today, yesterday.
2) Presets: openproject search mine | overdue | recent --days 3 | unassigned | reported | watching
3) --where: openproject search wp --where "status = open" --where "assignee = me" --where "updated > 14d"
            Operators in --where: =, !=, ~ (contains), >=, <=, >, <, and :open/:closed/:none/:any.
            Field aliases: updated->updatedAt, created->createdAt, due->dueDate.

DISCOVER (so you never guess):
   openproject search fields [--project P]   # every filterable field (incl. custom fields)
   openproject search operators              # operator cheat-sheet
   openproject search values <field>         # allowed values (status/type/priority/version/...)

Handy: --sort <field> --asc/--desc, --group-by status, --limit N (0=all), --count, --raw.
Default is OPEN work packages only; add --all for closed too.
""",
    "wp": """\
WORK PACKAGES
  create:  openproject wp create "Title" --project P --type Bug --assignee me --priority High \\
             --due-date 2026-08-01 --estimated 3 --description "..."
  read:    openproject wp get <id>            # add --raw for the full HAL document
  update:  openproject wp update <id> --status "In progress" --done-ratio 50   (lockVersion auto)
  assign:  openproject wp assign <id> jane.doe     (or `... none` / `wp unassign <id>`)
  move:    openproject wp move <id> other-project
  watch:   openproject wp watch <id> me            (list: `wp watchers <id>`)
  delete:  openproject wp delete <id> -y
  fields:  openproject wp schema --project P --type Bug   # discover writable + custom fields
  set custom fields:  --custom-fields '{"customField1":"INV-1","customField2":{"href":"/api/v3/custom_options/3"}}'
""",
    "time": """\
TIME ENTRIES
  log:     openproject time add 2.5 --work-package <id> --activity Development --comment "..."
           openproject time add 1 --project P --date 2026-07-10      (hours: 2.5 or PT2H30M)
  list:    openproject time list --user me --month 2026-07
           (filters: --from/--to dates, --work-package, --project)
  edit:    openproject time edit <id> --hours 3 --comment "..."
  delete:  openproject time delete <id> -y
  activities: openproject time activities --project P   (Development, Management, ...)
  NOTE: OpenProject 16+ requires a work package for time entries — logging against a
        project only (--project with no --work-package) is rejected there.
""",
    "comments": """\
COMMENTS (stored as work-package activities)
  add:   openproject comment add <wp_id> "markdown body"   (add --notify to email watchers)
  list:  openproject comment list <wp_id>
  edit:  openproject comment edit <activity_id> "plain string"   # NOTE: edit takes a plain string
  The activity_id comes from `comment list` (not the work-package id). No delete via the API.
""",
    "projects": """\
PROJECTS
  create:    openproject project create "Name" --identifier my-id --description "..." [--parent P] [--public]
  list:      openproject project list          (add --archived for archived ones)
  update:    openproject project update my-id --name "..." --description "..."
  archive:   openproject project archive my-id     (unarchive: `project unarchive my-id`)
  delete:    openproject project delete my-id -y
  Members:   openproject member add --project my-id --user jane.doe --role Member
             (only members can be assignees; `user available my-id` lists assignable people)
""",
    "costs": """\
TIME & COST REPORTING (for invoicing, per person)
  openproject cost report --month 2026-07 --rates rates.json
  openproject cost report --from 2026-07-01 --to 2026-07-31 --user jane.doe --rates rates.json

  The OpenProject API exposes no hourly rates, so you supply them. rates.json:
    {"currency":"EUR","default":90,"users":{"jane.doe":100},
     "projects":{"my-proj":{"default":100,"admin":110}}}
  Most specific wins: project+user > project default > user > global default.
  Without --rates you get hours only. Output groups by user, then by project.
""",
    "customfields": """\
CUSTOM FIELDS
  Custom fields are created in the OpenProject admin UI (not via the API). You can
  DISCOVER and SET them:
    openproject cf wp --project P --type Bug      # lists customFieldN, type, allowed values
    openproject cf project                        # project attributes
    openproject cf time                           # time-entry custom fields
  Set on create/update with --custom-fields (JSON):
    scalar (string/int/date/bool):  {"customField1":"INV-1"}
    reference (list/user/version):  {"customField2":{"href":"/api/v3/custom_options/3"}}
  Use the ids shown by `cf wp` / `search values customFieldN`.
""",
    "output": """\
OUTPUT & FIELDS
  Formats: json (default), table, markdown. Choose per command:
     openproject wp list -o table
     openproject wp get 42 -f markdown
  Set a default:  openproject settings set-format table   (see `settings show`)
  Select fields (dotted paths ok, works in every format):
     openproject search mine --fields id,subject,status,assignee.name
  -o/--format/-f and --fields work ANYWHERE on the line (before or after the command).
  Precedence: --format > -o > $OPCLI_FORMAT > saved default > json.
""",
    "auth": """\
AUTH & PROFILES
  login:   openproject auth login --url https://op.example.com --token opapi-xxxx [--name prod]
  check:   openproject auth whoami     |     openproject auth status
  logout:  openproject auth logout [--name prod]
  Env (non-interactive, no keyring): OPCLI_BASE_URL, OPCLI_TOKEN (+ OPCLI_PROFILE).
  Multiple instances: `openproject -p prod wp list` targets a saved profile.
  Get a token in OpenProject: My account -> Access tokens -> API.
""",
    "context": """\
SESSION CONTEXT — sticky defaults so you stop repeating flags
  A CLI has no live process, so "context" = durable saved defaults (not a running
  session). It's a map of option -> value auto-applied to later commands.

  set:    openproject context set --project webshop --assignee me
  show:   openproject context show          # ALWAYS check this to see active defaults
  clear:  openproject context clear         |  unset one: openproject context unset project
  save:   openproject context save sprint   # name the current context
  use:    openproject context use sprint    # switch to a saved one   |  list: context list

  How it applies: for any command with a matching option (--project, --user,
  --assignee, --status, --priority, --author, --query), the context value fills it
  IF you don't pass that flag. Explicit flags always win. Use the global
  --no-context to ignore the context for one command.

  AGENT NOTE: context is IMPLICIT state that changes command behaviour (e.g. scoping
  results to a project). If output looks wrongly scoped, run `openproject context
  show` or add `--no-context`. It is always inspectable and overridable.
""",
    "notifications": """\
NOTIFICATIONS (in-app)
  list:   openproject notify list                 (unread by default; --state read|all)
          openproject notify list --today
  count:  openproject notify count [--today]       -> {"total","unread","today","todayUnread"}
  mark:   openproject notify read <id> | unread <id> | read-all
""",
}


def guide(
    topic: str = typer.Argument(None, help="Optional topic: search, wp, time, comments, projects, costs, customfields, output, auth, notifications."),
) -> None:
    """Print a built-in operating guide so the CLI is usable without external docs.

    Run `openproject guide` for the overview, or `openproject guide <topic>` for a
    focused cheat-sheet (e.g. `openproject guide search`).
    """
    if not topic:
        typer.echo(OVERVIEW)
        return
    key = topic.strip().lower()
    text = TOPICS.get(key)
    if text is None:
        typer.echo(f"unknown topic '{topic}'. Available: " + ", ".join(TOPICS) + "\n")
        typer.echo(OVERVIEW)
        raise typer.Exit(code=2)
    typer.echo(text)
