# openproject-cli — the agent-ready OpenProject command-line interface

> A fast, scriptable **OpenProject CLI** for managing work packages, projects,
> time tracking, comments, and per-person cost reports from your terminal — and
> the first OpenProject command-line tool designed to be driven by **AI agents**
> (Claude, Cursor, LLM tool-loops) as well as humans.

[![CI](https://github.com/alexander-zierhut/agent-tool-openproject-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/alexander-zierhut/agent-tool-openproject-cli/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Agent ready](https://img.shields.io/badge/agent-ready-8A2BE2)

`openproject-cli` is a Python command-line interface for the
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
- 🖇️ **Three output formats** — `json` (default), `table`, and `markdown`; pick per
  command with `-f`, set a default, or select exact `--fields`.
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

---

## Quick start

### 1. Install

Pick whichever fits your target:

**a) `pipx` (recommended — isolated, `openproject` on PATH, needs Python 3.10+)**
```bash
pipx install agent-tool-openproject-cli          # from PyPI (installs the `openproject` command)
pipx install git+https://github.com/alexander-zierhut/agent-tool-openproject-cli.git  # or straight from git
```

**b) `pip` into a venv (for development)**
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .          # from this directory
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

Three output formats: **`json`** (default, best for scripts/agents),
**`table`** (human-readable terminal tables), and **`markdown`** (paste into
docs/PRs). Choose per command, or set a persistent default.

```bash
openproject wp list -o table                 # global flag (before the command)
openproject wp list --format markdown        # --format/-f works AFTER any command too
openproject wp get 42 -f md

openproject settings set-format table        # persist a default
openproject settings show                    # current default, config path, profiles
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

## Testing

A full integration suite drives the real CLI against the live instance.

```bash
docker compose up -d
eval "$(./scripts/get_admin_token.sh)"
export OPCLI_BASE_URL=http://localhost:8090 OPCLI_TOKEN="$APITOKEN"
./scripts/seed_test_data.sh          # modules + custom fields + a 2nd user
pip install -e '.[test]'
pytest                               # 56 tests
```

A few tests need a second, non-admin actor (to generate a notification). Set
`OPCLI_SECOND_TOKEN` to `jane.doe`'s token to enable them:

```bash
export OPCLI_SECOND_TOKEN=$(./scripts/get_admin_token.sh jane.doe | grep APITOKEN | cut -d= -f2)
```

Without `OPCLI_BASE_URL`/`OPCLI_TOKEN` the integration tests skip and only the
pure-unit tests run — handy for CI. See `docs/API_NOTES.md` for the researched
API details behind the implementation.

Or just use the Makefile:

```bash
make up        # docker compose up + wait for health
make seed      # mint token, seed test data, write .env
make test      # run the suite
make down      # tear down
```

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
