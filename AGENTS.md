# Using `openproject` from an AI agent

This CLI is built to be driven by an LLM/agent (Claude Code, Cursor, custom tool
loops). This page is the **machine contract** — how to call it reliably and
cheaply. For the human tutorial see [README](README.md); for every option see
[docs/COMMANDS.md](docs/COMMANDS.md).

> **No context? Start here:** run **`openproject guide`** — the CLI ships a
> built-in playbook (output contract, auth, discovery, gotchas, recipes) so an
> agent can bootstrap from the tool alone, with no external docs. Then
> `openproject guide <topic>` (search, wp, time, costs, …) for focused cheat-sheets.

## The output contract

- **stdout is JSON by default.** Parse it directly. Success prints a JSON object
  or array to stdout and exits `0`.
- **Errors are JSON on stderr** with a non-zero exit code:
  ```json
  { "error": "The requested resource could not be found.", "status": 404 }
  ```
- **Exit codes** are stable and meaningful — branch on them:

  | Code | Meaning |
  | --- | --- |
  | 0 | success |
  | 1 | generic error |
  | 3 | config error (no profile / bad config) |
  | 4 | auth error (401/403) — token missing or wrong |
  | 5 | not found (404) |
  | 6 | conflict (409, stale lockVersion) |
  | 7 | validation error (422) — check `fieldErrors` in the JSON |

## Run it non-interactively

Set these and the CLI never prompts (no keyring, no first-run format question):

```bash
export OPCLI_BASE_URL=https://openproject.example.com
export OPCLI_TOKEN=opapi-xxxxxxxx
openproject wp list -o json
```

`-o json` is the default, but pass it explicitly to be safe. The first-run
format prompt only appears on an interactive TTY, so pipelines are never blocked.

## Spend fewer tokens

- **`--fields`** trims the payload to what you need — dotted paths supported:
  ```bash
  openproject search wp --mine --fields id,subject,status,assignee.name
  ```
- **`--count`** returns just a total instead of rows:
  ```bash
  openproject search wp --project x --overdue --count   # -> {"total": 7, ...}
  ```
- **`--limit N`** caps rows (`--limit 0` = all, paginated for you).

## Don't guess filters — discover them

Instead of hard-coding the OpenProject filter JSON, ask the CLI at runtime:

```bash
openproject search fields              # every field you can filter on (live)
openproject search operators           # what =, o, !*, <>d, ~ mean
openproject search values status       # allowed values for a field
```

Then filter with plain flags or `--where` (no JSON needed):

```bash
openproject search wp --where "status = open" --where "assignee = me" --where "updated > 7d"
```

## Resolve names, not ids

You can pass human names anywhere and they're resolved for you — no need to look
up ids first:

```bash
openproject wp update 42 --status "In progress" --assignee jane.doe --priority High
```

`me` always resolves to the authenticated user.

## Common agent recipes

```bash
# Triage: my overdue work, minimal fields
openproject search mine --overdue --fields id,subject,dueDate

# Create a work package and capture its id
ID=$(openproject wp create "Investigate timeout" --project ops --type Bug \
       --assignee me --priority High | jq -r .id)

# Log time against it
openproject time add 1.5 --work-package "$ID" --activity Development --comment "repro"

# Add a comment without notifying watchers
openproject comment add "$ID" "Root cause found." --no-notify

# Monthly per-person billing report (rates from a file)
openproject cost report --month 2026-07 --rates rates.json

# Anything not wrapped: hit the API directly
openproject raw get work_packages/"$ID"
openproject raw patch work_packages/"$ID" -d '{"lockVersion":3,"subject":"…"}'
```

## Gotchas worth knowing

- **Updating a work package** handles `lockVersion` for you (fetch → patch →
  retry on conflict). With `raw patch` you must send `lockVersion` yourself.
- **Time `hours`** accept decimals (`2.5`) or ISO-8601 (`PT2H30M`).
- **Assignees must be project members** — a brand-new project has none; add one
  with `openproject member add` before assigning.
- **Comments**: `comment add` takes markdown; `comment edit` takes a plain string.
- **Wiki** is read-only metadata over the API (no body text). **Costs**: the API
  has no rates, so `cost report` multiplies hours by a rate table you provide.
- Use `--profile/-p name` to target a specific instance when several are configured.
