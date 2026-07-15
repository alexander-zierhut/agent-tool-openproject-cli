# Command reference

_Auto-generated from the CLI (`python scripts/gen_docs.py`). Every command also accepts the global `--output/-o` (json\|table\|markdown), `--format/-f`, `--fields`, `--profile/-p` and `--no-color` options, usable anywhere on the line._

## Groups

- [`attach`](#attach) — Attachments / file uploads on work packages.
- [`auth`](#auth) — Log in, log out, inspect credentials.
- [`cf`](#cf) — Inspect custom fields / resource schemas.
- [`comment`](#comment) — Add, edit, list work-package comments.
- [`cost`](#cost) — Time & cost reporting per person/project (invoicing).
- [`filelink`](#filelink) — Nextcloud/file-storage links on work packages.
- [`member`](#member) — Project memberships & roles.
- [`notify`](#notify) — In-app notifications.
- [`project`](#project) — Create, list, archive projects.
- [`raw`](#raw) — Escape hatch: call any API endpoint directly.
- [`search`](#search) — Powerful work-package (and global) search.
- [`settings`](#settings) — View & change CLI settings (default output format).
- [`time`](#time) — Log, edit, list time entries + reports.
- [`user`](#user) — Users, groups, memberships, assignable people.
- [`wiki`](#wiki) — Wiki pages (read + write where supported).
- [`wp`](#wp) — Work packages: CRUD, move, assign, watch.

## `attach`

### `openproject attach delete`

Delete an attachment.

**Arguments:** `attachment_id` (required)

| Option | Description |
| --- | --- |
| `--yes`, `-y` | Skip confirmation. |

### `openproject attach download`

Download an attachment's content.

**Arguments:** `attachment_id` (required)

| Option | Description |
| --- | --- |
| `--output`, `-O` | Output path (default: original file name). |

### `openproject attach get`

Show attachment metadata.

**Arguments:** `attachment_id` (required)

### `openproject attach list`

List attachments on a work package.

**Arguments:** `wp_id` (required)

### `openproject attach upload`

Upload a file and attach it to a work package.

**Arguments:** `wp_id` (required), `path` (required)

| Option | Description |
| --- | --- |
| `--name` | Override the stored file name. |
| `--description`, `-d` | Attachment description. |

## `auth`

### `openproject auth login`

Verify and store an API token securely (OS keyring by default).

Non-interactive example:
  openproject auth login --url http://localhost:8090 --token opapi-xxxx

| Option | Description |
| --- | --- |
| `--url`, `-u` | Base URL, e.g. https://op.example.com |
| `--token`, `-t` | API token (prompted if omitted). |
| `--name` | Profile name to store under. |
| `--username` | Informational: the API user's login. |
| `--no-verify-ssl` | Skip TLS verification. |

### `openproject auth logout`

Remove the stored API token for a profile.

| Option | Description |
| --- | --- |
| `--name` | Profile to log out (defaults to active). |

### `openproject auth status`

Show the active profile, credential backend, and connectivity.

### `openproject auth whoami`

Print the authenticated user (GET /users/me).

## `cf`

### `openproject cf project`

List custom fields (project attributes) available on projects.

| Option | Description |
| --- | --- |
| `--all` | Include built-in fields, not just custom. |

### `openproject cf time`

List custom fields available on time entries.

| Option | Description |
| --- | --- |
| `--all` | Include built-in fields, not just custom. |

### `openproject cf wp`

List custom fields available on work packages of a project/type.

| Option | Description |
| --- | --- |
| `--project`, `-P` | Project id/identifier. **(required)** |
| `--type`, `-t` | Work-package type name. |
| `--all` | Include built-in fields, not just custom. |

## `comment`

### `openproject comment add`

Add a comment to a work package.

**Arguments:** `wp_id` (required), `text` (required)

| Option | Description |
| --- | --- |
| `--notify`, `--no-notify` | Send notifications (default off). |

### `openproject comment edit`

Edit an existing comment by its activity id.

**Arguments:** `activity_id` (required), `text` (required)

### `openproject comment list`

List activities/comments for a work package (oldest first).

**Arguments:** `wp_id` (required)

| Option | Description |
| --- | --- |
| `--comments-only`, `--all-activity` | Only entries with a comment. |

## `cost`

### `openproject cost report`

Summarise hours (and billable cost) per person for a period — for invoicing.

| Option | Description |
| --- | --- |
| `--month` | Month YYYY-MM (sets the date range). |
| `--from` | Start date YYYY-MM-DD. |
| `--to` | End date YYYY-MM-DD. |
| `--user`, `-u` | Restrict to one user (login/name/id or 'me'). |
| `--project`, `-P` | Restrict to one project. |
| `--rates` | JSON rate table for billable amounts. |
| `--by-project`, `--no-by-project` | Break each person down by project. |

## `filelink`

### `openproject filelink add`

Link a Nextcloud/storage file to a work package.

**Arguments:** `wp_id` (required)

| Option | Description |
| --- | --- |
| `--storage`, `-s` | Storage id (see `filelink storages`). **(required)** |
| `--file-id` | File id within the storage (Nextcloud fileid). **(required)** |
| `--file-name` | File name to display. **(required)** |
| `--mime` | MIME type (folder: application/x-op-directory). |

### `openproject filelink delete`

Remove a file link.

**Arguments:** `file_link_id` (required)

| Option | Description |
| --- | --- |
| `--yes`, `-y` | Skip confirmation. |

### `openproject filelink get`

Show a single file link.

**Arguments:** `file_link_id` (required)

### `openproject filelink list`

List file links on a work package.

**Arguments:** `wp_id` (required)

### `openproject filelink storages`

List configured file storages (Nextcloud etc.).

## `member`

### `openproject member add`

Add a member to a project with one or more roles.

| Option | Description |
| --- | --- |
| `--project`, `-P` | Project id/identifier. **(required)** |
| `--user`, `-u` | Principal (login/name/id or 'me'). **(required)** |
| `--role`, `-r` | Role name (repeatable). **(required)** |

### `openproject member list`

List memberships.

| Option | Description |
| --- | --- |
| `--project`, `-P` | Filter by project. |
| `--user`, `-u` | Filter by principal (login/name/id). |
| `--limit`, `-n` | Maximum rows (0 = all). |

### `openproject member remove`

Remove a membership.

**Arguments:** `membership_id` (required)

| Option | Description |
| --- | --- |
| `--yes`, `-y` | Skip confirmation. |

### `openproject member roles`

List available roles.

### `openproject member update`

Replace a membership's roles.

**Arguments:** `membership_id` (required)

| Option | Description |
| --- | --- |
| `--role`, `-r` | New role set (repeatable; replaces all). **(required)** |

## `notify`

### `openproject notify count`

Count notifications (total + unread, and optionally today's).

| Option | Description |
| --- | --- |
| `--today` | Also count today's notifications. |
| `--project`, `-P` | Scope counts to a project. |

### `openproject notify get`

Show one notification.

**Arguments:** `notification_id` (required)

### `openproject notify list`

List your in-app notifications (unread by default).

| Option | Description |
| --- | --- |
| `--state` | unread \| read \| all. |
| `--reason` | mentioned, assigned, watched, ... |
| `--project`, `-P` | Filter by project. |
| `--today` | Only notifications created today. |
| `--limit`, `-n` | Maximum rows (0 = all). |

### `openproject notify read`

Mark a notification as read.

**Arguments:** `notification_id` (required)

### `openproject notify read-all`

Mark all notifications as read.

### `openproject notify unread`

Mark a notification as unread.

**Arguments:** `notification_id` (required)

## `project`

### `openproject project archive`

Archive a project (PATCH active=false).

**Arguments:** `project` (required)

### `openproject project create`

Create a project.

**Arguments:** `name` (required)

| Option | Description |
| --- | --- |
| `--identifier` | URL identifier (auto from name if omitted). |
| `--description`, `-d` | Description (markdown). |
| `--parent` | Parent project id/identifier. |
| `--public` | Make the project public. |
| `--custom-fields` | JSON of customFieldN values. |

### `openproject project delete`

Permanently delete a project (asynchronous on the server).

**Arguments:** `project` (required)

| Option | Description |
| --- | --- |
| `--yes`, `-y` | Skip confirmation. |

### `openproject project get`

Show a single project.

**Arguments:** `project` (required)

| Option | Description |
| --- | --- |
| `--raw`, `-r` | Return the full HAL document. |

### `openproject project list`

List projects (active by default include all unless filtered).

| Option | Description |
| --- | --- |
| `--active`, `--archived` | Filter by active state. |
| `--filters` | Raw OpenProject filters JSON (overrides --active). |
| `--sort` | Sort column (e.g. name, id, created_at). |
| `--limit`, `-n` | Maximum rows. |

### `openproject project unarchive`

Restore an archived project (PATCH active=true).

**Arguments:** `project` (required)

### `openproject project update`

Update project attributes (no lockVersion needed for projects).

**Arguments:** `project` (required)

| Option | Description |
| --- | --- |
| `--name` | New name. |
| `--identifier` | New identifier. |
| `--description`, `-d` | New description. |
| `--parent` | New parent id/identifier ('none' to detach). |
| `--public`, `--private` | Public flag. |
| `--custom-fields` | JSON of customFieldN values. |

## `raw`

### `openproject raw delete`

DELETE an endpoint.

**Arguments:** `path` (required)

| Option | Description |
| --- | --- |
| `--param`, `-p` | Query param key=value (repeatable). |

### `openproject raw get`

GET an endpoint.

**Arguments:** `path` (required)

| Option | Description |
| --- | --- |
| `--param`, `-p` | Query param key=value (repeatable). |

### `openproject raw patch`

PATCH an endpoint.

**Arguments:** `path` (required)

| Option | Description |
| --- | --- |
| `--data`, `-d` | JSON request body. |
| `--data-file` | File containing the JSON body. |
| `--param`, `-p` | Query param key=value (repeatable). |

### `openproject raw post`

POST to an endpoint.

**Arguments:** `path` (required)

| Option | Description |
| --- | --- |
| `--data`, `-d` | JSON request body. |
| `--data-file` | File containing the JSON body. |
| `--param`, `-p` | Query param key=value (repeatable). |

## `search`

### `openproject search fields`

List what you can filter/search work packages on (live from the instance).

| Option | Description |
| --- | --- |
| `--project`, `-P` | Show project-specific filters (incl. its custom fields). |

### `openproject search mine`

Open work packages assigned to me.

| Option | Description |
| --- | --- |
| `--project`, `-P` | Restrict to a project. |
| `--all` | Include closed. |
| `--limit`, `-n` |  |

### `openproject search operators`

Explain the filter operator codes.

### `openproject search overdue`

Past-due, still-open work packages.

| Option | Description |
| --- | --- |
| `--project`, `-P` |  |
| `--limit`, `-n` |  |

### `openproject search recent`

Recently updated work packages.

| Option | Description |
| --- | --- |
| `--days`, `-d` | Updated within the last N days. |
| `--project`, `-P` |  |
| `--all`, `--open-only` | Include closed (default yes). |
| `--limit`, `-n` |  |

### `openproject search reported`

Work packages I created (authored).

| Option | Description |
| --- | --- |
| `--project`, `-P` |  |
| `--all` |  |
| `--limit`, `-n` |  |

### `openproject search unassigned`

Open work packages with no assignee.

| Option | Description |
| --- | --- |
| `--project`, `-P` |  |
| `--limit`, `-n` |  |

### `openproject search values`

List the allowed values for a filterable field.

**Arguments:** `field` (required)

| Option | Description |
| --- | --- |
| `--project`, `-P` | Project context (versions, assignees, custom fields). |
| `--limit`, `-n` |  |

### `openproject search watching`

Work packages I watch.

| Option | Description |
| --- | --- |
| `--project`, `-P` |  |
| `--all` |  |
| `--limit`, `-n` |  |

### `openproject search wp`

Search work packages with rich, plain-language filters.

**Arguments:** `text` (optional)

| Option | Description |
| --- | --- |
| `--project`, `-P` | Restrict to a project. |
| `--status`, `-s` | 'open', 'closed', or a status name. |
| `--open` | Only open work packages. |
| `--closed` | Only closed work packages. |
| `--type`, `-t` | Type name. |
| `--priority` | Priority name. |
| `--assignee`, `-a` | Assignee (login/name/id or 'me'). |
| `--mine` | Assigned to me. |
| `--unassigned` | No assignee. |
| `--author`, `--created-by` | Author (login/name/id or 'me'). |
| `--responsible` | Accountable person. |
| `--watching` | Watched by me. |
| `--version` | Target version/milestone (name/id). |
| `--parent` | Children of this work-package id. |
| `--id` | Specific ids, comma-separated. |
| `--subject` | Subject contains (LIKE). |
| `--created-since` | Created on/after (date or 7d/2w/today). |
| `--created-before` | Created before (date or spec). |
| `--updated-since` | Updated on/after (date or spec). |
| `--due-before` | Due on/before (date or spec). |
| `--due-after` | Due on/after (date or spec). |
| `--overdue` | Past due and still open. |
| `--start-after` | Starts on/after. |
| `--start-before` | Starts on/before. |
| `--where`, `-w` | Expression e.g. "status = open" (repeatable). |
| `--filters` | Raw OpenProject filters JSON (overrides everything). |
| `--all` | Include closed work packages. |
| `--sort` | Sort field. |
| `--asc` | Ascending (default descending). |
| `--group-by` | Group column (status/type/assignee/project/priority). |
| `--limit`, `-n` | Maximum rows (0 = all). |
| `--count` | Return only the total match count. |
| `--raw`, `-r` | Return raw HAL elements. |

## `settings`

### `openproject settings get-format`

Print the effective default format.

### `openproject settings path`

Print the config file path.

### `openproject settings set-format`

Set the default output format used when no --format/-o is given.

**Arguments:** `fmt` (required)

### `openproject settings show`

Show current settings (default format, active profile, config location).

## `time`

### `openproject time activities`

List available time-entry activities (Development, Management, ...).

| Option | Description |
| --- | --- |
| `--project`, `-P` | Project context (activities can be project-scoped). |

### `openproject time add`

Log a time entry against a work package or project.

**Arguments:** `hours` (required)

| Option | Description |
| --- | --- |
| `--work-package`, `-w` | Work package id to log against. |
| `--project`, `-P` | Project id/identifier (if not logging on a WP). |
| `--date` | Date YYYY-MM-DD (default today). |
| `--activity` | Activity name (e.g. Development). |
| `--comment`, `-m` | Comment. |
| `--user`, `-u` | Log on behalf of another user (needs permission). |

### `openproject time delete`

Delete a time entry.

**Arguments:** `entry_id` (required)

| Option | Description |
| --- | --- |
| `--yes`, `-y` | Skip confirmation. |

### `openproject time edit`

Edit a time entry (partial; no lockVersion).

**Arguments:** `entry_id` (required)

| Option | Description |
| --- | --- |
| `--hours` | New hours (decimal or ISO8601). |
| `--date` | New date YYYY-MM-DD. |
| `--activity` | New activity name. |
| `--comment`, `-m` | New comment. |

### `openproject time get`

Show a single time entry.

**Arguments:** `entry_id` (required)

### `openproject time list`

List time entries with filters (per person / project / work package).

| Option | Description |
| --- | --- |
| `--user`, `-u` | Filter by user (login/name/id or 'me'). |
| `--project`, `-P` | Filter by project. |
| `--work-package`, `-w` | Filter by work package id. |
| `--from` | Start date (YYYY-MM-DD). |
| `--to` | End date (YYYY-MM-DD). |
| `--month` | Convenience month filter YYYY-MM. |
| `--limit`, `-n` | Maximum rows (0 = all). |

## `user`

### `openproject user available`

List users assignable within a project (available assignees).

**Arguments:** `project` (required)

### `openproject user create`

Create a user (requires admin).

**Arguments:** `login` (required)

| Option | Description |
| --- | --- |
| `--email`, `-e` | Email address. **(required)** |
| `--first-name` | First name. **(required)** |
| `--last-name` | Last name. **(required)** |
| `--password` | Initial password (else invite/status). |
| `--status` | active \| invited \| registered. |
| `--admin` | Grant admin. |

### `openproject user get`

Show a single user.

**Arguments:** `user` (required)

| Option | Description |
| --- | --- |
| `--raw`, `-r` | Return the full HAL document. |

### `openproject user groups`

List groups.

### `openproject user list`

List users (requires admin permission on most instances).

| Option | Description |
| --- | --- |
| `--status` | Filter by status (active, locked, invited...). |
| `--name` | Name/login substring filter. |
| `--limit`, `-n` | Maximum rows (0 = all). |

### `openproject user me`

Show the authenticated user.

## `wiki`

### `openproject wiki attachments`

List attachments on a wiki page.

**Arguments:** `page_id` (required)

### `openproject wiki get`

Show wiki page metadata (id + title only; body is not exposed by the API).

**Arguments:** `page_id` (required)

| Option | Description |
| --- | --- |
| `--raw`, `-r` | Return the full HAL document. |

## `wp`

### `openproject wp assign`

Set (or clear with 'none') the assignee.

**Arguments:** `wp_id` (required), `user` (required)

### `openproject wp assignees`

List users assignable to this work package.

**Arguments:** `wp_id` (required)

### `openproject wp create`

Create a work package.

**Arguments:** `subject` (required)

| Option | Description |
| --- | --- |
| `--project`, `-P` | Project id/identifier. **(required)** |
| `--type`, `-t` | Type name (default Task). |
| `--description`, `-d` | Description (markdown). |
| `--status`, `-s` | Initial status name. |
| `--priority` | Priority name. |
| `--assignee`, `-a` | Assignee (login/name/id or 'me'). |
| `--responsible` | Accountable user. |
| `--parent` | Parent work package id. |
| `--start-date` | YYYY-MM-DD. |
| `--due-date` | YYYY-MM-DD. |
| `--estimated` | Estimated time (hours or ISO8601). |
| `--custom-fields` | JSON of customFieldN values. |
| `--set` | Raw JSON merged into the create body. |
| `--notify` | Send notifications for this create. |

### `openproject wp delete`

Delete a work package.

**Arguments:** `wp_id` (required)

| Option | Description |
| --- | --- |
| `--yes`, `-y` | Skip confirmation. |

### `openproject wp get`

Show one work package.

**Arguments:** `wp_id` (required)

| Option | Description |
| --- | --- |
| `--raw`, `-r` | Return the full HAL document. |

### `openproject wp list`

List / filter work packages (global, scoped by filters). See `search wp` for the full set.

| Option | Description |
| --- | --- |
| `--project`, `-P` | Project id/identifier. |
| `--status`, `-s` | 'open', 'closed', or a status name. |
| `--type`, `-t` | Work-package type name. |
| `--assignee`, `-a` | Assignee (login/name/id or 'me'). |
| `--mine` | Assigned to me. |
| `--unassigned` | No assignee. |
| `--author`, `--created-by` | Author (login/name/id or 'me'). |
| `--priority` | Priority name. |
| `--version` | Target version (name/id). |
| `--overdue` | Past due and still open. |
| `--updated-since` | Updated since (date or 7d/today). |
| `--due-before` | Due on/before (date or spec). |
| `--query`, `-q` | Full-text search (subject/description/comments). |
| `--where`, `-w` | Expression filter, e.g. "status = open" (repeatable). |
| `--all` | Include closed (disable default open filter). |
| `--sort` | Sort field, e.g. id, updatedAt, dueDate. |
| `--desc` | Sort descending. |
| `--limit`, `-n` | Maximum rows (0 = all). |

### `openproject wp move`

Move a work package to another project.

**Arguments:** `wp_id` (required), `project` (required)

| Option | Description |
| --- | --- |
| `--type`, `-t` | New type (if not valid in target project). |

### `openproject wp schema`

Discover the create schema (fields, required flags, custom fields) via the form.

| Option | Description |
| --- | --- |
| `--project`, `-P` | Project id/identifier. **(required)** |
| `--type`, `-t` | Type name. |

### `openproject wp unassign`

Remove the assignee.

**Arguments:** `wp_id` (required)

### `openproject wp unwatch`

Remove a watcher.

**Arguments:** `wp_id` (required), `user` (optional)

### `openproject wp update`

Update a work package (lockVersion handled automatically).

**Arguments:** `wp_id` (required)

| Option | Description |
| --- | --- |
| `--subject` | New subject. |
| `--description`, `-d` | New description. |
| `--status`, `-s` | New status name. |
| `--type`, `-t` | New type name. |
| `--priority` | New priority. |
| `--assignee`, `-a` | Assignee ('none' to clear). |
| `--responsible` | Accountable ('none' to clear). |
| `--parent` | Parent id ('none' to detach). |
| `--start-date` | YYYY-MM-DD. |
| `--due-date` | YYYY-MM-DD. |
| `--estimated` | Estimated time (hours or ISO8601). |
| `--done-ratio` | Percentage done 0-100. |
| `--custom-fields` | JSON of customFieldN values. |
| `--set` | Raw JSON merged into the patch body. |
| `--notify` | Send notifications for this change. |

### `openproject wp watch`

Add a watcher (note: body key is 'user', not under _links).

**Arguments:** `wp_id` (required), `user` (optional)

### `openproject wp watchers`

List watchers of a work package.

**Arguments:** `wp_id` (required)

