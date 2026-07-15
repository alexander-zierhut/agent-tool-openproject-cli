# Usage guide

Task-oriented walkthroughs for the `openproject` CLI. For the exhaustive
option-by-option reference see [COMMANDS.md](COMMANDS.md); for AI-agent usage see
[AGENTS.md](../AGENTS.md).

- [Setup & login](#setup--login)
- [Work packages](#work-packages)
- [Searching effectively](#searching-effectively)
- [Assignees & members](#assignees--members)
- [Comments](#comments)
- [Time tracking & monthly invoicing](#time-tracking--monthly-invoicing)
- [Custom fields](#custom-fields)
- [Attachments & Nextcloud](#attachments--nextcloud)
- [Notifications](#notifications)
- [Output formats & field selection](#output-formats--field-selection)
- [Multiple instances (profiles)](#multiple-instances-profiles)
- [Scripting & automation](#scripting--automation)

---

## Setup & login

```bash
# point at your instance and verify + store the API token in your OS keyring
openproject auth login --url https://openproject.example.com --token opapi-xxxx
openproject auth whoami            # confirm who you are
openproject auth status            # profile, credential backend, connectivity
```

Generate the API token in OpenProject under *My account → Access tokens → API*.
For CI/agents, skip the keyring and use env vars: `OPCLI_BASE_URL`, `OPCLI_TOKEN`.

## Work packages

```bash
# create
openproject wp create "Login button misaligned" --project webshop --type Bug \
    --assignee me --priority High --due-date 2026-08-15 --estimated 3

# read / list
openproject wp get 1234
openproject wp list --project webshop --status open

# update (lockVersion handled automatically)
openproject wp update 1234 --status "In progress" --done-ratio 50
openproject wp assign 1234 jane.doe          # or `--assignee none` to clear
openproject wp move 1234 mobile-app          # change project
openproject wp watch 1234 me                 # follow changes
openproject wp delete 1234 -y
```

Discover what fields (including custom fields) a project/type accepts:

```bash
openproject wp schema --project webshop --type Bug
```

## Searching effectively

Three levels, pick whichever is quickest:

```bash
# 1) plain flags
openproject search wp --mine --overdue
openproject search wp --project webshop --type Bug --priority High --updated-since 7d
openproject search wp --unassigned --status open

# 2) presets
openproject search mine
openproject search overdue
openproject search recent --days 3

# 3) --where expressions (no JSON)
openproject search wp --where "status = open" --where "assignee = me" --where "updated > 14d"
```

Don't remember a field name or value? Ask:

```bash
openproject search fields --project webshop   # filterable fields (incl. custom fields)
openproject search operators                  # operator cheat-sheet
openproject search values status              # allowed values
```

## Assignees & members

Only project members can be assignees. A new project has none, so add people first:

```bash
openproject user available webshop                       # who can be assigned
openproject member add --project webshop --user jane.doe --role Member
openproject member list --project webshop
openproject member update 55 --role "Project admin"      # replaces the role set
openproject member remove 55 -y
```

## Comments

```bash
openproject comment add 1234 "Deployed to staging — please retest."
openproject comment list 1234
openproject comment edit 987 "Deployed to staging (v2) — please retest."   # 987 = activity id
```

`comment add` sends markdown and can `--notify`/`--no-notify` (default off).

## Time tracking & monthly invoicing

```bash
# log time (decimals or ISO-8601 both accepted)
openproject time add 2.5 --work-package 1234 --activity Development --comment "debugging"
openproject time add 1 --project webshop --date 2026-07-10

# review
openproject time list --user me --month 2026-07
openproject time activities --project webshop

# per-person billing report for a month
openproject cost report --month 2026-07 --rates rates.json
```

`rates.json` (see [`rates.example.json`](../rates.example.json)) — most specific
rate wins (project+user → project default → user → global default):

```json
{
  "currency": "EUR",
  "default": 90,
  "users":    { "admin": 120, "jane.doe": 100 },
  "projects": { "webshop": { "default": 100, "admin": 110 } }
}
```

> The OpenProject API exposes no hourly rates or cost reports, so `cost report`
> sums time entries client-side and applies your rate table. Without `--rates`
> it reports hours only.

## Custom fields

Custom fields are created in the OpenProject admin UI (not the API), but you can
discover and set them:

```bash
openproject cf wp --project webshop --type Bug          # customFieldN + allowed values
openproject wp create "Task" --project webshop \
    --custom-fields '{"customField1":"INV-2026-007","customField2":{"href":"/api/v3/custom_options/3"}}'
```

Scalar fields take a value; list/user/version fields take `{"href": "..."}`.

## Attachments & Nextcloud

```bash
openproject attach upload 1234 ./report.pdf --description "Q3 report"
openproject attach list 1234
openproject attach download 77 -O ./out.pdf
openproject attach delete 77 -y

# link an existing Nextcloud/storage file (storage configured in admin)
openproject filelink storages
openproject filelink add 1234 --storage 1 --file-id 9182 --file-name "Contract.pdf"
```

## Notifications

```bash
openproject notify list                 # unread by default
openproject notify list --today
openproject notify count --today        # {"total":.., "unread":.., "today":.., "todayUnread":..}
openproject notify read 5
openproject notify read-all
```

## Output formats & field selection

```bash
openproject wp list --project webshop -o table          # human tables
openproject wp list --project webshop -f markdown        # paste into docs
openproject settings set-format table                    # persist a default

# choose exactly which fields to return/show (dotted paths ok)
openproject search mine --fields id,subject,status,assignee.name
```

`--format/-f`, `-o`, and `--fields` work anywhere on the line (before or after
the command). Precedence: `--format` → `-o` → `$OPCLI_FORMAT` → saved default → json.

## Multiple instances (profiles)

```bash
openproject auth login --url https://prod.example.com  --token opapi-a --name prod
openproject auth login --url https://staging.example.com --token opapi-b --name staging
openproject -p staging wp list          # target a profile per-invocation
```

## Scripting & automation

- JSON on stdout, structured errors on stderr, meaningful exit codes — see
  [AGENTS.md](../AGENTS.md).
- `openproject raw {get,post,patch,delete} <path>` reaches any endpoint the typed
  commands don't wrap.
- Pipe to `jq`: `openproject search mine --fields id,subject | jq -r '.[].subject'`.
