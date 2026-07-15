# Using `openproject` from an AI agent

This CLI is built to be driven by an LLM/agent (Claude Code, Cursor, custom tool
loops). This page is the **machine contract** — how to call it reliably and
cheaply. For the human tutorial see [README](README.md); for every option see
[docs/COMMANDS.md](docs/COMMANDS.md).

> **No context? Start here:** run **`openproject guide`** — the CLI ships a
> built-in playbook (output contract, auth, discovery, gotchas, recipes) so an
> agent can bootstrap from the tool alone, with no external docs. Then
> `openproject guide <topic>` (search, wp, time, costs, …) for focused cheat-sheets.

> **Claude Code users:** `openproject install claude` registers a skill so Claude
> auto-invokes the CLI whenever you mention OpenProject.

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
- **`--stream`** emits NDJSON (one object per line) for large result sets, so you
  can process incrementally. **`-o csv`** for spreadsheet-style output.

## Preview writes before doing them

Add **`--dry-run`** to any mutating command: the CLI resolves everything (names →
hrefs, `lockVersion`) and prints the exact request it *would* send, then exits 0
without touching the server. Great for planning a change, then re-running without
the flag to apply it.

```bash
openproject wp update 42 --status Closed --assignee jane.doe --dry-run
# -> {"dryRun": true, "request": {"method": "PATCH", "url": "...", "body": {...}}}
```

## Session context (sticky defaults) — and its caveat

`openproject context` stores **sticky defaults** that are auto-applied to later
commands, so you stop repeating `--project`/`--user`/filters. A CLI has no live
process, so "context" = durable defaults saved in config, not a running session.

```bash
openproject context set --project webshop --assignee me   # set/merge defaults
openproject context show                                   # inspect active defaults
openproject context unset assignee                         # drop one key
openproject context clear                                  # drop all
openproject context save sprint                            # name it
openproject context use sprint   |   openproject context list   # switch / list
```

**How it applies:** for any command with a matching option (`--project`,
`--user`, `--assignee`, `--author`, `--status`, `--priority`, `--query`), the
context value fills it **only when you don't pass that flag**. So with
`context set --project webshop`, `openproject wp list` behaves like
`openproject wp list --project webshop`.

**Caveat for agents — this is implicit state that changes results.** Rules to stay safe:

- **Explicit flags always win** — pass `--project X` to override the context.
- **`--no-context`** ignores the context entirely for one command.
- If output looks wrongly scoped (too few / wrong project), run
  `openproject context show` first, or re-run with `--no-context`.
- Don't assume a fresh environment is context-free — **check `context show`** at
  the start of a task, and prefer being explicit in scripts you don't control.

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

# Focus a whole task on one project, then work without repeating --project
openproject context set --project ops        # ... do work ...   openproject context clear

# Monthly per-person billing report (rates from a file); detailed CSV w/ custom fields
openproject cost report --month 2026-07 --rates rates.json
openproject cost report --month 2026-07 --rates rates.json --detailed -o csv > invoice.csv

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
