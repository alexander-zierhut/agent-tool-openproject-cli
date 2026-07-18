# openproject — the agent-ready OpenProject CLI

> A fast, scriptable **OpenProject CLI** for managing work packages, projects,
> time tracking, comments, and per-person cost reports from your terminal — and
> the first OpenProject command-line tool designed to be driven by **AI agents**
> (Claude, Cursor, LLM tool-loops) as well as humans.

[![PyPI](https://img.shields.io/pypi/v/agent-tool-openproject-cli)](https://pypi.org/project/agent-tool-openproject-cli/)
[![CI](https://github.com/alexander-zierhut/agent-tool-openproject-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/alexander-zierhut/agent-tool-openproject-cli/actions/workflows/ci.yml)
![Python](https://img.shields.io/pypi/pyversions/agent-tool-openproject-cli)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Agent ready](https://img.shields.io/badge/agent-ready-8A2BE2)

**Install:** `pipx install agent-tool-openproject-cli` — then run `openproject guide`.

[**agent-tool-openproject-cli**](https://pypi.org/project/agent-tool-openproject-cli/)
(the installed command is `openproject`) is a Python command-line interface for the
[OpenProject](https://www.openproject.org/) REST API v3. It covers the whole
day-to-day workflow — **work packages** (create/update/delete/move), assignees,
custom fields, projects, comments, **time entries**, a genuinely good
**work-package search**, notifications, wiki, attachments with **Nextcloud** file
links, and **per-person time & cost reporting for monthly invoicing** — all with
first-class JSON output so it slots straight into automation and AI agents.

### Why this OpenProject CLI?

- 🤖 **Agent-ready** — structured JSON on stdout, structured errors on stderr, and
  stable exit codes. Plus a built-in **`openproject guide`** playbook so an agent
  can learn the tool from the tool itself. See [AGENTS.md](AGENTS.md).
- 🔎 **Discoverable search** — filter with plain flags (`--mine`, `--overdue`,
  `--updated-since 7d`), one-word presets (`search mine`), or `--where` expressions.
  Never memorise filter JSON: `search fields`, `search operators`, `search values`.
- 🖇️ **Four output formats** — `json` (default), `table`, `markdown`, and `csv`;
  pick per command with `-f`, set a default, select exact `--fields`, or `--stream`
  NDJSON for big result sets.
- 🧪 **Safe by default** — `--dry-run` previews any write; the client retries
  transient failures; and `openproject context` gives sticky per-session defaults.
- 💶 **Invoicing extras** — per-person cost reports, and a detailed CSV export that
  includes **time-entry custom fields** (which OpenProject's own reports can't).
- 🔐 **Safe credentials** — API token stored in the OS keyring (Secret Service /
  macOS Keychain / Windows Credential Locker), with a `0600` file fallback.
- 🧰 **Escape hatch** — `openproject raw` calls any endpoint the typed commands
  don't wrap.
- 📦 **Install anywhere** — pipx, pip, or a single self-contained binary (no Python
  required on the target).

**Docs:** [Usage guide](docs/USAGE.md) · [Full command reference](docs/COMMANDS.md) · [Agent guide](AGENTS.md)

**Keywords:** OpenProject CLI, OpenProject command line, OpenProject API client,
work package automation, time tracking CLI, project management CLI, AI agent tool,
LLM tooling, Claude, DevOps automation, invoicing.

## The command surface

Everything is discoverable from the binary — `openproject --help`, then
`openproject guide` for the playbook and `openproject <group> --help` for any
group. The top level:

```text
 Usage: openproject [OPTIONS] COMMAND [ARGS]...

 Agent-friendly CLI for OpenProject (work packages, projects, time, search,
 invoicing).

 Output is JSON on stdout by default (errors are JSON on stderr with a non-zero
 exit code); add `-o table` or `-o markdown`, or trim with `--fields id,subject`.
 Pass names not ids (`--assignee jane.doe`, `--status "In progress"`, `me`).

 New here / no context? Run `openproject guide` for the full playbook, or
 `openproject search fields` to discover what you can filter on.

╭─ Commands ───────────────────────────────────────────────────────────────────────╮
│ guide     Built-in operating guide — how to use this CLI without external docs.  │
│ auth      Log in, log out, inspect credentials.                                  │
│ project   Create, list, archive projects.                                        │
│ wp        Work packages: CRUD, move, assign, watch.                              │
│ search    Powerful work-package (and global) search.                             │
│ comment   Add, edit, list work-package comments.                                 │
│ time      Log, edit, list time entries + reports.                                │
│ user      Users, groups, memberships, assignable people.                         │
│ member    Project memberships & roles.                                           │
│ cf        Inspect custom fields / resource schemas.                              │
│ notify    In-app notifications.                                                  │
│ wiki      Wiki pages (read + write where supported).                             │
│ attach    Attachments / file uploads on work packages.                           │
│ filelink  Nextcloud/file-storage links on work packages.                         │
│ cost      Time & cost reporting per person/project (invoicing).                  │
│ raw       Escape hatch: call any API endpoint directly.                          │
│ settings  View & change CLI settings (default output format).                    │
│ context   Sticky session defaults (project/user/filters) reused across commands. │
│ install   Integrate with other tools (e.g. `install claude`).                    │
╰──────────────────────────────────────────────────────────────────────────────────╯
```

Global options — `-o/--output json|table|markdown|csv`, `--fields`, `--dry-run`,
`--stream`, `--no-context` — are stripped from argv before parsing, so they work
anywhere on the line. Full reference: [docs/COMMANDS.md](docs/COMMANDS.md).

## Compatibility

- **OpenProject API:** the stable REST **API v3** (HAL+JSON).
- **Tested against:** OpenProject **13, 14, 15, 16, and 17** (Community, all-in-one).
  The full integration suite passes on every one — the CLI covers the whole feature
  set across all five majors. (15.x also runs in CI on every push; the `compat`
  workflow re-runs the 13–17 matrix.)
- **Version notes uncovered by testing:**
  - **v16+** — time entries require a work package. Logging time against a *project*
    only (`time add --project` with no `--work-package`) is rejected with
    "Logged for can't be blank"; log against a work package instead.
  - **v17** — the Docker image needs a real `SECRET_KEY_BASE` env var to boot
    (a container-config change, unrelated to the CLI).
  - The time-entry work-package **filter** name differs across versions
    (`work_package_id` on ≤15 vs the newer `entity_*` form); the CLI detects and
    adapts automatically.
- **Python:** 3.10+.

Anything version-specific can be reached directly with `openproject raw <method> <path>`.

---

## Quick start

### 1. Install

Pick whichever fits your target:

**a) `pipx` (recommended — isolated, puts `openproject` on your PATH, needs Python 3.10+)**
```bash
pipx install agent-tool-openproject-cli          # installs the `openproject` command
```

**b) `pip`**
```bash
pip install agent-tool-openproject-cli           # from PyPI
# or, for local development from a clone:
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

**c) Single self-contained binary (no Python on the target)**

Download the prebuilt binary for your OS from the GitHub Releases page, then:
```bash
chmod +x openproject-linux-x86_64 && mv openproject-linux-x86_64 /usr/local/bin/openproject
openproject --help
```
Or build one yourself — produces a single `dist/openproject` (~16 MB) that
bundles the interpreter and all deps, including the OS keyring backends:
```bash
pip install -e '.[build]'
./scripts/build_binary.sh          # -> dist/openproject   (.exe on Windows)
```
CI (`.github/workflows/release.yml`) builds Linux/macOS/Windows binaries on
every `v*` tag and attaches them to the release.

> The command is `openproject`. The short name `op` is intentionally **not**
> claimed, to avoid clobbering another tool of that name (this machine already
> has an OpenProject CLI at `/usr/local/bin/op`). Add your own alias if you want
> a shorter command, e.g. `alias opr=openproject`.

### Use with Claude Code

Register the CLI as a Claude Code **skill** so Claude auto-uses it whenever you
mention OpenProject:

```bash
openproject install claude          # writes ~/.claude/skills/openproject/SKILL.md
openproject install claude --print  # preview the skill first
openproject install claude --uninstall
```

The skill points Claude at `openproject guide`, so it learns the tool from the
tool. On the **first interactive run**, if Claude Code is detected, the CLI also
offers to install it (once) — decline and nothing changes. Add `--memory` to also
drop a one-line hint in `~/.claude/CLAUDE.md`, or `--project` to install into the
current repo's `.claude/`.

### 2. Bring up a local OpenProject (for development/testing)

```bash
docker compose up -d                 # boots the all-in-one image on :8090
docker compose logs -f openproject   # watch until "seeding" finishes (~5 min)
eval "$(./scripts/get_admin_token.sh)"   # mints & exports APITOKEN
```

Web UI: http://localhost:8090 — admin / `AdminPassw0rd!`

### 3. Log in

```bash
openproject auth login --url http://localhost:8090 --token "$APITOKEN"
openproject auth whoami
```

`login` verifies the token against `/users/me`, saves the connection profile to
`~/.config/op-cli/config.json`, and stores the token in your keyring. Thereafter
just run `openproject ...`.

For headless/CI use you can skip the keyring entirely and pass everything via
environment variables:

```bash
export OPCLI_BASE_URL=http://localhost:8090
export OPCLI_TOKEN=opapi-xxxxxxxx
openproject wp list
```

---

## Command reference

Run `openproject <group> --help` for full options. Highlights:

### Work packages — `openproject wp`

```bash
openproject wp create "Fix login bug" --project my-proj --type Bug \
    --assignee me --priority High --due-date 2026-08-01 --estimated 4
openproject wp get 42
openproject wp list --project my-proj --status open --assignee me
openproject wp update 42 --status "In progress" --done-ratio 50
openproject wp move 42 other-project
openproject wp assign 42 jane.doe          # or `openproject wp assign 42 none` to clear
openproject wp watch 42 me
openproject wp schema --project my-proj --type Task   # discover fields + custom fields
openproject wp delete 42 -y
```

### Search — `openproject search`

The star feature, designed to be usable **without memorising the JSON filter
language**. Three ways to search, easiest first:

**1. Plain-language flags** on `search wp`:

```bash
openproject search wp "payment timeout"                    # full text
openproject search wp --mine --overdue                     # my past-due items
openproject search wp --project my-proj --status open --assignee jane.doe
openproject search wp --type Bug --priority High --updated-since 7d
openproject search wp --unassigned --project my-proj
openproject search wp --version "Sprint 12" --all
openproject search wp --id 42,57,103                       # specific ids
openproject search wp --due-before 2026-08-01              # or --due-before +14d
openproject search wp "invoice" --count                    # just the total
openproject search wp --group-by status --project my-proj
```

Dates accept ISO (`2026-08-01`) or relative specs: `7d`, `2w`, `1m`, `+30d`,
`today`, `yesterday`.

**2. Presets** — common searches as one word:

```bash
openproject search mine           # open, assigned to me
openproject search overdue        # past due & still open
openproject search unassigned     # open with no assignee
openproject search reported       # I created them
openproject search watching       # I'm watching
openproject search recent --days 3
```

**3. `--where` expressions** — compact, no JSON, repeatable (AND-ed):

```bash
openproject search wp --where "status = open" --where "assignee = me"
openproject search wp --where "assignee:none"              # unassigned
openproject search wp --where "updated > 7d" --where "priority = High"
openproject search wp --where "subject ~ timeout"
```

And when you don't remember what's available, **ask the CLI**:

```bash
openproject search fields                 # what you can filter on (live)
openproject search fields --project x     # incl. that project's custom fields
openproject search operators              # what =, o, !*, <>d, ~ … mean
openproject search values status          # allowed values for a field
openproject search values type
openproject search values version --project x
```

The raw JSON filter escape hatch is still there when you need it:

```bash
openproject search wp --filters '[{"customField1":{"operator":"~","values":["INV-2026"]}}]'
```

### Projects — `openproject project`

```bash
openproject project create "Client X" --identifier client-x --description "..."
openproject project list                       # add --archived for archived ones
openproject project archive client-x           # PATCH active=false
openproject project unarchive client-x
openproject project delete client-x -y
```

### Assignees & members — `openproject wp assign`, `openproject member`, `openproject user`

```bash
openproject user available my-proj             # who can be assigned in a project
openproject member add --project my-proj --user jane.doe --role Member
openproject member list --project my-proj
openproject member update 12 --role "Project admin"   # replaces the role set
openproject member remove 12 -y
```

### Comments — `openproject comment`

```bash
openproject comment add 42 "Deployed to staging."
openproject comment list 42
openproject comment edit 137 "Deployed to staging (corrected)."   # 137 = activity id
```

### Time entries — `openproject time`

```bash
openproject time add 2.5 --work-package 42 --activity Development --comment "debugging"
openproject time add 1 --project my-proj --date 2026-07-10        # log against a project
openproject time list --user me --month 2026-07
openproject time edit 88 --hours 3
openproject time activities --project my-proj
openproject time delete 88 -y
```

Hours accept decimals (`2.5`) or ISO-8601 (`PT2H30M`) — they're converted for you.

### Custom fields — `openproject cf`

Custom fields can't be *created* via the API (admin/Rails only), but you can
discover them and set values:

```bash
openproject cf wp --project my-proj --type Task     # lists customFieldN + allowed values
openproject wp create "Task" --project my-proj \
    --custom-fields '{"customField1":"INV-2026-007","customField2":{"href":"/api/v3/custom_options/3"}}'
```

Value-type fields (string/int/date/bool) take a scalar; list/user/version fields
take `{"href": "..."}` (use the ids from `openproject cf wp`).

### Time & cost reporting (invoicing) — `openproject cost`

OpenProject's API exposes **no** hourly rates or cost reports, so this report
sums time entries per person and applies a **rate table you supply**:

```bash
openproject cost report --month 2026-07 --rates rates.json
openproject cost report --from 2026-07-01 --to 2026-07-31 --user jane.doe --rates rates.json
```

`rates.json` (see `rates.example.json`):

```json
{
  "currency": "EUR",
  "default": 90,
  "users":    { "admin": 120, "jane.doe": 100 },
  "projects": { "client-x": { "default": 100, "admin": 110 } }
}
```

Without `--rates` it reports hours only. Most specific rate wins:
project+user → project default → user → global default.

**Detailed export with time-entry custom fields** — one row per entry, including
the time entry's custom fields (something OpenProject's own reports can't export).
Perfect for invoicing spreadsheets:

```bash
openproject cost report --month 2026-07 --rates rates.json --detailed -o csv > july.csv
# columns: date,user,project,workPackage,activity,hours,rate,amount,comment,Cost Center,Billable,…
```

Set the custom fields when logging: `openproject time add 2 -w 42 --custom-fields '{"customField3":"CC-1000","customField4":true}'` (discover them with `openproject cf time`).

### Notifications — `openproject notify`

```bash
openproject notify list                # unread by default; --state read|all
openproject notify list --today        # only today's
openproject notify count               # {"total": N, "unread": M}
openproject notify count --today       # adds today / todayUnread
openproject notify read 5
openproject notify unread 5
openproject notify read-all
```

### Attachments — `openproject attach`

```bash
openproject attach upload 42 ./report.pdf --description "Q3 report"
openproject attach list 42
openproject attach download 7 -O ./out.pdf
openproject attach delete 7 -y
```

### Nextcloud / file storages — `openproject filelink`

Links an existing file in a configured storage (e.g. your Nextcloud) to a work
package. The storage must be set up in OpenProject admin first.

```bash
openproject filelink storages
openproject filelink add 42 --storage 1 --file-id 123 --file-name "Contract.pdf"
openproject filelink list 42
openproject filelink delete 9 -y
```

### Wiki — `openproject wiki`

> **Limitation:** OpenProject API v3 only exposes wiki *metadata* (id + title)
> and page attachments — there is no API to read or write the wiki body text.

```bash
openproject wiki get 3
openproject wiki attachments 3
```

### Raw escape hatch — `openproject raw`

```bash
openproject raw get work_packages/42
openproject raw get work_packages -p 'filters=[{"status":{"operator":"o","values":null}}]'
openproject raw post work_packages -d '{"subject":"x","_links":{"project":{"href":"/api/v3/projects/1"},"type":{"href":"/api/v3/types/1"}}}'
openproject raw patch work_packages/42 -d '{"lockVersion":3,"subject":"y"}'
openproject raw delete work_packages/42
```

### Auth & profiles — `openproject auth`

```bash
openproject auth login --url https://op.example.com --token opapi-xxxx --name prod
openproject auth status
openproject -p prod wp list          # use a specific profile per-invocation
openproject auth logout --name prod
```

### Output format & settings — `openproject settings`

Four output formats: **`json`** (default), **`table`**, **`markdown`**, and
**`csv`**. Choose per command, or set a persistent default.

```bash
openproject wp list -o table                 # global flag (before the command)
openproject wp list --format markdown        # --format/-f works AFTER any command too
openproject search wp --mine -o csv          # spreadsheet export
openproject wp get 42 --fields id,subject,assignee.name    # pick exact fields (dotted ok)

openproject settings set-format table        # persist a default
openproject settings show                    # current default, config path, profiles
```

**Preview & scale flags** (work anywhere on the line):

```bash
openproject wp update 42 --status Closed --dry-run   # prints the request, sends nothing
openproject search wp --project big --stream          # NDJSON, one object per line, as fetched
```

The client also **retries** transient failures (429 rate-limits + 5xx on reads)
with backoff, honoring `Retry-After`.

### Session context — `openproject context`

Stop repeating `--project`/`--user`/filters: set them once and they apply to
later commands as defaults (explicit flags always win; `--no-context` bypasses).

```bash
openproject context set --project webshop --assignee me
openproject context show               # see the active defaults
openproject wp list                    # behaves like: wp list --project webshop --assignee me
openproject wp list --project other    # explicit flag wins
openproject --no-context wp list       # ignore the context for one command

openproject context save sprint        # name it, switch between saved contexts
openproject context use sprint
```

On the **first interactive run** the CLI asks which default format you'd like and
saves your choice. Non-interactive runs (pipes, CI, agents) never prompt — they
default to `json`. Precedence: `--format`/`-f` → `-o/--output` → `$OPCLI_FORMAT`
→ saved default → `json`.

---

## Output for agents

- Default output is pretty JSON on **stdout**. Errors are structured JSON on
  **stderr** with a non-zero exit code (`{"error": "...", "status": 404}`).
- Exit codes: `0` ok, `4` auth, `5` not found, `6` conflict, `7` validation,
  `1`/`3` general/config.
- Reference-by-name works everywhere sensible: `--status "In progress"`,
  `--assignee jane.doe`, `--project client-x`, `--activity Development`,
  `--type Bug` are resolved to ids for you. `me` resolves to the current user.
- Discover filters at runtime with `openproject search fields`,
  `search operators`, and `search values <field>` — no need to memorise the
  filter JSON.

---

## Contributing / Development

**You do not need OpenProject, Docker, or a token to contribute.** Clone it and run:

```bash
pip install -e '.[test]'
pytest                    # 144 passed, 103 skipped — ~2s, no server needed
```

That is the whole setup. The suite is green on a clean checkout: the tests that
need a live instance detect there isn't one and skip with a message telling you
what to set. `make test-unit` runs the same hermetic set explicitly.

Please add a test with your change — `pytest -m "not integration"` is fast enough
to run on every save.

### The deeper tier (only if you're touching the client↔server seam)

Boot a real OpenProject and the integration tests light up automatically:

```bash
make up        # docker compose up + wait for health (first boot seeds the DB, ~5 min)
make env       # mint the admin token, seed test data, write .env
make test      # the full suite against the live instance
make down      # tear down
```

Or by hand:

```bash
docker compose up -d
eval "$(./scripts/get_admin_token.sh)"
export OPCLI_BASE_URL=http://localhost:8090 OPCLI_TOKEN="$APITOKEN"
./scripts/seed_test_data.sh          # modules + custom fields + a 2nd user
pytest
```

A few tests need a second, non-admin actor (to generate a notification). Set
`OPCLI_SECOND_TOKEN` to `jane.doe`'s token to enable them:

```bash
export OPCLI_SECOND_TOKEN=$(./scripts/get_admin_token.sh jane.doe | grep APITOKEN | cut -d= -f2)
```

CI runs all of this on every push, so you don't have to. See `docs/API_NOTES.md`
for the researched API details behind the implementation.

---

## Security notes

- The API token is the only secret persisted, and it goes to the OS keyring by
  default. `openproject auth status` shows which backend is in use.
- On a headless box with no Secret Service, the token falls back to a `0600`
  file at `~/.config/op-cli/credentials.json` and the CLI warns you.
- `OPCLI_TOKEN` in the environment always takes precedence (nothing is written
  to disk in that mode).

## Known limitations (API v3, not the CLI)

- **Wiki** is read-only metadata (no body text over the API).
- **Costs**: no hourly rates or cost-report endpoints exist — hence the
  client-side rate table for invoicing.
- **Custom fields** can't be created via the API (admin UI / Rails only); the
  CLI discovers and sets them.

## Part of the family

Built on **[agent-tool-shared-cli](https://github.com/alexander-zierhut/agent-tool-shared-cli)** —
the chassis every tool in this family shares: JSON on stdout, JSON errors on
stderr, a stable cross-tool exit-code contract, `--dry-run`, four output formats,
and a built-in `guide` so an agent can learn each tool from the tool itself.

| Tool | Install | For |
| --- | --- | --- |
| [**drone-cli**](https://github.com/alexander-zierhut/agent-tool-drone-cli) | `pipx install agent-tool-drone-cli` | Drone CI — builds, failing-step logs, promotions |
| [**grafana-cli**](https://github.com/alexander-zierhut/agent-tool-grafana-cli) | `pipx install agent-tool-grafana-cli` | Grafana — log discovery, health scan, alert routing |
| [**openproject**](https://github.com/alexander-zierhut/agent-tool-openproject-cli) | `pipx install agent-tool-openproject-cli` | OpenProject — work packages, time, invoicing |
| [**lexware-office**](https://github.com/alexander-zierhut/agent-tool-lexware-office-cli) | `pipx install agent-tool-lexware-office-cli` | Lexware Office — invoices, contacts, AR-aging |

They compose over the shared contract:
`openproject time report --month 2026-07 && lexware-office invoice create ...`
turns tracked hours into an invoice.

## License

MIT — see [LICENSE](LICENSE).
