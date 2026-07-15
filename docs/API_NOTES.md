# OpenProject API v3 — implementation notes

_Distilled from automated research (12 agents). Verify specifics against the live instance._


---

# AREA: Authentication & tokens (OpenProject API v3, HAL+JSON)

**Auth:** OpenProject APIv3 accepts four auth mechanisms; for a CLI, HTTP Basic with an API key is the primary, simplest path. (1) API KEY via HTTP BASIC: username is the literal string "apikey" (NOT the user's login) and the password is the user's personal API token (format "opapi-<40 hex chars>", e.g. opapi-2519132cdf62dcf5a66fd96394672079f9e9cad1). curl: `curl -u apikey:$API_KEY https://host/api/v3/...`. The login credentials themselves never work against the API. (2) The SAME token can be sent as a BEARER token: `Authorization: Bearer <token>` (works for both personal API tokens and OIDC/JWT access tokens). (3) OAuth2 (authorization_code, authorization_code+PKCE, client_credentials) against /oauth/authorize and /oauth/token, scope defaults to `api_v3`. (4) SESSION/cookie auth works ONLY same-origin (enforced via the `Sec-Fetch-Site` header) — not usable from a CLI. Basic-auth for APIv3 is gated by the instance setting `apiv3_enable_basic_auth` (default: true). ANONYMOUS: if the instance does not force authentication, unauthenticated requests get anonymous-user permissions; if it does force auth, every request without valid credentials returns HTTP 401. Recommended CLI approach: store the API token, send Basic auth (apikey:token) on every request; verify credentials by calling GET /api/v3/users/me.

## Endpoints

### GET /api/v3/users/me
Return the currently authenticated user (the account behind the credentials). Ideal for a login/whoami/credential-check command.
- **req:** No body/params. 'me' is an alias for the current user id, resolved by the same handler as GET /api/v3/users/{id}. Requires valid credentials; with anonymous access it returns the anonymous user (or 401 if the instance forces auth).
- **res:** HAL+JSON User resource. Fields: id, login, firstName, lastName, name, email, admin (bool), avatar, status, language, createdAt, updatedAt, identityUrl (deprecated). _links include self, memberships, showUser, lock/unlock (admin), updateImmediately. For /me your own login/name/language/timestamps are always visible.

### GET /api/v3/users/{id}
View a single user by numeric id (or the string 'me').
- **req:** id accepts an integer or 'me'. Viewing arbitrary users needs permission; some fields are privacy-restricted unless admin or self.
- **res:** HAL+JSON User resource (same shape as /me).

### GET /api/v3/users
List users (for admin/user-management CLI subcommands).
- **req:** Requires manage_user (admin) permission. Supports pagination (offset, pageSize) and JSON 'filters' query param (e.g. filter by status, login, name, group).
- **res:** HAL collection: _embedded.elements[] of User, plus total, count, pageSize, offset, and _links.self/next/prev paging.

### POST /oauth/token
OAuth2 token endpoint - exchange an authorization code (or client_credentials/refresh_token) for an access token.
- **req:** POST body with grant_type (authorization_code | client_credentials | refresh_token), client_id, client_secret (unless PKCE public client), code, redirect_uri (must match the /oauth/authorize one), and for PKCE code_verifier. Lives at app root /oauth/token, NOT under /api/v3.
- **res:** JSON: access_token, token_type='bearer', expires_in, refresh_token, scope (e.g. 'api_v3', or 'bcf_v2_1' on BIM edition). Use access_token as Authorization: Bearer against /api/v3.

### GET /oauth/authorize
OAuth2 authorization endpoint - obtain an authorization code (interactive/browser step).
- **req:** Query params: response_type=code, client_id, redirect_uri, scope (defaults to api_v3 if omitted), state, and for PKCE code_challenge + code_challenge_method=S256. For headless/desktop use redirect_uri=urn:ietf:wg:oauth:2.0:oob to display the code. Requires a registered OAuth application (client_id/client_secret created under Administration -> Authentication -> OAuth applications).
- **res:** Redirects to redirect_uri with ?code=<auth_code>&state=..., or displays the code (oob).

## Gotchas
- Basic-auth username is the fixed literal 'apikey' - not the login. Password = the API token. Passing the real login/password fails.
- The API token string already encodes the identity; the login is never sent or used with Basic auth.
- Only ONE API token can exist per user at a time. Generating/resetting a new one immediately invalidates the previous token.
- The plaintext token is shown to the user (or returned by Token::API#plain_value) EXACTLY ONCE at creation. The DB stores only an HMAC-SHA256 hash (HMAC over Setting.hashed_token_pepper), so a lost token cannot be recovered - it must be regenerated.
- Basic auth for APIv3 can be turned off by admins: apiv3_enable_basic_auth=false (env OPENPROJECT_APIV3__ENABLE__BASIC__AUTH=false). Default is true. If disabled, use Bearer token or OAuth2.
- Session/cookie auth is same-origin ONLY (guarded by the Sec-Fetch-Site request header) - unusable from a CLI/server-to-server context.
- If the instance forces authentication on all requests (login_required), any request lacking valid credentials returns HTTP 401 with WWW-Authenticate. Otherwise you silently act as the anonymous user - check /api/v3/users/me to detect whether you are actually authenticated.
- OAuth /oauth/authorize and /oauth/token live at the application root, NOT under /api/v3.
- The token model is Token::API (prefix :opapi), inheriting Token::Named -> hashed token base; the visible value is 'opapi-' + 40 hex chars.
- Admins can also globally disable users creating personal API tokens via Administration -> API and webhooks; if disabled, users won't have a Generate option under /my/access_token.

## Examples
```
# Verify credentials / whoami (HTTP Basic, username is literally 'apikey')
API_KEY=opapi-2519132cdf62dcf5a66fd96394672079f9e9cad1
curl -u apikey:$API_KEY https://community.openproject.org/api/v3/users/me
```
```
# Same request using the token as a Bearer token instead of Basic
curl -H "Authorization: Bearer $API_KEY" https://community.openproject.org/api/v3/users/me
```
```
# Manual Basic header (base64 of 'apikey:<token>')
curl -H "Authorization: Basic $(printf 'apikey:%s' "$API_KEY" | base64)" https://community.openproject.org/api/v3/users/me
```
```
# Python (requests) - Basic auth for every call
import requests
AUTH = ('apikey', 'opapi-...')
r = requests.get('https://host/api/v3/users/me', auth=AUTH)
r.raise_for_status(); me = r.json()  # HAL User resource
```
```
# Rails console: create an API token for a user and print the plaintext ONCE
# packaged:  sudo openproject run console
# docker:    docker compose run --rm web bundle exec rails console
user = User.find_by(login: 'admin')
token = Token::API.create!(user: user)
puts token.plain_value   # => opapi-...  (only on this in-memory object)
```
```
# One-liner via runner (no interactive console)
sudo openproject run runner "puts Token::API.create!(user: User.find_by(login: 'admin')).plain_value"
```
```
# OAuth2 code exchange
curl -X POST https://host/oauth/token -d grant_type=authorization_code -d client_id=$CLIENT_ID -d client_secret=$CLIENT_SECRET -d code=$AUTH_CODE -d redirect_uri='urn:ietf:wg:oauth:2.0:oob'
# -> {"access_token":"...","token_type":"bearer","expires_in":7200,"refresh_token":"...","scope":"api_v3"}
```

## Open questions (verify live)
- Confirm the exact UI path for generating the personal API token on the live instance - historically /my/access_token (My account -> Access token -> 'API' row -> Generate/Reset). Verify it renders the token exactly once.
- Confirm whether the target instance has apiv3_enable_basic_auth enabled (default true) and whether personal API token creation is enabled under Administration -> API and webhooks - either could break Basic-auth CLI login.
- Verify current token expiry: personal Token::API tokens are effectively non-expiring, but confirm no max-token-lifetime setting is enforced.
- Verify whether creating a new Token::API via console auto-deletes the user's prior API token (single-token-per-user) on the running version, so the CLI 'reset' semantics match.
- Confirm exact OAuth scope strings accepted (api_v3 default; bcf_v2_1 only on BIM/enterprise) and whether client_credentials requires binding to an impersonation user.
- Confirm whether the instance forces authentication on all requests (login_required) - determines whether anonymous requests 401 or fall back to the anonymous user.


---

# AREA: Work Packages: CRUD, form/schema, move, relations, parent/child, watchers, assignee/responsible

**Auth:** All work-package endpoints require authentication. Simplest for a CLI: HTTP Basic auth with username literally "apikey" and password = the user's API token (My account > Access tokens > API). E.g. `curl -u apikey:<TOKEN>`. OAuth2 Bearer and session cookies also work. Every write (POST/PATCH) must send header `Content-Type: application/json`. Permissions are per-project: creating/editing needs "add/edit work packages"; `spentTime`, `watchers`, `ancestors` etc. are gated by view permissions and simply won't appear in `_links`/`_embedded` if you lack them. Missing permission -> 403; unauthenticated -> 401.

## Endpoints

### GET /api/v3/work_packages
List/search all work packages the user can see (global, across projects). Preferred over the per-project variant.
- **req:** Query params: offset (page number, 1-based, default 1), pageSize (default 20; instance max often 100/200), filters (URL-encoded JSON, see gotchas), sortBy (URL-encoded JSON e.g. [["id","asc"]]), groupBy, showSums (bool), select (comma list to trim payload, e.g. select=total,elements/id,elements/subject,elements/_links/status). To scope to one project use a filter instead of the per-project path: filters=[{"project":{"operator":"=","values":["5"]}}] (values are string IDs).
- **res:** HAL Collection: {_type:"WorkPackageCollection", total, count, pageSize, offset, _embedded:{elements:[<WorkPackage>...]}, _links:{self, nextByOffset?, prevByOffset?, jumpTo(templated), changeSize(templated)}}. Iterate pages until offset*pageSize >= total, or follow _links.nextByOffset.href. Each element carries lockVersion, id, subject, description, and _links (self, project, type, status, priority, assignee, responsible, parent, author, ...).

### GET /api/v3/projects/{id}/work_packages
List work packages within one project. DEPRECATED but still functional; prefer the global endpoint + project filter.
- **req:** {id} is the project numeric id or identifier. Same offset/pageSize/filters/sortBy params as the global list.
- **res:** Same WorkPackageCollection shape as the global list.

### GET /api/v3/work_packages/{id}
Fetch one work package. Use this to read the current lockVersion before any PATCH.
- **req:** {id} = numeric work package id. No required params.
- **res:** Single WorkPackage resource. Key writable-relevant fields: subject (string 1-255), description {format,raw,html}, startDate, dueDate, estimatedTime (ISO8601 duration e.g. "PT2H"), percentageDone, scheduleManually. lockVersion (int) is at the top level. _links holds self, project, type, status, priority, assignee, responsible, parent, author(read-only), children[](read-only), ancestors[](read-only), watch/unwatch(templated actions), addWatcher, addRelation, addComment, update(the form URL), updateImmediately(PATCH URL), delete. Read-only derived fields: derivedStartDate, derivedDueDate, derivedEstimatedTime, derivedPercentageDone, spentTime.

### POST /api/v3/work_packages/form
Validate a proposed create payload and DISCOVER the schema (required fields, allowed values/allowedValues links) WITHOUT persisting. Recommended first step before create.
- **req:** Send a partial or full create body (same shape as the real create). Must include at least _links.project so the server can resolve project-specific schema (allowed types/statuses/categories). Body example: {"_links":{"project":{"href":"/api/v3/projects/1"},"type":{"href":"/api/v3/types/1"}},"subject":"Draft"}. Accepts ?notify but it's irrelevant here (nothing saved).
- **res:** Returns _type:"Form" with _embedded.payload (the normalized body you can post to create verbatim, includes a computed lockVersion for creates), _embedded.schema (per-field: required(bool), writable(bool), and _links.allowedValues or a link to the allowed-values collection), and _embedded.validationErrors (a MAP keyed by field name -> Error resource; empty {} means valid). _links.validate (POST, re-run form) and _links.commit (POST, the create URL) are present; commit link is ONLY present when validationErrors is empty. Always 200 even when there are validation errors (errors live in the body, not the HTTP status).

### POST /api/v3/work_packages
Create a work package (global endpoint; project is specified inside the body).
- **req:** Required: subject (root-level string) and _links.project. In practice also supply _links.type; status defaults to the project/type default if omitted (you CAN send _links.status). CRITICAL: every resource reference goes inside _links as {"href":"/api/v3/.../{id}"} — NOT at the root. description is a formattable object; on write send only {"raw":"markdown text"} (server fills html; format defaults to the instance setting, usually "markdown"). Optional query param ?notify=false to suppress email notifications. Example body: {"subject":"My task","description":{"raw":"Details in **markdown**"},"_links":{"type":{"href":"/api/v3/types/1"},"status":{"href":"/api/v3/statuses/1"},"project":{"href":"/api/v3/projects/1"},"priority":{"href":"/api/v3/priorities/8"},"assignee":{"href":"/api/v3/users/42"},"parent":{"href":"/api/v3/work_packages/100"}}}
- **res:** 201 Created with the full WorkPackage (includes new id and lockVersion=0). 422 with a single Error (or _embedded.errors array for multiple) on validation failure — inspect the Error resource's message and _embedded.details._links to find the offending property. 403 if lacking add permission.

### POST /api/v3/projects/{id}/work_packages
Create within a project (DEPRECATED). Project is implied by the URL so _links.project may be omitted.
- **req:** Same body as global create minus the mandatory _links.project. Prefer the global endpoint for new code.
- **res:** 201 Created WorkPackage, same as global create.

### POST /api/v3/work_packages/{id}/form
Validate a proposed UPDATE to an existing work package and inspect the schema for its current project/type (e.g. to check which statuses are reachable, or whether a target project is valid before a move).
- **req:** Send the same partial body you intend to PATCH, INCLUDING the current lockVersion. Use this to pre-validate a project move: post {"lockVersion":N,"_links":{"project":{"href":"/api/v3/projects/9"}}} and read validationErrors + the refreshed schema (allowed types/statuses in the target project).
- **res:** Form resource with _embedded.payload/schema/validationErrors and _links.commit (the PATCH URL) present only when valid. Does not persist.

### PATCH /api/v3/work_packages/{id}
Update fields, move to another project, set parent/assignee/responsible/status, etc. Send only the fields you change.
- **req:** REQUIRES top-level lockVersion equal to the current server value — read it via GET first. Scalars at root (subject, description{raw}, startDate, dueDate, estimatedTime, percentageDone, scheduleManually); resource refs inside _links. Setting a link to null clears it, e.g. {"lockVersion":3,"_links":{"assignee":{"href":null}}}. Optional ?notify=false. Examples — edit: {"lockVersion":3,"subject":"New subject","description":{"raw":"updated"}}; set assignee+responsible: {"lockVersion":3,"_links":{"assignee":{"href":"/api/v3/users/42"},"responsible":{"href":"/api/v3/users/15"}}}; set parent: {"lockVersion":3,"_links":{"parent":{"href":"/api/v3/work_packages/100"}}}; change status: {"lockVersion":3,"_links":{"status":{"href":"/api/v3/statuses/12"}}}.
- **res:** 200 OK with the updated WorkPackage; its lockVersion is incremented by 1 (capture it for the next PATCH). 409 Conflict if lockVersion is stale — on 409 the CLI should re-GET, re-apply changes onto the fresh lockVersion, and retry. 422 for validation errors (e.g. status transition not allowed, type invalid in target project). 403 for permission.

### PATCH /api/v3/work_packages/{id}
MOVE a work package to a different project (special case of update).
- **req:** Body: {"lockVersion":N,"_links":{"project":{"href":"/api/v3/projects/{targetId}"}}}. Because type/status/category/version/assignee may not exist in the target project, a move can 422. Robust flow: POST to /work_packages/{id}/form with the new project first, read schema for allowed type/status, then include corrected _links.type / _links.status / _links.category (or set stale ones to {"href":null}) in the same PATCH. Children move with their parent automatically.
- **res:** 200 OK moved WorkPackage. 422 if a referenced type/status/category/version is invalid in the destination — the Error details name the property to fix.

### DELETE /api/v3/work_packages/{id}
Delete a work package (and, recursively, its descendants).
- **req:** No body. No lockVersion required. Deleting a parent deletes its whole subtree — warn the user.
- **res:** 204 No Content on success. 403 without delete permission; 404 if already gone.

### GET /api/v3/work_packages/{id}/relations
List relations where this work package is one endpoint.
- **req:** No required params. There is also a global GET /api/v3/relations?filters=... for cross-cutting queries.
- **res:** Collection of Relation resources; each has id, name, type, reverseType, lag, description, and _links.from / _links.to (each an href to a work package).

### POST /api/v3/work_packages/{id}/relations
Create a relation FROM this work package TO another.
- **req:** from is implied by the URL {id}; body supplies only to. Body: {"type":"follows","_links":{"to":{"href":"/api/v3/work_packages/78"}}}. Optional lag (int days >=0, only meaningful for precedes/follows) and description. Valid type values: relates, duplicates, duplicated, blocks, blocked, precedes, follows, includes, partof, requires, required. (Parent/child is NOT a relation here — set it via _links.parent on the work package.)
- **res:** 201 Created Relation. 422 if the relation would create a cycle or is otherwise invalid; 404 if the target work package id doesn't exist / isn't visible.

### GET /api/v3/work_packages/{id}/watchers
List users watching the work package.
- **req:** Requires view-watchers permission; otherwise the watchers link is absent on the WP. Companion: GET /api/v3/work_packages/{id}/available_watchers for addable users.
- **res:** Collection of User resources in _embedded.elements.

### POST /api/v3/work_packages/{id}/watchers
Add a watcher.
- **req:** Body MUST wrap the user in a `user` object: {"user":{"href":"/api/v3/users/23"}}. (Note: this is one of the few write bodies where the reference key is `user` at root, not under _links.)
- **res:** 201 Created, returns the added User resource. Idempotent-ish: re-adding an existing watcher is harmless.

### DELETE /api/v3/work_packages/{id}/watchers/{user_id}
Remove a watcher.
- **req:** {user_id} is the numeric user id (not a full href). No body.
- **res:** 204 No Content.

### GET /api/v3/work_packages/{id}/available_assignees
Discover valid values for _links.assignee (and, in practice, responsible) — the users assignable in this WP's project.
- **req:** Use the returned user hrefs directly in _links.assignee / _links.responsible on create/update. (Some versions also expose /available_responsibles; the schema/form allowedValues links are the authoritative source.)
- **res:** Collection of User (and possibly Group/Placeholder) resources.

## Gotchas
- lockVersion is mandatory on every PATCH and must equal the server's current value. It starts at 0 on create and increments by 1 on each successful update. A stale value returns 409 Conflict — implement a re-GET-and-retry loop in the CLI.
- All resource references (project, type, status, priority, assignee, responsible, parent, category, version) MUST be nested inside _links as {"href":"/api/v3/<resource>/<id>"}. Putting them at the root (e.g. "type":{...}) is a common mistake and will be ignored/rejected. Only scalars (subject, description, dates, percentageDone, estimatedTime) go at the root.
- description (and other formattable text) is an object {format, raw, html}. On WRITE send only {"raw":"..."}; the server computes html. format is instance-wide (usually "markdown", older instances "textile") — don't hardcode assumptions; read it from the schema.
- filters is a URL-encoded JSON array: [{"<name>":{"operator":"<op>","values":[".."]}}]. values are almost always arrays of STRINGS (even numeric ids). Multiple filter objects are AND-ed; there is no OR. Operators that take no operand (o=open, c=closed, *=not null, !*=null, t=today, w=this week) still need the key with values:null or an empty/ignored array. Common ids: status, project, type, assignee, responsible, subject, subjectOrId, updatedAt, createdAt. Booleans use ["t"]/["f"].
- Full operator set: = (equals one of), ! (not one of), ~ (contains words, LIKE), !~ (not contains), ** (full-text across string attrs), &= (contains all), * (not null), !* (is null), o (open status), c (closed status), >= / <= (numeric), and date operators t (today), w (this week), t- / t+ (exactly N days past/future), <t- >t- <t+ >t+ (relative day windows), =d (on ISO date), <>d (between two ISO dates in values array).
- The per-project list/create/form paths (/api/v3/projects/{id}/work_packages[...]) are DEPRECATED. Prefer the global /api/v3/work_packages with a project filter (list) or _links.project in the body (create).
- Moving across projects can fail (422) because the current type/status/category/version/assignee may be invalid in the target project. Pre-validate with POST /work_packages/{id}/form including the new project, then send corrected links (or null them) in the same PATCH.
- Parent/child hierarchy is set via _links.parent on the work package (create or PATCH), NOT via the relations endpoint. children and ancestors are read-only.
- Watchers add-body is the odd one out: {"user":{"href":...}} with the ref under `user` at the root, while delete uses a bare numeric {user_id} in the path.
- The form endpoint always returns HTTP 200 even when invalid — validation state lives in _embedded.validationErrors (a map; empty {} = valid) and the presence/absence of _links.commit. Don't rely on the status code there.
- Default pageSize is small (often 20) and there is a max cap; for full syncs, loop pages using offset until offset*pageSize >= total (or follow _links.nextByOffset). Use the select param to shrink large collection payloads.
- estimatedTime and remainingTime are ISO 8601 durations (e.g. "PT2H30M"), not numbers. Dates are plain "YYYY-MM-DD" strings.
- Use ?notify=false on create/PATCH to avoid spamming assignees/watchers during bulk CLI operations (default notify=true).

## Examples
```
# List open work packages in project 5, page 2, 50 per page
curl -u apikey:$TOKEN \
  'https://op.example.com/api/v3/work_packages?offset=2&pageSize=50&filters=%5B%7B%22project%22%3A%7B%22operator%22%3A%22%3D%22%2C%22values%22%3A%5B%225%22%5D%7D%7D%2C%7B%22status%22%3A%7B%22operator%22%3A%22o%22%7D%7D%5D'
# decoded filters: [{"project":{"operator":"=","values":["5"]}},{"status":{"operator":"o"}}]
```
```
# Step 1 - validate + discover schema before creating
curl -u apikey:$TOKEN -H 'Content-Type: application/json' \
  -X POST https://op.example.com/api/v3/work_packages/form \
  -d '{"subject":"Build CLI","_links":{"project":{"href":"/api/v3/projects/1"},"type":{"href":"/api/v3/types/1"}}}'
# -> read _embedded.validationErrors (must be {}), then POST the _embedded.payload to _links.commit.href
```
```
# Step 2 - create
curl -u apikey:$TOKEN -H 'Content-Type: application/json' \
  -X POST 'https://op.example.com/api/v3/work_packages?notify=false' \
  -d '{"subject":"Build CLI","description":{"raw":"Ship the **openproject** CLI"},"_links":{"type":{"href":"/api/v3/types/1"},"status":{"href":"/api/v3/statuses/1"},"project":{"href":"/api/v3/projects/1"},"priority":{"href":"/api/v3/priorities/8"},"assignee":{"href":"/api/v3/users/42"}}}'
```
```
# Update subject + status (must include current lockVersion, from a prior GET)
curl -u apikey:$TOKEN -H 'Content-Type: application/json' \
  -X PATCH https://op.example.com/api/v3/work_packages/1234 \
  -d '{"lockVersion":3,"subject":"Renamed","_links":{"status":{"href":"/api/v3/statuses/12"}}}'
```
```
# Move WP 1234 to project 9
curl -u apikey:$TOKEN -H 'Content-Type: application/json' \
  -X PATCH https://op.example.com/api/v3/work_packages/1234 \
  -d '{"lockVersion":4,"_links":{"project":{"href":"/api/v3/projects/9"}}}'
```
```
# Clear the assignee (set link href to null)
curl -u apikey:$TOKEN -H 'Content-Type: application/json' \
  -X PATCH https://op.example.com/api/v3/work_packages/1234 \
  -d '{"lockVersion":5,"_links":{"assignee":{"href":null}}}'
```
```
# Add a 'follows' relation from 1234 to 78 with 2 days lag
curl -u apikey:$TOKEN -H 'Content-Type: application/json' \
  -X POST https://op.example.com/api/v3/work_packages/1234/relations \
  -d '{"type":"follows","lag":2,"_links":{"to":{"href":"/api/v3/work_packages/78"}}}'
```
```
# Add watcher user 23, then remove
curl -u apikey:$TOKEN -H 'Content-Type: application/json' -X POST \
  https://op.example.com/api/v3/work_packages/1234/watchers -d '{"user":{"href":"/api/v3/users/23"}}'
curl -u apikey:$TOKEN -X DELETE https://op.example.com/api/v3/work_packages/1234/watchers/23
```
```
# Delete
curl -u apikey:$TOKEN -X DELETE https://op.example.com/api/v3/work_packages/1234   # -> 204
```

## Open questions (verify live)
- Is _links.status truly optional on create (defaulting to the project/type default status) on the target instance, or must it be sent? Verify by POSTing to the form and checking schema.status.required.
- Exact allowed relation `type` enum on the installed version (older versions lacked includes/partof/requires/required). Confirm via GET /api/v3/work_packages/{id}/relations schema or by trial POST.
- Whether a global POST /api/v3/relations (with both from and to in _links) is accepted, or only the nested /work_packages/{id}/relations form — docs show the nested form; verify on the live instance.
- description.format value on this instance ("markdown" vs "textile") — read it from a work package or the form schema rather than assuming.
- Instance pageSize maximum (100 vs 200 vs configurable) for tuning bulk pagination.
- Confirm the available-values endpoint name for responsible (some versions expose /available_responsibles, others only surface allowedValues via the form schema).
- Whether moving a WP with children across projects re-parents/keeps the subtree and how invalid category/version in the target are reported — validate with the form endpoint before PATCH.


---

# AREA: Search & filtering for work packages (OpenProject API v3, HAL+JSON)

**Auth:** No special auth for this area — standard API v3 auth applies. Use HTTP Basic with username `apikey` and the user's API token (base64 of `apikey:<TOKEN>`), or OAuth2 Bearer, or a session cookie. All GET list/filter endpoints require the token to have read permission on the relevant projects; results are automatically scoped to what the authenticated user may see. Saving/updating/deleting queries and starring require the "save queries" / "manage public queries" permissions. Global (cross-project) listing at /api/v3/work_packages returns only work packages from projects the user can access.

## Endpoints

### GET /api/v3/work_packages
Global (cross-project) list + filter of work packages. THE primary search endpoint.
- **req:** All query params are optional. filters (URL-encoded JSON array; see gotchas for the format & operator list). sortBy (URL-encoded JSON array of [field,dir] pairs, default [["id","asc"]]). groupBy (single column string, e.g. status, type, assignee, priority, project). pageSize (int, elements per page). offset (int, 1-based PAGE number, NOT a row offset; default 1). showSums (bool, default false). select (comma list for sparse fieldset, e.g. total,elements/subject,elements/id,self). timestamps (Enterprise baseline compare, ISO8601 / relative like PT0S / keyword oneDayAgo@HH:MM+HH:MM; default PT0S). IMPORTANT: if you omit filters entirely, the server applies the DEFAULT filter [{"status_id":{"operator":"o","values":null}}] (only OPEN work packages). To get everything, send filters=[] (encoded %5B%5D).
- **res:** _type: WorkPackageCollection. Top-level: total (matching count across all pages), count (in this page), pageSize, offset. _embedded.elements = array of WorkPackage HAL resources. _links: self, and templated jumpTo {?offset}, changeSize {?pageSize}; when applicable nextByOffset, previousByOffset, and createWorkPackage/createWorkPackageImmediately. groupBy adds _embedded.groups (with count/sums per group); showSums adds a sumsSchema/sums.

### GET /api/v3/projects/{project_id}/work_packages
Project-scoped list + filter (same semantics as global, implicitly limited to one project).
- **req:** Identical query params (filters, sortBy, groupBy, pageSize, offset, showSums, select, timestamps). You do NOT need to add a project filter — the path scopes it. Useful when you already know the project id/identifier.
- **res:** Same WorkPackageCollection shape. _links.createWorkPackage is present here (project context known).

### GET /api/v3/queries
List saved queries (does NOT embed work-package results).
- **req:** Optional filters param supports: project_id (e.g. {"operator":"!*"} for global queries with no project), id, updated_at. Example: filters=[{"project_id":{"operator":"=","values":["3"]}}].
- **res:** Collection of Query resources. Each Query carries filters, sortBy, groupBy, columns, public, starred, and _links (self, user, project, results, schema, star/unstar, update, updateImmediately, delete). No _embedded.results in the list view.

### GET /api/v3/queries/{id}
Fetch one saved query AND run it — returns the work packages it selects.
- **req:** Can be overridden ad-hoc with the same params as work_packages (filters, offset, pageSize, sortBy, groupBy, showSums, timestamps, timelineVisible, showHierarchies) to page/re-sort without persisting.
- **res:** Query resource with _embedded.results = a full WorkPackageCollection (total, count, pageSize, offset, _embedded.elements, templated _links.self/jumpTo/changeSize). This is the easiest way to execute a stored search and page through it.

### GET /api/v3/queries/default
Run an UNPERSISTED default query — the cleanest way to do an ad-hoc search that returns a full Query+results envelope.
- **req:** Accepts filters, offset, pageSize, sortBy, groupBy, showSums, timestamps, timelineVisible, showHierarchies (defaults: filters=open status, sortBy=[["id","asc"]], offset=1, showHierarchies=true). Project-scoped variant: /api/v3/projects/{id}/queries/default (deprecated in favor of /api/v3/workspaces/{id}/queries/default).
- **res:** Query resource with _embedded.results WorkPackageCollection, plus the resolved filter/sort/group schema links — handy to discover valid operators/values.

### GET /api/v3/queries/form
Validate a query body before creating it (returns a Form with schema, validationErrors, and a commit link).
- **req:** POST-like: send the same JSON body you'd POST to /queries. Returns embedded payload + schema so you can resolve allowed filters/operators/columns.
- **res:** _type: Form. _embedded.payload (echoed query), _embedded.schema, _embedded.validationErrors, _links.commit (href to POST /queries).

### POST /api/v3/queries
Create/save a query (persist a search: filters + sortBy + groupBy + columns + public/starred).
- **req:** JSON body: {name, filters:[...], sortBy:[...], groupBy, columns:[...], sums, public, starred, timelineVisible, showHierarchies, _links:{project:{href:"/api/v3/projects/{id}"}}} (project null/omitted = global query). Note: inside a stored query, filters are represented as HAL QueryFilterInstance objects using _links.filter/operator/values, NOT the compact query-param JSON.
- **res:** 201 with the created Query resource (has id, self link, star/unstar/update/delete action links).

### PATCH /api/v3/queries/{id}
Update a saved query.
- **req:** Two action links: `update` (form-validated) vs `updateImmediately` (persist directly). Body same shape as create; send only changed props.
- **res:** Updated Query resource.

### DELETE /api/v3/queries/{id}
Delete a saved query.
- **req:** No body.
- **res:** 204 No Content.

### PATCH /api/v3/queries/{id}/star
Star (favorite) a query. Also /unstar to remove.
- **req:** Triggered via the query's _links.star.href / _links.unstar.href (PATCH, no body). Requires save-own/manage-public permission.
- **res:** Updated Query with starred=true/false.

### GET /api/v3/queries/schema
Discover all available work-package filters, their operators and expected value types.
- **req:** Also /api/v3/projects/{id}/queries/schema (deprecated) / /api/v3/workspaces/{id}/queries/schema. Read _embedded.filtersSchemas.
- **res:** Schema with embedded filtersSchemas collection; each entry lists the filter name, allowed operators (links to /api/v3/queries/operators/{code}), and value resource type. Use this to resolve customFieldN human names and legal operators dynamically.

### GET /api/v3/queries/available_projects
List projects a new query can be scoped to.
- **req:** No required params.
- **res:** Collection of Project resources.

## Gotchas
- FILTER WIRE FORMAT: filters is a URL-encoded JSON ARRAY of single-key objects: [{"<name>":{"operator":"<code>","values":[<v>,...]}}]. Multiple array entries are AND-ed together. There is no OR across different fields — put multiple values in one filter's values array for OR-within-a-field.
- DEFAULT-FILTER TRAP: omitting the filters param is NOT 'no filter' — the server injects [{"status_id":{"operator":"o","values":null}}] so you only get OPEN items. Send filters=[] to disable filtering and return all statuses.
- VALUES ARE ALWAYS STRINGS IN AN ARRAY, even for numeric IDs: values:["1","2"] not [1,2]. For linked resources (status/type/assignee/author/priority/project/version/category) pass the numeric resource ID as a string. For operators that take no argument (o, c, t, w, *, !*, ow) pass values: null or [].
- FILTER NAME CASING: the documented/UI JSON uses camelCase filter names — status, type, assignee, responsible, author, priority, project, version, category, subject, subjectOrId, search, watcher, parent, createdAt, updatedAt, startDate, dueDate, doneRatio, estimatedTime, customFieldN. The OpenAPI source also lists snake_case internal names (assigned_to, created_at, due_date, start_date, updated_at, custom_field, status, type…) and both largely work; prefer copying exact names from the query schema or the UI network tab.
- CUSTOM FIELDS: filter key is customField<N> (camelCase + integer id), e.g. [{"customField5":{"operator":"=","values":["7"]}}]. List/version-type CFs filter by custom_option / resource ID; text CFs use ~ / !~; multi-value CFs support &= (contains ALL). Resolve N and its type via /api/v3/queries/schema or the CF's schema — N is instance-specific.
- FULL-TEXT SEARCH: two ways. (a) the dedicated `search` filter searches across subject/description/comments: [{"search":{"operator":"**","values":["payment bug"]}}]. (b) the `**` operator on subjectOrId does an ID-or-full-text match. For a simple subject substring use subject with ~ (SQL LIKE, words in order) or !~ to exclude.
- STATUS OPEN/CLOSED: use operator o (open) / c (closed) on the status filter with values:null — this respects each status's is_closed flag, unlike matching specific status IDs with =.
- DATE/RELATIVE OPERATORS ARE SUBTLE: t=today, w=this week (values:null). t-/t+ = exactly N days ago/ahead. Range forms: <t+ = within the next N days, >t+ = more than N days ahead, >t- = within the last N days (fewer than N days ago), <t- = more than N days ago. =d = on a specific ISO date, <>d = between two ISO dates (values has 2 entries). >= / <= are numeric (done_ratio, estimated_hours, ids).
- PAGINATION: offset is a 1-based PAGE index, not a record offset. total = full match count, count = items in current page, pageSize = page size. Follow _links.jumpTo (templated {?offset}) / changeSize (templated {?pageSize}) or just increment offset until offset*pageSize >= total. nextByOffset appears when a next page exists.
- sortBy is a JSON array of [field, direction] pairs: [["status","asc"],["updatedAt","desc"]] — multi-key sort supported; direction is asc/desc. groupBy takes a SINGLE column name string. Combine groupBy with showSums=true to get per-group sums.
- STORED-QUERY FILTER FORMAT DIFFERS: inside GET/POST /api/v3/queries a filter is a HAL QueryFilterInstance ({_type, _links:{filter, operator, values}}), whereas the ad-hoc filters query-param is the compact {name:{operator,values}} JSON. Don't mix them.
- LONG QUERIES: if the URL gets too long, OpenProject accepts a zlib+base64-compressed `eprops` param carrying the encoded query params instead of individual filters/sortBy params.
- select (sparse fieldset) paths are dotted relative to the collection: total,elements/subject,elements/id,self — big performance win when listing many work packages.
- timestamps (baseline/historical comparison) is Enterprise-only; each returned element then carries _embedded.attributesByTimestamp for diffing.

## Examples
```
# Global search: open bugs (type id 7) assigned to user 12 or 34, newest first, page 1 of 20
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/work_packages' \
  --data-urlencode 'filters=[{"type":{"operator":"=","values":["7"]}},{"assignee":{"operator":"=","values":["12","34"]}},{"status":{"operator":"o","values":null}}]' \
  --data-urlencode 'sortBy=[["updatedAt","desc"]]' \
  --data-urlencode 'pageSize=20' --data-urlencode 'offset=1'
```
```
# Disable the default open-only filter to return ALL statuses
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/work_packages' --data-urlencode 'filters=[]'
```
```
# Full-text search across subject/description/comments
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/work_packages' \
  --data-urlencode 'filters=[{"search":{"operator":"**","values":["payment timeout"]}}]'
```
```
# Subject contains (SQL LIKE), exclude a word, within a project path
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/projects/my-project/work_packages' \
  --data-urlencode 'filters=[{"subject":{"operator":"~","values":["login"]}},{"subject":{"operator":"!~","values":["legacy"]}}]'
```
```
# Date filters: due in the next 7 days AND updated within the last 3 days AND created between two dates
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/work_packages' \
  --data-urlencode 'filters=[{"dueDate":{"operator":"<t+","values":["7"]}},{"updatedAt":{"operator":">t-","values":["3"]}},{"createdAt":{"operator":"<>d","values":["2026-01-01T00:00:00Z","2026-06-30T23:59:59Z"]}}]'
```
```
# Filter by custom field 5 = option id 7 (resolve the CF id/type via /api/v3/queries/schema)
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/work_packages' \
  --data-urlencode 'filters=[{"customField5":{"operator":"=","values":["7"]}}]'
```
```
# Group by status with sums
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/work_packages' \
  --data-urlencode 'filters=[]' --data-urlencode 'groupBy=status' --data-urlencode 'showSums=true'
```
```
# Sparse fieldset for fast listing
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/work_packages' \
  --data-urlencode 'select=total,elements/id,elements/subject,elements/status,self'
```
```
# Run an ad-hoc search via the default query (returns Query envelope with _embedded.results)
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/queries/default' \
  --data-urlencode 'filters=[{"assignee":{"operator":"=","values":["me"]}}]'  # some filters accept the keyword "me"
```
```
# Execute a saved query and page through its results
curl -u apikey:$TOKEN 'https://op.example.com/api/v3/queries/142?pageSize=50&offset=2'
```
```
# Create (persist) a saved query — note HAL QueryFilterInstance form for filters
curl -u apikey:$TOKEN -X POST 'https://op.example.com/api/v3/queries' -H 'Content-Type: application/json' -d '{
  "name": "My open bugs",
  "public": false,
  "sortBy": [["updatedAt","desc"]],
  "filters": [{"_links":{"filter":{"href":"/api/v3/queries/filters/status"},"operator":{"href":"/api/v3/queries/operators/o"},"values":[]}}],
  "_links": {"project": {"href": "/api/v3/projects/3"}}
}'
```

## Open questions (verify live)
- Confirm on the live instance whether camelCase filter names (assignee, createdAt, dueDate, customField5) and/or snake_case (assigned_to, created_at, due_date) are the accepted keys for the compact filters query param — copy exact names from GET /api/v3/queries/schema or the browser network tab to be safe.
- Verify each configured custom field's integer id and type (list/text/date/bool) via /api/v3/queries/schema so you can pick the correct operator (=, ~, &=, etc.) and value form (option id vs raw string).
- Confirm whether the `me` keyword value is accepted for assignee/author/watcher filters on this instance/version (works in the UI-generated queries).
- Check the exact WorkPackageCollection _links present in your version (nextByOffset/previousByOffset naming, jumpTo/changeSize templates) by inspecting a real response.
- Confirm the &= 'contains all' operator support for multi-value custom fields and the >t-/<t-/>t+/<t+ relative-date semantics against real data (day-boundary edge cases).
- Determine whether your deployment uses /api/v3/projects/{id}/queries/* (legacy) or /api/v3/workspaces/{id}/queries/* (current) for project-scoped default/schema endpoints.
- timestamps baseline comparison is Enterprise-gated — verify availability if the CLI needs historical/baseline queries.


---

# AREA: Projects

**Auth:** All Projects endpoints use the standard API v3 auth. Simplest for a CLI: HTTP Basic auth with username literally "apikey" and the user's API token as the password (curl -u apikey:TOKEN), or OAuth2 Bearer. Send Content-Type: application/json on POST/PATCH (a missing/incorrect content type yields 406/415). Permissions gate operations: GET requires "view project"; POST create requires the GLOBAL "add project" permission; PATCH requires "edit project"/"edit workspace" on the target; DELETE requires admin. Note {id} in single-project paths accepts either the numeric id OR the string identifier. IMPORTANT: Projects do NOT use lockVersion / optimistic locking (unlike work packages) — the project resource has no lockVersion field, so PATCH just applies the supplied attributes with no version token needed.

## Endpoints

### GET /api/v3/projects
List/filter projects (a HAL collection). Since OP 17.0 this may also return other workspace types (program, portfolio) alongside projects.
- **req:** Optional query params: filters (JSON string), sortBy (JSON string), select (sparse fieldset), plus pagination offset & pageSize. filters example: [{"active":{"operator":"=","values":["t"]}}]. sortBy example: [["name","asc"]] (supported orders: id, name, typeahead, created_at, public, latest_activity_at, required_disk_space, plus per-custom-field). select example: total,elements/identifier,elements/name. All JSON params must be URL-encoded.
- **res:** 200 application/hal+json collection. Envelope: total, count, pageSize, offset; items in _embedded.elements (array of ProjectModel); navigation via _links.self, _links.nextByOffset, _links.previousByOffset, _links.jumpTo (templated). 400 with errorIdentifier ...InvalidQuery on bad filter.

### GET /api/v3/projects/{id}
Fetch one project (id numeric or identifier string).
- **req:** No body. Supports select query param.
- **res:** 200 ProjectModel: _type, id, identifier, name, active, public, favorited, description/statusExplanation (formattable: format/raw/html), createdAt, updatedAt, customFieldN values, and _links (self, parent, status, categories, types, versions, memberships, workPackages, ancestors[], update, updateImmediately, delete, favor/disfavor). 404 if missing or not permitted (403 is masked as 404).

### POST /api/v3/projects
Create a project.
- **req:** application/json body = ProjectModel subset. Required: name. identifier is auto-derived from name if omitted (must be unique, lowercase, [a-z0-9-_]). Optional scalar props: description {raw}, statusExplanation {raw}, public (bool, default false), active (bool, default true), customFieldN (value custom fields). Relations go under _links as {"href":"..."}: parent -> /api/v3/projects/{id}, status -> /api/v3/project_statuses/{code}, and resource-type custom fields as _links.customFieldN (e.g. a user CF -> /api/v3/users/315). Use the form endpoint first to discover valid fields.
- **res:** 201 Created with full ProjectModel (same shape as GET one). 403 MissingPermission (needs global 'add project'). 422 PropertyConstraintViolation with _embedded.details.attribute naming the bad field (e.g. name blank, identifier taken). 400 invalid body; 406/415 content-type problems.

### PATCH /api/v3/projects/{id}
Update a project; also the mechanism to ARCHIVE/UNARCHIVE.
- **req:** application/json with only the attributes to change (partial). Same field shapes as create. ARCHIVE: {"active": false}. UNARCHIVE: {"active": true}. Change status: {"_links":{"status":{"href":"/api/v3/project_statuses/at_risk"}}} plus optional statusExplanation {raw}. Reparent: {"_links":{"parent":{"href":"/api/v3/projects/9"}}} (set null href to detach). NO lockVersion required.
- **res:** 200 with updated ProjectModel. 403 needs 'edit project'. 404 missing. 422 PropertyConstraintViolation (_embedded.details.attribute). 400/406/415 as create.

### DELETE /api/v3/projects/{id}
Permanently delete a project (async).
- **req:** No body. Requires admin. Deletion runs asynchronously; the project is archived immediately then removed in the background — there is no endpoint to poll deletion status.
- **res:** 204 No Content on accepted. 403 MissingPermission (admin). 404 missing. 422 if it cannot be deleted yet (e.g. other workspaces still reference its versions).

### POST /api/v3/projects/form
Create-form: validate a payload and get the schema without persisting.
- **req:** Same JSON body as create (may be empty {}). Use to discover which custom fields/attributes are writable and their allowed values before POSTing.
- **res:** 200 Form object with _embedded.payload (echoed/normalized values), _embedded.schema (per-field type, required, allowedValues, writable), _embedded.validationErrors, and _links.commit (present only when the payload is valid — POST there or to /projects to persist).

### POST /api/v3/projects/{id}/form
Update-form: validate an update payload and get the schema for an existing project.
- **req:** Partial JSON like the PATCH body.
- **res:** 200 Form with _embedded.schema/payload/validationErrors; _links.commit points at PATCH /projects/{id} when valid.

### GET /api/v3/projects/schema
Schema describing project resource (field types, required flags, custom fields / project attributes).
- **req:** No body. DEPRECATED — projects are workspaces now; prefer GET /api/v3/workspaces/schema. Collection form: GET /api/v3/projects/schemas.
- **res:** 200 schema; status field's allowedValues link to /api/v3/project_statuses/{on_track,at_risk,off_track,...}. Custom fields appear as customFieldN entries.

### GET /api/v3/projects/available_parent_projects
List valid parent candidates for creating/reparenting.
- **req:** Optional query: of={id-or-identifier} (candidates for an existing project), or workspace_type={project|program|portfolio}, plus filters/sortBy.
- **res:** 200 HAL collection of eligible parent workspaces in _embedded.elements.

### POST /api/v3/projects/{id}/copy
Duplicate a project (async job).
- **req:** JSON body of attributes to override on the copy; typically driven via POST /api/v3/projects/{id}/copy/form first. Copying is the practical way to carry over enabled modules and configuration.
- **res:** Returns a job/status resource; the new project is created asynchronously.

### GET /api/v3/project_statuses/{id}
Look up a project status resource.
- **req:** {id} is the status CODE, one of: not_started, on_track, at_risk, off_track, finished, discontinued.
- **res:** 200 ProjectStatus: {_type:ProjectStatus, id:<code>, name:<label>, _links.self}. These same hrefs are what you set in a project's _links.status.

## Gotchas
- Projects have NO lockVersion / optimistic locking — do not send lockVersion on project PATCH (that concept applies only to work packages).
- Archiving is NOT a dedicated endpoint. There is no /archive path. You archive by PATCH {"active": false} and unarchive by PATCH {"active": true}. (DeepWiki's mention of separate /archive endpoints is wrong for API v3.)
- Enabled modules are NOT exposed or editable through the API v3 project resource — no enabledModules field or endpoint exists (0 references in the spec). To provision modules, use the copy endpoint from a template project or configure via UI.
- {id} accepts BOTH the numeric id and the string identifier in single-project paths — handy for CLI UX but be consistent.
- identifier is auto-generated from name when omitted, but must be unique and match [a-z0-9-_]; a clash returns 422 PropertyConstraintViolation with _embedded.details.attribute=identifier.
- Formattable fields (description, statusExplanation) are WRITTEN as {"raw": "..."} but READ back as {"format","raw","html"}. Send only raw.
- Relations (parent, status, and resource/link-type custom fields) go under _links as {"href": "..."}; only value-type custom fields are top-level customFieldN keys. To DETACH a parent, PATCH _links.parent.href to null.
- DELETE is asynchronous and returns 204 immediately; the project is archived at once but physically removed later, and there is no status endpoint to poll.
- 'Project attributes' is the newer UI name for project custom fields; which ones are active per project can be filtered via the available_project_attributes filter, and discovered via the (schema/)form endpoints.
- Since OpenProject 17.0 the /projects list can also return programs and portfolios (workspaces), which may surprise strictly-typed clients — filter on _type=Project if you need only projects.
- filters/sortBy/select are JSON strings passed as query params and MUST be URL-encoded. Boolean filter values use ["t"]/["f"], not true/false.
- Pagination offset is a 1-based PAGE NUMBER, not a row offset; combine with pageSize. Read total/count/pageSize from the collection envelope to loop.

## Examples
```
# List active projects, sorted by name, page 1 of 100 (URL-decoded filters shown for clarity)
curl -u apikey:$OP_TOKEN \
  'https://OP_HOST/api/v3/projects?filters=%5B%7B%22active%22%3A%7B%22operator%22%3A%22%3D%22%2C%22values%22%3A%5B%22t%22%5D%7D%7D%5D&sortBy=%5B%5B%22name%22%2C%22asc%22%5D%5D&pageSize=100&offset=1'
# decoded filters: [{"active":{"operator":"=","values":["t"]}}]  decoded sortBy: [["name","asc"]]
```
```
# Filter by parent (children of project 1) and search name/identifier
# filters (decode): [{"parent_id":{"operator":"=","values":["1"]}},{"name_and_identifier":{"operator":"~","values":["mobile"]}}]
```
```
# Create a project with parent, status and a custom field
curl -u apikey:$OP_TOKEN -H 'Content-Type: application/json' -X POST \
  https://OP_HOST/api/v3/projects -d '{
    "name": "Mobile App",
    "identifier": "mobile-app",
    "public": false,
    "active": true,
    "description": { "raw": "Native **iOS/Android** app" },
    "statusExplanation": { "raw": "Kickoff done" },
    "customField5": "High",
    "_links": {
      "parent": { "href": "/api/v3/projects/123" },
      "status": { "href": "/api/v3/project_statuses/on_track" },
      "customField6": { "href": "/api/v3/users/315" }
    }
  }'
```
```
# Archive a project (by identifier)
curl -u apikey:$OP_TOKEN -H 'Content-Type: application/json' -X PATCH \
  https://OP_HOST/api/v3/projects/mobile-app -d '{ "active": false }'

# Unarchive
curl -u apikey:$OP_TOKEN -H 'Content-Type: application/json' -X PATCH \
  https://OP_HOST/api/v3/projects/mobile-app -d '{ "active": true }'
```
```
# Change status + explanation, and rename
curl -u apikey:$OP_TOKEN -H 'Content-Type: application/json' -X PATCH \
  https://OP_HOST/api/v3/projects/42 -d '{
    "name": "Mobile App v2",
    "statusExplanation": { "raw": "Vendor delay" },
    "_links": { "status": { "href": "/api/v3/project_statuses/at_risk" } }
  }'
```
```
# Detach parent (make top-level)
curl -u apikey:$OP_TOKEN -H 'Content-Type: application/json' -X PATCH \
  https://OP_HOST/api/v3/projects/42 -d '{ "_links": { "parent": { "href": null } } }'
```
```
# Delete
curl -u apikey:$OP_TOKEN -X DELETE https://OP_HOST/api/v3/projects/42   # -> 204
```
```
# Validate before create (form) to discover writable custom fields / allowed values
curl -u apikey:$OP_TOKEN -H 'Content-Type: application/json' -X POST \
  https://OP_HOST/api/v3/projects/form -d '{ "name": "Test" }'
# read _embedded.schema, _embedded.validationErrors; _links.commit present only when valid
```

## Open questions (verify live)
- Confirm the default and maximum pageSize on the target instance (commonly 20 default; max governed by the 'Maximum results per page'/per_page_options setting) so the CLI can page efficiently.
- Verify the exact set of active project_status codes on the live instance — spec examples show on_track/at_risk/off_track; the full standard set is not_started, on_track, at_risk, off_track, finished, discontinued. Enumerate via GET on the schema/form allowedValues to be safe.
- Enumerate the instance-specific custom fields / project attributes (customFieldN ids and whether each is a value field vs a _links resource) via POST /api/v3/projects/form or the schema endpoint before building create/update payloads.
- Confirm whether the deprecated GET /api/v3/projects/schema still works on the target version or whether you must switch to /api/v3/workspaces/schema.
- Confirm behavior/response shape of POST /api/v3/projects/{id}/copy (async job resource + how to poll) on the live instance, since it's the practical route for provisioning enabled modules that the project API otherwise doesn't expose.
- Check whether createdAt is writable (spec notes it can be, for admins, only with the apiv3_write_readonly_attributes setting enabled).


---

# AREA: Assignees, users, memberships, groups, roles, principals

**Auth:** All endpoints use the same auth as the rest of APIv3: HTTP Basic with username `apikey` and the API token as the password (or OAuth2 Bearer). For a CLI, Basic-with-apikey is simplest. Permission scoping matters heavily in this area: listing/reading users needs admin or the global `manage_user` permission; creating users, locking/unlocking, and deleting users are admin-only. Memberships require the project-level `view members` permission to list/read and `manage members` to create/update/delete; global (project-less) memberships require `manage_user` or "create project" global rights. Roles are readable by anyone with `view members` or `manage members`. Groups create/update/delete are admin-only. available_assignees / available_watchers are filtered server-side to what the current user is allowed to see, so results differ per token. Property visibility on User resources is also role-gated (login, firstName, lastName, email, createdAt, updatedAt are hidden from non-admins who are not the user themselves).

## Endpoints

### GET /api/v3/users
List/search users (admin or manage_user global permission).
- **req:** Supports pagination (offset, pageSize) and sortBy. Filters via URL-encoded JSON `filters` param. Known user filters: `status` (values are numeric status codes: 1=active, 2=registered, 3=locked, 4=invited), `group` (group id), `name` (searches first/last name, email), `login`. Example: filters=[{"status":{"operator":"=","values":["1"]}}] URL-encoded.
- **res:** HAL Collection: `_type`:"Collection", `total`, `count`, `pageSize`, `offset`, and `_embedded.elements[]` each a User resource. Iterate pages until offset*pageSize >= total.

### GET /api/v3/users/me
Get the currently authenticated user (resolve 'who am I' / default assignee).
- **req:** No params. `me` is a magic id also usable at /api/v3/users/me; equivalent to /api/v3/users/{myId}.
- **res:** Single User resource: id, name, firstName, lastName, login, email, admin (bool), status, language, avatar, and `_links.self`. Good for validating the token and getting the caller's id.

### GET /api/v3/users/{id}
Fetch one user by numeric id (or 'me').
- **req:** id is integer or the literal `me`.
- **res:** User resource. `_links` include self, showUser (HTML), updateImmediately (PATCH), lock, unlock, delete, and `memberships`. Non-admin callers see a reduced property set for other users.

### POST /api/v3/users
Create a new user (admin only).
- **req:** Plain JSON body (not wrapped). Required: `login` (<=256), `email` (<=60), `firstName` (<=30), `lastName` (<=30), and `status` ("active" or "invited"). `password` is REQUIRED when status="active"; for status="invited" OpenProject emails an invitation and no password is set. Optional: `admin` (bool), `language` (ISO 639-1 like "en"), plus `_links.auth_source` (LDAP, admin) or `identity_url` for OmniAuth SSO. Use GET /api/v3/users/schema to discover exact writable fields for the target instance.
- **res:** 201 with the created User resource (has id). 422 with an Error/ErrorCollection body on validation failure (e.g. duplicate login/email).

### PATCH /api/v3/users/{id}
Update user attributes (self-service limited; admin for others).
- **req:** Send only changed fields as plain JSON. Users resources do NOT use lockVersion (no optimistic locking on users). Self password change requires supplying `password` plus `currentPassword`.
- **res:** 200 with updated User resource.

### POST /api/v3/users/{id}/lock  and  /api/v3/users/{id}/unlock
Restrict / re-enable a user's login (admin only).
- **req:** No body. Also exposed as `lock`/`unlock` _links on the User resource.
- **res:** 200 with the User resource, status flips to "locked"/"active".

### DELETE /api/v3/users/{id}
Permanently delete a user (admin, or self if enabled).
- **req:** No body. Irreversible.
- **res:** 202 Accepted (deletion is processed asynchronously).

### GET /api/v3/projects/{id}/available_assignees
List principals that can be set as assignee (and, since v14, also responsible) for work packages in the project.
- **req:** {id} is the project id or identifier. This is the correct source for populating an assignee picker in a CLI. Returns both Users and Groups (any assignable principal). Note: available_responsibles was REMOVED in OpenProject 14.0 because it returned identical data — use available_assignees for both. Docs mention a newer alias /api/v3/workspaces/{id}/available_assignees; the /projects/{id}/ path remains the widely-supported one (verify against your instance version).
- **res:** HAL Collection with `_embedded.elements[]` of User (and possibly Group) resources, plus `total`/`count`. Each element's `_links.self.href` (e.g. /api/v3/users/11 or /api/v3/groups/7) is exactly what you put into the work package's assignee link.

### GET /api/v3/work_packages/{id}/available_watchers
List users who may be added as watchers on a specific work package.
- **req:** {id} is a work package id (watcher eligibility is per-WP, unlike assignees which are per-project). Requires `add work package watchers` permission.
- **res:** HAL Collection of User resources in `_embedded.elements[]`. Add one with POST /api/v3/work_packages/{id}/watchers body {"user":{"href":"/api/v3/users/{uid}"}}; remove with DELETE /api/v3/work_packages/{id}/watchers/{uid}.

### PATCH /api/v3/work_packages/{id}
Set/change the assignee and/or responsible on a work package (this is how assignee is assigned — confirmed).
- **req:** Assignee is NOT a plain field; it is set via `_links.assignee.href` pointing to /api/v3/users/{id} OR /api/v3/groups/{id} (groups can be assignees). Same for `_links.responsible.href`. You MUST include the current `lockVersion` (integer) for optimistic locking, or the PATCH is rejected with 409 Conflict. Set to null via {"href": null} to unassign. Optional ?notify=false query param suppresses notifications.
- **res:** 200 with the updated WorkPackage (lockVersion incremented). 409 if lockVersion is stale — re-GET the WP to obtain the fresh lockVersion and retry.

### GET /api/v3/memberships
List project (and global) memberships with filtering/sorting.
- **req:** Pagination offset/pageSize. URL-encoded JSON `filters`. Useful filters: `project` (project id), `principal` (user/group id), `role` (role id), `name`, `email`, `status`, `group`, `blocked`, `created_at`, `updated_at`. sortBy default [["id","asc"]]. Example to find a user's membership in a project: filters=[{"project":{"operator":"=","values":["3"]}},{"principal":{"operator":"=","values":["5"]}}].
- **res:** HAL Collection; `_embedded.elements[]` each a Membership with id, createdAt, updatedAt, and `_links`/`_embedded` for project, principal, roles[]. You need the membership id to PATCH or DELETE it.

### POST /api/v3/memberships
Add a user OR group to a project with one or more roles.
- **req:** Body is HAL: `_links.principal.href` = /api/v3/users/{id} or /api/v3/groups/{id} (required); `_links.roles` = ARRAY of {href:/api/v3/roles/{id}} (required, at least one); `_links.project.href` = /api/v3/projects/{id} (omit for a global/system membership). Optional `_meta.notificationMessage` {format:"markdown", raw:"..."} and `_meta.sendNotification` (bool, default true — set false to add silently). Validate first with POST /api/v3/memberships/form if unsure. Only grantable, project-unit roles are valid here (see roles filters).
- **res:** 201 with the created Membership resource (has id, embedded principal/project/roles). 422 on invalid role/principal.

### PATCH /api/v3/memberships/{id}
Change the set of roles on an existing membership.
- **req:** Send `_links.roles` as the FULL replacement array of role hrefs (it replaces, not merges — include every role you want kept). Principal and project are generally immutable. Supports the same `_meta.notificationMessage`/`sendNotification`. No lockVersion on memberships.
- **res:** 200 with updated Membership.

### DELETE /api/v3/memberships/{id}
Remove a user/group from a project (delete the membership).
- **req:** Needs the membership id (find it via the list filter above), not the user id. No body.
- **res:** 204 No Content on success.

### GET /api/v3/memberships/available_projects
List projects in which the caller may manage members (for building a create-membership flow).
- **req:** No required params.
- **res:** HAL Collection of Project resources in `_embedded.elements[]`.

### GET /api/v3/roles
List all roles to obtain role ids/hrefs for memberships.
- **req:** Filters: `grantable` (whether the role is assignable to a membership) and `unit` ('project' or 'system'). To get roles valid for a normal project membership use filters=[{"unit":{"operator":"=","values":["project"]}},{"grantable":{"operator":"=","values":["true"]}}]. Includes built-ins like Anonymous and Non member.
- **res:** HAL Collection; each element Role has id, name, _type:"Role", `_links.self` (the href you feed into membership roles[]).

### GET /api/v3/roles/{id}
Fetch a single role.
- **req:** Requires view members or manage members permission.
- **res:** Role resource {id, name, _type, _links.self}. 403/404 as usual.

### GET /api/v3/groups
List all groups (each is a Principal).
- **req:** Standard collection; supports pagination.
- **res:** HAL Collection of Group resources in `_embedded.elements[]`.

### POST /api/v3/groups
Create a group with optional initial members (admin only).
- **req:** Body: {"name":"..." (required), "_links":{"members":[{"href":"/api/v3/users/42"},...] (optional)}}.
- **res:** 201 with Group resource; `_embedded.members[]` lists the member users; `_links` include self, members, memberships, updateImmediately, delete.

### GET/PATCH/DELETE /api/v3/groups/{id}
Read, update (rename / change members), or delete a group.
- **req:** PATCH accepts `name` and/or `_links.members` (the members array is a full replacement set). Admin-only for PATCH/DELETE. No lockVersion.
- **res:** GET/PATCH return the Group resource; DELETE returns 202 Accepted (async).

### GET /api/v3/principals
Unified list of users + groups + placeholder users — best single endpoint for assignee/watcher autocompletion across types.
- **req:** Filters (URL-encoded JSON): `type` (values "User","Group","PlaceholderUser"), `name` (~ contains), `any_name_attribute` (matches first/last name, email, or login — great for search-as-you-type), `status` (1=active,2=registered,3=locked,4=invited), and `member` (project id(s) — restricts to principals who are members of those projects, i.e. eligible assignees). Operators here are typically `=` and `~`. Example: filters=[{"member":{"operator":"=","values":["3"]}},{"type":{"operator":"=","values":["User"]}},{"any_name_attribute":{"operator":"~","values":["john"]}}]. Supports pagination + sortBy.
- **res:** HAL Collection; `_embedded.elements[]` mixes User/Group/PlaceholderUser (check `_type`). Results are limited to principals visible to the caller.

## Gotchas
- Assignee is set through a HAL link, never a plain field: PATCH the work package with `_links.assignee.href` = /api/v3/users/{id} (or /api/v3/groups/{id}). Groups CAN be assignees/responsibles. To unassign, send {"href": null}.
- Work package PATCH REQUIRES the current integer `lockVersion`; a stale value returns 409 Conflict. Always GET the WP first, read lockVersion, then PATCH. Users, memberships, groups, and roles do NOT use lockVersion.
- available_responsibles was removed in OpenProject 14.0 — it returned the same data as available_assignees. Use /api/v3/projects/{id}/available_assignees for both assignee and responsible pickers.
- Docs reference a newer /api/v3/workspaces/{id}/available_assignees alias and label the /projects/{id}/ form 'deprecated', but the /projects/{id}/ path is what most instances still serve. Detect version or try /projects first.
- Removing a person from a project is a DELETE on the MEMBERSHIP id, not the user id. You must first list memberships filtered by project+principal to discover that membership id.
- Membership PATCH `_links.roles` REPLACES the whole role set — it does not append. Include every role you want to keep, or the omitted ones are removed.
- Group `_links.members` on PATCH is likewise a full-replacement set, not an add.
- Only roles with unit='project' and grantable=true are valid targets for a project membership; feeding a system/built-in role href will 422. Filter roles accordingly.
- User `status` field uses strings in create/read ("active","invited","registered","locked") but numeric codes in the `status` filter values (1/2/3/4). Same numeric codes for the principals status filter.
- Creating a user with status="active" REQUIRES a password; status="invited" triggers an email invitation flow and needs no password.
- User/Principal property visibility is role-gated: a non-admin token may get back Users with login/email/name fields omitted for other people, which can break code that assumes those fields are present.
- Suppress member-add emails with `_meta.sendNotification=false`; suppress work-package assignee-change emails with the ?notify=false query param on the PATCH.
- The `filters` query param is a URL-encoded JSON ARRAY of single-key objects: [{"name":{"operator":"=","values":["x"]}}]. values are ALWAYS strings, even for ids/booleans ("true", "5").

## Examples
```
# Who am I (validate token, get caller id)
curl -u apikey:$TOKEN https://op.example.com/api/v3/users/me
```
```
# Create an active user
curl -u apikey:$TOKEN -H 'Content-Type: application/json' -X POST \
  https://op.example.com/api/v3/users -d '{
  "login":"j.doe","email":"j.doe@example.com",
  "firstName":"Jane","lastName":"Doe",
  "status":"active","password":"Str0ngPassw0rd!",
  "admin":false,"language":"en"
}'
```
```
# List assignable principals for project 3 (populate assignee picker)
curl -u apikey:$TOKEN 'https://op.example.com/api/v3/projects/3/available_assignees?pageSize=100'
```
```
# Assign work package 1234 to user 11 (must include current lockVersion)
curl -u apikey:$TOKEN -H 'Content-Type: application/json' -X PATCH \
  'https://op.example.com/api/v3/work_packages/1234?notify=false' -d '{
  "lockVersion": 7,
  "_links": { "assignee": { "href": "/api/v3/users/11" } }
}'
```
```
# Unassign a work package
curl -u apikey:$TOKEN -H 'Content-Type: application/json' -X PATCH \
  https://op.example.com/api/v3/work_packages/1234 -d '{"lockVersion":8,"_links":{"assignee":{"href":null}}}'
```
```
# Add user 5 to project 3 with roles 4 and 6, silently
curl -u apikey:$TOKEN -H 'Content-Type: application/json' -X POST \
  https://op.example.com/api/v3/memberships -d '{
  "_links": {
    "project":   { "href": "/api/v3/projects/3" },
    "principal": { "href": "/api/v3/users/5" },
    "roles": [ {"href":"/api/v3/roles/4"}, {"href":"/api/v3/roles/6"} ]
  },
  "_meta": { "sendNotification": false }
}'
```
```
# Find the membership id for user 5 in project 3 (needed before update/delete)
curl -u apikey:$TOKEN 'https://op.example.com/api/v3/memberships?filters=%5B%7B%22project%22%3A%7B%22operator%22%3A%22%3D%22%2C%22values%22%3A%5B%223%22%5D%7D%7D%2C%7B%22principal%22%3A%7B%22operator%22%3A%22%3D%22%2C%22values%22%3A%5B%225%22%5D%7D%7D%5D'
```
```
# Change roles on membership 42 (full replacement set)
curl -u apikey:$TOKEN -H 'Content-Type: application/json' -X PATCH \
  https://op.example.com/api/v3/memberships/42 -d '{"_links":{"roles":[{"href":"/api/v3/roles/6"}]}}'
```
```
# Remove membership 42 (removes the user from the project)
curl -u apikey:$TOKEN -X DELETE https://op.example.com/api/v3/memberships/42
```
```
# List grantable project roles to choose role ids
curl -u apikey:$TOKEN 'https://op.example.com/api/v3/roles?filters=%5B%7B%22unit%22%3A%7B%22operator%22%3A%22%3D%22%2C%22values%22%3A%5B%22project%22%5D%7D%7D%5D'
```
```
# Create a group with two initial members
curl -u apikey:$TOKEN -H 'Content-Type: application/json' -X POST \
  https://op.example.com/api/v3/groups -d '{"name":"QA Team","_links":{"members":[{"href":"/api/v3/users/42"},{"href":"/api/v3/users/43"}]}}'
```
```
# Autocomplete assignees across users+groups in project 3 matching 'john'
curl -u apikey:$TOKEN 'https://op.example.com/api/v3/principals?filters=%5B%7B%22member%22%3A%7B%22operator%22%3A%22%3D%22%2C%22values%22%3A%5B%223%22%5D%7D%7D%2C%7B%22any_name_attribute%22%3A%7B%22operator%22%3A%22~%22%2C%22values%22%3A%5B%22john%22%5D%7D%7D%5D'
```

## Open questions (verify live)
- Confirm whether your instance version serves /api/v3/projects/{id}/available_assignees (older) or the newer /api/v3/workspaces/{id}/available_assignees alias — the docs mark the projects form deprecated but most deployments still respond on it. Test both against the live instance.
- Verify available_assignees actually returns Group principals on your instance (some versions return only Users) if you intend to assign work packages to groups.
- Confirm exact writable user fields by GETting /api/v3/users/schema on the target instance — custom fields and auth-source requirements vary by configuration (e.g. LDAP-managed instances may forbid setting password).
- Verify the DELETE user / DELETE group responses (202 async vs 204) on your version, and whether self-deletion is enabled in instance settings.
- Confirm whether placeholder users (PlaceholderUser) are relevant for your assignee flows; they appear via /api/v3/principals and /api/v3/placeholder_users but cannot log in.
- Check whether membership PATCH allows changing the principal/project on your version (generally immutable — usually you must delete and recreate).
- Confirm the numeric status filter codes (1=active,2=registered,3=locked,4=invited) against the live instance, as some endpoints also accept the string status names in filters.


---

# AREA: Comments & activities (work package journals/comments)

**Auth:** Same auth as the rest of API v3: HTTP Basic with username `apikey` + the API token, or OAuth2 Bearer. Reading activities requires the `view work package` permission on the containing work package (a 404 is returned if the WP is missing OR not viewable). Posting a comment requires the `add work package notes` / `create journals` permission (plus `view work package`). Editing a comment via PATCH requires the `edit journals` permission; the author of an own comment can edit it, and users with the right permission can edit others' comments; otherwise 403 "You are not allowed to edit the comment of this journal entry". Internal comments (a newer feature) are gated separately: viewing needs `view_internal_comments`, adding needs `add_internal_comments`.

## Endpoints

### GET /api/v3/work_packages/{id}/activities
List all activities (comments AND system change journals) for one work package, oldest-first.
- **req:** Path param `id` = work package id (required). Query params: `offset` (page number, 1-based, default 1) and `pageSize` (elements per page). No `filters` param on this endpoint. Requires `view work package` permission on the WP.
- **res:** HAL Collection: `{"_type":"Collection","total":N,"count":N,"_embedded":{"elements":[Activity...]}}`. Each element is an Activity resource (see gotchas for the comment-vs-journal distinction). This collection is NOT self-paginating in the classic sense on older versions — it returns all entries; use `total`/`count` to size. Each activity carries `_links.self` pointing at `/api/v3/activities/{activityId}`.

### POST /api/v3/work_packages/{id}/activities
Add a new comment (journal note) to a work package. operationId Comment_work_package.
- **req:** Path param `id` = work package id. Query param `notify` (boolean, optional, DEFAULT true) — controls whether change notifications / emails are sent to watchers, assignee, etc.; set `?notify=false` to comment silently. Content-Type: application/json. Body uses the activity comment write model: `{"comment":{"raw":"...markdown..."}}`. Optional `internal` boolean (default false) on instances supporting internal comments. Only `comment.raw` is writable; do not send `format`/`html`. Requires `create journals` + `view work package`.
- **res:** 201 Created with the created Activity resource (HAL+JSON) as body, including `id`, `_type:"Activity::Comment"`, `version`, `comment.{format,raw,html}`, `createdAt`, and `_links.self`/`workPackage`/`user`. Errors: 400 invalid body, 403 insufficient permission, 404 WP not found/not viewable.

### GET /api/v3/activities/{id}
Retrieve a single activity (comment or journal) by its own id.
- **req:** Path param `id` = activity id (the numeric id from `_links.self` of a collection element, NOT the work package id). No body.
- **res:** 200 OK, single Activity resource in HAL+JSON with the full property set (id, version, comment, details[], createdAt, updatedAt, internal, _type, _links).

### PATCH /api/v3/activities/{id}
Edit the comment text of an existing activity. operationId Update_activity.
- **req:** Path param `id` = activity id. Content-Type: application/json. Body is the activity comment write model: `{"comment":{"raw":"new markdown"}}` (optionally `internal`). Requires `edit journals` permission (or being the comment author with edit rights). IMPORTANT: the API docs / OpenAPI spec do NOT document a `lockVersion` field or a 409 response for this endpoint — unlike work package PATCH, optimistic locking is not required here; you just send the new `comment.raw`. Attempting to change read-only props (e.g. `id`) yields 422 "The ID of an activity can't be changed".
- **res:** 200 OK with the updated Activity resource (HAL+JSON); its `version` and `updatedAt` change. Errors: 400 invalid body, 403 "You are not allowed to edit the comment of this journal entry", 406 missing Content-Type, 415 unsupported media type, 422 read-only property modification.

## Gotchas
- Two different id spaces: the collection is fetched by WORK PACKAGE id (/work_packages/{id}/activities) but edits/reads of a single entry use the ACTIVITY id (/activities/{activityId}). Get the activity id from each element's `_links.self.href`.
- Distinguishing comments from system journal entries: check `_type`. `"Activity::Comment"` = a user comment (has non-empty `comment.raw`). Plain `"Activity"` = a change journal entry generated by the system. A single activity can be BOTH — a user can change fields and add a comment in the same journal, so an `Activity::Comment` may also carry a populated `details` array. Practically: treat non-empty `comment.raw` as 'has a comment' and non-empty `details[]` as 'has field changes'.
- `details` is an array of Formattable objects (each with format/raw/html) describing each field change in human-readable markdown (e.g. 'Status changed from New to In progress'). Use it to render the change log; it is read-only.
- Markdown: comment content is CommonMark markdown. Write only `comment.raw`; the server returns `comment.format` ("markdown"), `raw`, and rendered `html`. Do not send `html`/`format` on writes.
- `notify` defaults to TRUE on POST — comments trigger emails/notifications unless you pass `?notify=false`. There is no `notify` param documented on PATCH.
- lockVersion is NOT used for activity PATCH (no 409 documented), which differs from work package updates where a matching `lockVersion` in the body is mandatory and a stale one returns 409. Do not try to read/send lockVersion when editing a comment.
- On POST, the whole created Activity is returned (201) — capture `_links.self` to allow later edit/delete rather than re-listing.
- `internal` (internal comments) is a newer capability; older instances ignore it and it defaults to false (a normal, visible comment). Viewing/adding internal comments needs the separate `view_internal_comments`/`add_internal_comments` permissions.
- There is no documented DELETE for a comment via this endpoint set; comments are typically removed by PATCHing to empty or via the WP UI — verify on the target instance.
- Activities also expose sub-resources on newer versions: `/api/v3/activities/{id}/attachments` (GET/POST multipart) and `/api/v3/activities/{id}/emoji_reactions` — relevant only if the CLI needs attachments/reactions on comments.

## Examples
```
# List activities for work package 1234 (comments + journals)
curl -u apikey:$OP_TOKEN \
  'https://op.example.com/api/v3/work_packages/1234/activities?pageSize=100'
```
```
# Add a markdown comment, sending notifications (default)
curl -u apikey:$OP_TOKEN -X POST \
  -H 'Content-Type: application/json' \
  'https://op.example.com/api/v3/work_packages/1234/activities' \
  -d '{"comment":{"raw":"Deployed to **staging**. See `release-2.3`."}}'
```
```
# Add a comment silently (no emails)
curl -u apikey:$OP_TOKEN -X POST \
  -H 'Content-Type: application/json' \
  'https://op.example.com/api/v3/work_packages/1234/activities?notify=false' \
  -d '{"comment":{"raw":"internal note, no ping"}}'
```
```
# Edit an existing comment (activity id 98765) — no lockVersion needed
curl -u apikey:$OP_TOKEN -X PATCH \
  -H 'Content-Type: application/json' \
  'https://op.example.com/api/v3/activities/98765' \
  -d '{"comment":{"raw":"edited: fixed the typo"}}'
```
```
# Detect comment vs system journal in a response element
# element._type == 'Activity::Comment' AND element.comment.raw != '' -> user comment
# element._type == 'Activity' (comment.raw empty) with element.details[] populated -> system change log
```

## Open questions (verify live)
- Confirm on the live instance whether GET /work_packages/{id}/activities honors offset/pageSize (auto-paginates) or returns the full list in one Collection — behavior has differed across versions.
- Verify whether the target instance supports the `internal` comment flag and the `view_internal_comments`/`add_internal_comments` permissions (feature availability varies by version/edition).
- Confirm PATCH /api/v3/activities/{id} truly requires no lockVersion on the target version (docs omit it and omit a 409) — test an edit and watch for 409/422.
- Check whether comment deletion is possible via the API on this instance (no DELETE is documented for the activity endpoint).
- Confirm the exact permission name mapping on the instance: docs mention both 'add work package notes'/'create journals' for POST and 'edit journals' for PATCH; verify the role has these enabled.


---

# AREA: Time entries (/api/v3/time_entries) — list, get, create, update, delete, activities, schema; filtering for per-person / per-project reporting

**Auth:** Standard API v3 auth. Use HTTP Basic with username `apikey` and the user's API token as the password (curl -u apikey:TOKEN), or OAuth2 Bearer. Every write needs `Content-Type: application/json`. Permissions matter here: creating requires "Log own time" (or "Log time" for others); listing/reading needs "View time entries" (you see your own + entries you're permitted to view); editing needs "Edit time entries" or "Edit own time entries" (own only). Setting `_links.user` to someone else requires the "Log time for other users" permission. Ongoing timers are visible/editable to their owner even without the broader view/edit perms.

## Endpoints

### GET /api/v3/time_entries
List time entries (paginated, filterable, sortable). Primary reporting endpoint.
- **req:** Query params: `filters` (URL-encoded JSON array, see gotchas), `offset` (1-based page, default 1), `pageSize` (default 20/instance max), `sortBy` (URL-encoded JSON, e.g. [["spent_on","desc"]]). Sortable fields: id, hours, spent_on, created_at, updated_at (default [["spent_on","asc"]]). Available filter names (snake_case): user_id, project_id, entity_type (values "WorkPackage"/"Meeting"), entity_id, activity_id, spent_on, created_at, updated_at, ongoing. There is NO work_package_id filter — filter by work package via entity_type=WorkPackage + entity_id.
- **res:** HAL Collection: {_type:"Collection", total, count, pageSize, offset, _embedded:{elements:[TimeEntry,...]}, _links:{self, nextByOffset, previousByOffset, jumpTo(templated), changeSize(templated)}}. Iterate _embedded.elements; page until offset*pageSize >= total or follow _links.nextByOffset.

### GET /api/v3/time_entries/{id}
Retrieve a single time entry.
- **req:** No body. 404 if not found or not viewable.
- **res:** TimeEntry resource (see create response shape). Note: NO lockVersion field is present.

### POST /api/v3/time_entries
Create a time entry (log time).
- **req:** JSON body. hours MUST be an ISO8601 duration string (e.g. "PT2H30M", "PT4H") — decimals are NOT accepted by the API. Required per schema: spentOn (date), hours (ISO8601 duration; omitted for ongoing timers), _links.entity (work package or meeting), _links.user. In practice _links.user defaults to the authenticated user when omitted — send it only to log on behalf of another. _links.project is OPTIONAL (derived from the entity's project if omitted). Optional: _links.activity (a default activity is used if omitted), comment ({"raw":"..."}), ongoing (bool). startTime/endTime only when the instance enables time tracking. Legacy: _links.workPackage still accepted as an alias for a work-package entity (deprecated in favor of _links.entity).
- **res:** 201 Created with the full TimeEntry (see example). Includes _links.updateImmediately (patch), update (post form), delete, schema, self, project, entity, workPackage (if WP), user, activity.

### PATCH /api/v3/time_entries/{id}
Update a time entry in place (the updateImmediately link).
- **req:** Send ONLY the changed properties/links as a JSON body — a partial document. Time entries have NO lockVersion / optimistic locking (the resource carries no lockVersion property and the model has no lock_version column), so you do NOT send lockVersion and there is no 409-conflict concern. e.g. {"hours":"PT3H"} or {"comment":{"raw":"updated"}} or {"_links":{"activity":{"href":"/api/v3/time_entries/activities/2"}}}.
- **res:** 200 OK with the updated TimeEntry. 422 on validation errors.

### DELETE /api/v3/time_entries/{id}
Delete a time entry.
- **req:** No body.
- **res:** 204 No Content on success; 403/404 otherwise.

### POST /api/v3/time_entries/form
Create-form: validate/prepare a payload without persisting; returns computed schema + payload + validationErrors.
- **req:** Same body shape as create; nothing is saved. Useful to resolve the default activity, allowed values, and validate before POSTing.
- **res:** Form resource with _embedded.payload, _embedded.schema, _embedded.validationErrors, and a commit link when valid.

### POST /api/v3/time_entries/{id}/form
Update-form: validate a proposed change without saving.
- **req:** Partial body like the PATCH.
- **res:** Form resource as above.

### GET /api/v3/time_entries/schema
Schema for time entries: field types, writability, required flags, and allowed values (including allowed activities).
- **req:** No body. Single global schema (not per-project in the path). allowedValues for activity are embedded/linked here; allowed projects/work packages/users are exposed via href links on the schema.
- **res:** Schema resource. Key writable fields: spentOn(Date,required), hours(Duration,required for non-ongoing), comment(Formattable,plain,optional), ongoing(Boolean,optional), startTime(DateTime, required only if instance forces start/end tracking), user(required), entity(required), project(optional), activity(optional, has default). endTime is read-only (writable:false).

### GET /api/v3/time_entries/activities/{id}
Retrieve a single time entry activity.
- **req:** No body. NOTE: there is NO collection/list endpoint for activities (the route only defines GET by id). To enumerate selectable activities, read the `activity` field's allowedValues from GET /api/v3/time_entries/schema (or the create-form response), which are project-scoped.
- **res:** TimeEntriesActivity: {_type, id, name (max 30 chars), position, default(bool), _embedded:{projects:[...]}, _links:{self, projects}}. Referenced from a time entry via _links.activity → /api/v3/time_entries/activities/{id}.

### GET /api/v3/time_entries/available_projects
List projects in which the current user is allowed to log time (use to populate _links.project / pick where to log).
- **req:** No body.
- **res:** HAL Collection of Project resources.

### GET /api/v3/time_entries/available_work_packages_on_create
List work packages the user can log time against when creating.
- **req:** May accept a project filter; returns candidate work packages for _links.entity.
- **res:** HAL Collection of WorkPackage resources.

### GET /api/v3/time_entries/{id}/available_work_packages_on_edit
List work packages selectable when editing an existing entry.
- **req:** No body.
- **res:** HAL Collection of WorkPackage resources.

## Gotchas
- hours is ISO8601 DURATION, not decimal: send "PT2H30M", "PT4H", "PT45M" — the API rejects/misreads plain numbers like 2.5. On read it is also returned as an ISO8601 duration string (internally stored as decimal hours). Your CLI must convert user-entered decimals (2.5) to/from ISO8601 durations.
- NO optimistic locking on time entries: unlike work packages, TimeEntry has no lockVersion. Do NOT send lockVersion on PATCH; there is no 409 conflict flow. Just PATCH the changed fields.
- Filter by work package uses entity_type + entity_id, NOT a work_package_id filter (which does not exist). Example: [{"entity_type":{"operator":"=","values":["WorkPackage"]}},{"entity_id":{"operator":"=","values":["77"]}}].
- entity vs workPackage vs project requiredness differs by version: current dev schema marks _links.entity (work package/meeting) required and _links.project optional (project is derived from the entity). Older/published docs treat project as required. For the common case send _links.entity (the work package); project is inferred. Verify against the target instance if you need project-only logging (no work package).
- _links.workPackage is DEPRECATED in favor of _links.entity but still accepted on write; on read, workPackage link is only present when the entity is a WorkPackage. Prefer entity for new code, but accept both when parsing.
- comment is a plain Formattable: send {"comment":{"raw":"text"}}; it is returned as {format:"plain", raw, html}. It is NOT markdown/rich text.
- _links.user defaults to the authenticated user on create when omitted; set it explicitly only to log on behalf of someone else, which requires the 'Log time for other users' permission (else 403/422).
- startTime/endTime are only writable/visible when the instance enables start-and-end-time tracking (allow_tracking_start_and_end_times); startTime becomes required only if the instance forces it. endTime is read-only via the API. Guard for their absence.
- spentOn is a plain calendar date YYYY-MM-DD (no time). Date-range reporting uses the spent_on filter with operator '<>d' and two ISO dates.
- filters, sortBy are URL-encoded JSON in query params. Each filter is its own object in the array; multiple objects are AND-combined. Values are always arrays of strings (even booleans/ids).
- Pagination offset is a 1-based PAGE number, not a record offset; combine with pageSize. Use total/count to know when to stop, or follow _links.nextByOffset. For very large/complex queries the API also supports a zlib+base64 'eprops' param instead of raw filters.
- Activities have no list endpoint — enumerate via the schema's activity allowedValues (project-scoped). activity has a server-side default, so omitting _links.activity is valid.

## Examples
```
# List my time entries for July 2026 (per-person + date range), newest first
FILTERS='[{"user_id":{"operator":"=","values":["me"]}},{"spent_on":{"operator":"<>d","values":["2026-07-01","2026-07-31"]}}]'
SORT='[["spent_on","desc"]]'
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/time_entries' \
  --data-urlencode "filters=$FILTERS" \
  --data-urlencode "sortBy=$SORT" \
  --data-urlencode 'pageSize=100' --data-urlencode 'offset=1'
```
```
# Per-project report for a date range (note: user_id 'me' resolves to the current user; use a numeric id for a specific person)
FILTERS='[{"project_id":{"operator":"=","values":["11"]}},{"spent_on":{"operator":"<>d","values":["2026-07-01","2026-07-31"]}}]'
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/time_entries' --data-urlencode "filters=$FILTERS"
```
```
# Filter by a specific work package
FILTERS='[{"entity_type":{"operator":"=","values":["WorkPackage"]}},{"entity_id":{"operator":"=","values":["77"]}}]'
curl -u apikey:$TOKEN -G 'https://op.example.com/api/v3/time_entries' --data-urlencode "filters=$FILTERS"
```
```
# Create: log 2h30m on work package 77 today with an activity and comment (project inferred, user defaults to me)
curl -u apikey:$TOKEN -X POST 'https://op.example.com/api/v3/time_entries' \
  -H 'Content-Type: application/json' -d '{
  "spentOn": "2026-07-15",
  "hours": "PT2H30M",
  "comment": {"raw": "Implemented CLI time command"},
  "_links": {
    "entity":   {"href": "/api/v3/work_packages/77"},
    "activity": {"href": "/api/v3/time_entries/activities/1"}
  }
}'
```
```
# Create on behalf of another user (needs 'Log time for other users' permission)
curl -u apikey:$TOKEN -X POST 'https://op.example.com/api/v3/time_entries' \
  -H 'Content-Type: application/json' -d '{
  "spentOn": "2026-07-15", "hours": "PT1H",
  "_links": {"entity": {"href": "/api/v3/work_packages/77"}, "user": {"href": "/api/v3/users/3"}}
}'
```
```
# Update just the hours and comment (partial PATCH, NO lockVersion)
curl -u apikey:$TOKEN -X PATCH 'https://op.example.com/api/v3/time_entries/42' \
  -H 'Content-Type: application/json' -d '{"hours": "PT3H", "comment": {"raw": "Adjusted"}}'
```
```
# Change the activity of an entry
curl -u apikey:$TOKEN -X PATCH 'https://op.example.com/api/v3/time_entries/42' \
  -H 'Content-Type: application/json' -d '{"_links": {"activity": {"href": "/api/v3/time_entries/activities/2"}}}'
```
```
# Delete
curl -u apikey:$TOKEN -X DELETE 'https://op.example.com/api/v3/time_entries/42'
```
```
# Discover selectable activities (no list endpoint) via the schema
curl -u apikey:$TOKEN 'https://op.example.com/api/v3/time_entries/schema'
```
```
# 201 create response (shape)
{
  "_type": "TimeEntry", "id": 42,
  "comment": {"format": "plain", "raw": "...", "html": "<p>...</p>"},
  "spentOn": "2026-07-15", "hours": "PT2H30M", "ongoing": false,
  "createdAt": "2026-07-15T13:58:24.927Z", "updatedAt": "2026-07-15T13:58:24.927Z",
  "_links": {
    "self": {"href": "/api/v3/time_entries/42"},
    "updateImmediately": {"href": "/api/v3/time_entries/42", "method": "patch"},
    "update": {"href": "/api/v3/time_entries/42/form", "method": "post"},
    "delete": {"href": "/api/v3/time_entries/42", "method": "delete"},
    "schema": {"href": "/api/v3/time_entries/schema"},
    "project": {"href": "/api/v3/projects/11", "title": "DeathStarV2"},
    "entity": {"href": "/api/v3/work_packages/77", "title": "Build new hangar"},
    "workPackage": {"href": "/api/v3/work_packages/77", "title": "Build new hangar"},
    "user": {"href": "/api/v3/users/3", "title": "Darth Vader"},
    "activity": {"href": "/api/v3/time_entries/activities/1", "title": "Management"}
  }
}
```

## Open questions (verify live)
- entity-vs-project requiredness: the current dev schema marks _links.entity (work package/meeting) REQUIRED and _links.project OPTIONAL (derived), while older releases and the published docs treat project as required and permit project-only logging (no work package). Confirm on the target instance whether you can create a time entry with only _links.project (no entity), and which is required.
- Exact default pageSize / max pageSize (instance-configurable; commonly 20 default). Verify on the live instance to size batched reporting pulls.
- Whether the spent_on filter accepts relative operators (t-, w, <>d) in your version and how time zones are applied for the boundaries of '<>d' date ranges.
- Whether hours is strictly required for non-ongoing entries in your version (schema default suggests required), or can be omitted; confirm by POSTing a minimal body against the live instance.
- Whether 'me' is accepted as a user_id filter value in your version (it works for many endpoints); otherwise resolve the current user's numeric id via /api/v3/users/me first.
- For 'Meeting' entities: whether your instance/version exposes meeting time logging (entity_type "Meeting") — depends on the meetings module being enabled.


---

# AREA: Custom fields (WorkPackageCustomField and project custom fields) in the OpenProject REST API v3

**Auth:** Same auth as the rest of API v3: HTTP Basic with username `apikey` and the user's API token, or OAuth2 Bearer. Reading a custom field value / custom option requires the relevant view permission (e.g. view_work_packages) in a project where that field is active; `/api/v3/custom_options/{id}` returns 404 if you lack that permission. CRITICAL: creating or managing custom-field DEFINITIONS is an admin-only, server-side operation that is NOT exposed over API v3 at all — there is no POST/PATCH/DELETE for custom fields. That must be done in the admin UI (/custom_fields) or via the Rails console (requires shell access to the server/container), not through any token. Setting custom field VALUES on work packages/projects goes through the normal WP create/update endpoints and needs edit_work_packages (or manage project attributes for project CFs).

## Endpoints

### GET /api/v3/work_packages/schemas/{project_id}-{type_id}
Read the WorkPackage schema for a given project+type to DISCOVER which custom fields exist, their human-readable names, data types, whether they are required/writable/hasDefault, and (for list/user/version types) their allowedValues. This is the primary way to map customFieldN -> meaning.
- **req:** Schema id is the composite string `{projectId}-{typeId}` (e.g. `3-1`). A custom field only appears here if it is enabled for that TYPE AND active in that PROJECT (both conditions). No body.
- **res:** _type:Schema. Each field is a top-level property keyed by name; custom fields use keys matching ^customField\d+$ where N is the CustomField record id. Each property object has: type (e.g. 'String','Formattable','Integer','Float','Date','Boolean','CustomOption','[]CustomOption','User','Version'), name (human label), required (bool), writable (bool), hasDefault (bool), and optionally location:'_links'. For link/list types there is a nested _links.allowedValues which is EITHER an inline array of {href,title} OR a single {href} pointing to a collection resource (client must handle both).

### GET /api/v3/work_packages/{id}/schema
Schema for an existing work package (resolves that WP's own project+type). Convenient when you have a WP id but not the type/project ids.
- **req:** No body. Also reachable by following _links.schema.href on a work package resource.
- **res:** Same Schema shape as the composite-id endpoint.

### GET /api/v3/work_packages/schemas
Collection of schemas; enumerate/filter multiple project-type schemas at once.
- **req:** Optional ?filters=[{"id":{"operator":"=","values":["3-1","3-2"]}}] (URL-encoded) to select specific schemas.
- **res:** HAL collection: _embedded.elements is an array of Schema resources; total/count/pageSize present.

### POST /api/v3/projects/{id}/work_packages/form
Best way to discover AND validate custom field keys/allowed values in-context before a real write. Dry-run: returns the schema and a payload skeleton without persisting.
- **req:** Body may be empty {} or a partial payload (e.g. set _links.type to force a type so its custom fields appear). Content-Type application/json. There is also POST /api/v3/work_packages/form for edits.
- **res:** _type:Form. _embedded.schema = full Schema (customFieldN definitions + allowedValues), _embedded.payload = pre-filled writable body you can modify and POST, _embedded.validationErrors surfaces field-level problems.

### POST /api/v3/projects/{id}/work_packages
Create a work package WITH custom field values in one call.
- **req:** Scalar CF types (string/int/float/date/bool/long-text) go at top level as customFieldN. Link CF types (single list, multi list, user, version) go under _links.customFieldN. Long-text CF value must be an object {"raw":"..."} (Formattable), not a bare string. Multi-value list = array of {href}. Must also set _links.type (and it must be a type the CF is enabled for) or the CF won't be accepted.
- **res:** 201 with the created WorkPackage; CF values echoed back as customFieldN scalars and/or _links.customFieldN {href,title}. Response includes lockVersion for subsequent PATCH.

### PATCH /api/v3/work_packages/{id}
Update custom field values on an existing work package (optimistic-locked).
- **req:** MUST include current lockVersion (integer) in the body or you get 409 Conflict. Set scalar CFs top-level (customFieldN); set link CFs under _links.customFieldN. To CLEAR a link CF send _links.customFieldN:{"href":null} (or [] for multi); clear a scalar with null.
- **res:** 200 with updated WorkPackage; lockVersion increments by one each successful write. 422 with _embedded.errors if a CF is not writable/active for the WP's project+type.

### GET /api/v3/custom_options/{id}
Resolve a single list-type custom option (the href targets used by list custom fields).
- **req:** id is the CustomOption record id. These ids are what appear in allowedValues hrefs and in _links.customFieldN for list CFs.
- **res:** { _type:'CustomOption', id, value (the display string), _links:{ self, customField } }. 404 if missing or no view permission.

### GET /api/v3/projects/{id}/schema
Discover PROJECT custom fields (projects have their own customFieldN attributes, separate from work packages).
- **req:** No body. Project resources also expose values as customFieldN (scalars top-level, links under _links).
- **res:** Schema resource listing project attributes incl. customFieldN with the same type/allowedValues conventions.

### GET /api/v3/custom_field_items/{id}
Read a single item of a HIERARCHY-format custom field (newer field_format). Read-only.
- **req:** id = hierarchy item id. Only relevant if a CF uses field_format 'hierarchy'. There is NO create/POST here.
- **res:** Hierarchy item read model (HAL). 403/404 on permission/missing.

## Gotchas
- The N in `customFieldN` is the CustomField's database record id, NOT a per-work-package index. If you create a field that lands at id 7, its key is `customField7` everywhere (payload, schema, _links).
- A custom field is only visible/settable on a work package if BOTH are true: (a) the field is enabled for that work package's TYPE, and (b) the field is active in that PROJECT (either is_for_all=true, or the project explicitly enables it). If either is missing, the field is absent from the schema and a PATCH/POST setting it yields 422 (or is ignored).
- Placement rule driven by the schema: scalar types (single-line string, int, float, date, bool, URL/link) go at the TOP LEVEL as customFieldN; reference types (single list, multi list, user, version) go under _links.customFieldN as {href} objects. The schema property's `location:'_links'` (and presence of _links.allowedValues) tells you which.
- Long-text custom fields (field_format 'text') are Formattable, not plain strings. Read: {format,raw,html}. Write: send an object {"raw":"**markdown**"} — sending a bare string fails.
- Multi-value list CFs take an ARRAY of link objects under _links (e.g. [ {href:.../custom_options/12}, {href:.../custom_options/13} ]); single-value list takes ONE link object. To clear: [] for multi, {"href":null} for single.
- allowedValues in a schema is polymorphic: an inline ARRAY of {href,title} for small enumerable sets (typical for list CFs -> /api/v3/custom_options/{id}), OR a single {href} link to a collection for large sets (e.g. user CFs). The CLI must branch on array-vs-object.
- List-type CF values reference /api/v3/custom_options/{id}. To build a write payload you need the option's id, not its text. Get ids from the schema's allowedValues, or from custom_options endpoint, or (server-side) cf.custom_options.pluck(:id,:value).
- Custom field DEFINITIONS cannot be created, edited, or deleted through API v3 — there is no endpoint. Only the admin UI (/custom_fields) or the Rails console/seed data can manage them. Don't design the CLI to 'create a custom field' via HTTP; expose a documented Rails-console recipe instead.
- PATCH requires the current integer lockVersion; it increments on every successful write; a stale value returns 409 Conflict. Fetch the WP (or use the form) to get the fresh lockVersion before writing.
- Dates for date-format CFs are ISO date-only strings 'YYYY-MM-DD' (no time component).
- Discovering CF keys from a bare work-package GET is unreliable because unset CFs may be omitted; use the schema or the form endpoint to get the authoritative, contextualized list of custom fields and their allowed values.

## Examples
```
# Discover custom fields for project 3 / type 1 (find customFieldN keys, names, types, allowedValues)
curl -u apikey:$OP_TOKEN 'https://op.example.com/api/v3/work_packages/schemas/3-1'
# then grep the JSON for keys matching ^customField[0-9]+$
```
```
// Illustrative Schema fragment showing each custom-field type
{
  "customField1": {"type":"String","name":"Ref code","required":false,"writable":true},
  "customField2": {"type":"Formattable","name":"Notes (long)","writable":true},
  "customField3": {"type":"Integer","name":"Story points"},
  "customField4": {"type":"Float","name":"Budget"},
  "customField5": {"type":"Date","name":"Go-live"},
  "customField6": {"type":"Boolean","name":"Billable"},
  "customField7": {"type":"CustomOption","name":"Severity","location":"_links",
     "_links":{"allowedValues":[
        {"href":"/api/v3/custom_options/12","title":"Low"},
        {"href":"/api/v3/custom_options/13","title":"High"}]}},
  "customField8": {"type":"[]CustomOption","name":"Tags","location":"_links",
     "_links":{"allowedValues":[{"href":"/api/v3/custom_options/20","title":"A"}]}},
  "customField9": {"type":"User","name":"Reviewer","location":"_links",
     "_links":{"allowedValues":{"href":"/api/v3/work_packages/available_assignees?..."}}},
  "customField10": {"type":"Version","name":"Target version","location":"_links"}
}
```
```
# Create a WP setting every custom-field kind at once
curl -u apikey:$OP_TOKEN -H 'Content-Type: application/json' -X POST \
  'https://op.example.com/api/v3/projects/3/work_packages' -d '{
  "subject": "CF demo",
  "customField1": "ABC-123",
  "customField2": { "raw": "**long** markdown text" },
  "customField3": 8,
  "customField4": 12500.50,
  "customField5": "2026-09-01",
  "customField6": true,
  "_links": {
    "type": { "href": "/api/v3/types/1" },
    "customField7": { "href": "/api/v3/custom_options/13" },
    "customField8": [ {"href":"/api/v3/custom_options/20"}, {"href":"/api/v3/custom_options/21"} ],
    "customField9": { "href": "/api/v3/users/14" },
    "customField10": { "href": "/api/v3/versions/3" }
  }
}'
```
```
# Update CF values on an existing WP (lockVersion required); clear the list CF
curl -u apikey:$OP_TOKEN -H 'Content-Type: application/json' -X PATCH \
  'https://op.example.com/api/v3/work_packages/1234' -d '{
  "lockVersion": 5,
  "customField3": 13,
  "_links": { "customField7": { "href": null } }
}'
```
```
# Rails console: CREATE a work-package custom field (NOT possible via API v3).
# Run inside the app container, e.g. docker compose exec web bundle exec rails runner '<code>'
cf = WorkPackageCustomField.create!(
  name: "Severity",
  field_format: "list",                       # string|text|int|float|date|bool|list|user|version|link|hierarchy
  possible_values: ["Low", "Medium", "High"], # creates CustomOption rows for list fields
  is_required: false,
  is_for_all: true,                            # active in every project (else assign projects explicitly)
  multi_value: false
)
# Make it appear on work packages by enabling it for the desired types:
Type.all.each { |t| t.custom_fields << cf unless t.custom_fields.include?(cf) }
puts "key = customField#{cf.id}"
cf.custom_options.pluck(:id, :value)          # -> option ids to use as /api/v3/custom_options/{id}
```
```
# Rails console: non-list field + project-scoped activation
cf = WorkPackageCustomField.create!(name: "Budget", field_format: "float", is_for_all: false)
Type.find(1).custom_fields << cf
Project.find(3).work_package_custom_fields << cf   # activate only in project 3
```

## Open questions (verify live)
- Confirm the exact schema `type` string emitted per field_format on the target OpenProject version (esp. long-text => 'Formattable', single list => 'CustomOption', multi list => '[]CustomOption', user => 'User', version => 'Version', URL/link => 'String') by inspecting a live schema JSON.
- Verify whether user-type CF allowedValues is an inline array or a single collection link on the live instance (affects how the CLI resolves choices).
- Confirm the Rails association names on the running version: t.custom_fields for types and project.work_package_custom_fields for project-scoped activation (older/newer versions may differ).
- Check whether the target version ships newer admin/project-custom-field mapping API endpoints; if so, some project-CF activation could be scriptable over HTTP instead of Rails.
- Verify whether hierarchy-format custom fields are in use and how their item hrefs (/api/v3/custom_field_items/{id}) are set as values.
- Confirm exact error/status behavior when setting a CF that is not enabled for the WP's type/project (422 with _embedded.errors vs silent drop) on the live instance.


---

# AREA: Notifications (in-app / IAN) — OpenProject REST API v3 (HAL+JSON)

**Auth:** Standard API v3 auth applies: HTTP Basic with username `apikey` and the user's API token as password, or OAuth2 Bearer token, or session cookie. All notification endpoints operate on the AUTHENTICATED user's own notifications only — there is no way to read or act on another user's notifications, and no project/admin permission grants cross-user access. An unauthenticated request yields 401; a request for a notification not belonging to the current user yields 404 (not 403). Collection GET/mark-all endpoints implicitly scope to the current user, so filters only narrow within that set. "IAN" = In-App Notification (as opposed to email/mail notifications), which is why the read-state property and action links are named readIAN/read_ian rather than plain read.

## Endpoints

### GET /api/v3/notifications
List the current user's in-app notifications (paginated, filterable, sortable, groupable).
- **req:** Query params (all optional): offset (integer, default 1, 1-based page number), pageSize (integer, default 20), sortBy (JSON, e.g. [["id","desc"]]; sortable columns: id, reason, readIAN), groupBy (string: "reason" or "project"), filters (JSON array, see request format below). Filters supported: id, project, readIAN, reason, resourceId, resourceType. Filter JSON format: [{ "fieldName": { "operator": "=", "values": [ ... ] } }]. Common examples: unread only -> [{"readIAN":{"operator":"=","values":["f"]}}]; by reason -> [{"reason":{"operator":"=","values":["mentioned","assigned"]}}]; by project id -> [{"project":{"operator":"=","values":["11"]}}]; scoped to a work package -> [{"resourceId":{"operator":"=","values":["77"]}},{"resourceType":{"operator":"=","values":["WorkPackage"]}}]. The filters value must be URL-encoded when placed in the query string. readIAN values are the string flags "t" (true=read) and "f" (false=unread), NOT true/false. reason values (enum): mentioned, assigned, responsible (accountable), watched, subscribed, commented, created, prioritized, processed, dateAlert (and scheduled). Operator "=" is the primary one used; "!" (not) also applies.
- **res:** 200 OK -> HAL Collection. Top-level fields: _type="Collection", total (total matching, ignoring pagination), count (number in this page), pageSize, offset, plus _embedded.elements = array of Notification resources. When groupBy is set, a groups array is added where each entry has value (the reason/project) and count. The collection also embeds _embedded.detailsSchemas (schemas describing the notifications' details properties, for client rendering). _links includes self, and templated jumpTo{offset}, changeSize{size}. 400/422 on malformed filters/sortBy; 403 if not permitted to view.

### GET /api/v3/notifications/{id}
Retrieve a single notification by its integer id (must belong to the current user).
- **req:** Path param id (integer). No query params. No body.
- **res:** 200 OK -> single Notification resource (HAL+JSON). Fields: _type="Notification", id, readIAN (bool), reason (string), createdAt, updatedAt. _embedded may contain actor (User), project (Project), activity (Activity), resource (e.g. WorkPackage), and details (array). _links: self, project, activity, actor, resource, details[], and exactly one of readIAN (present when currently unread) or unreadIAN (present when currently read) giving the toggle action href+method. 404 if the id does not exist or is not the current user's.

### GET /api/v3/notifications/{notification_id}/details/{id}
Retrieve a single detail (a Values::Property) attached to a notification, e.g. the changed date for a dateAlert.
- **req:** Path params: notification_id (integer), id (detail index/id, integer). No body.
- **res:** 200 OK -> a Values::Property-style detail resource with property/value. Rarely needed by a CLI; the details are also available embedded/linked from the notification itself.

### POST /api/v3/notifications/{id}/read_ian
Mark a single notification as read.
- **req:** Path param id (integer). No request body required (send empty body). No query params. Only allowed if the notification is currently unread (otherwise the readIAN action link is absent; calling it is a no-op/idempotent from a CLI's perspective).
- **res:** 204 No Content on success. No response body. 404 if not found/not owned. Re-fetch the notification (or the list) to see updated readIAN state.

### POST /api/v3/notifications/{id}/unread_ian
Mark a single notification as unread.
- **req:** Path param id (integer). No request body required (empty body). No query params.
- **res:** 204 No Content on success. No body. 404 if not found/not owned.

### POST /api/v3/notifications/read_ian
Mark ALL of the current user's notifications as read (mark-all-read), optionally narrowed by filters.
- **req:** No request body. Optional filters query param (SAME JSON format as GET list) to scope which notifications get marked, e.g. only for one project or one reason: ?filters=[{"reason":{"operator":"=","values":["mentioned"]}}] (URL-encoded). Without filters, every unread notification for the user is marked read. Filters here only reduce the implicit current-user collection.
- **res:** 204 No Content on success. No body. 400/422 on malformed filters.

### POST /api/v3/notifications/unread_ian
Mark the current user's notification collection as unread (mark-all-unread), optionally narrowed by filters.
- **req:** No request body. Optional filters query param (same format as list) to scope the operation. Without filters it applies to the whole (current-user) collection.
- **res:** 204 No Content on success. No body.

## Gotchas
- readIAN filter/property is BOOLEAN-encoded as strings "t"/"f", not JSON true/false. Unread = "f", read = "t". Getting this wrong silently returns the wrong set.
- The mark-single and mark-all endpoints return 204 No Content with an EMPTY body — do not try to parse JSON from the response. Update local state by re-fetching.
- read_ian / unread_ian are POST, and take NO request body. Any scoping for the collection variants goes in the `filters` QUERY parameter, not the body. This is unusual for a POST and easy to get wrong.
- The action links are named readIAN / unreadIAN in _links (camelCase) but the URL path segments are read_ian / unread_ian (snake_case). Only ONE of the two links is present on a given notification depending on current read state — prefer following the HAL link rather than constructing the path, so you naturally no-op when already in the target state.
- `filters` must be a JSON array serialized to a string AND URL-encoded when placed in the query string. Same for `sortBy` and `groupBy` value semantics.
- offset is 1-based (page number), NOT a zero-based record offset. pageSize default is 20; iterate pages until count*page reaches total (or until an element page is empty).
- resourceId and resourceType filters should be used TOGETHER — resourceId alone is ambiguous. resourceType is a class name string like "WorkPackage".
- The `resource` embedded/linked object is polymorphic (usually WorkPackage but can be other types); do not assume it is always a WorkPackage. Same for `project` (could be Project). Guard on _type.
- Notifications are strictly per-authenticated-user; there is no admin/global list endpoint and no way to mark another user's notifications. A wrong-owner id returns 404, not 403.
- reason enum spelling matters and is camelCase in values (e.g. dateAlert, not date_alert). Known values: mentioned, assigned, responsible, watched, subscribed, commented, created, prioritized, processed, dateAlert, scheduled. Treat unknown reasons gracefully as OpenProject adds new ones across versions.
- When groupBy is used the response adds a top-level `groups` array (value+count); elements are still returned. Don't assume grouping replaces elements.
- The collection embeds `detailsSchemas` to help render notification `details`; a simple CLI can ignore it, but it inflates response size.

## Examples
```
# List unread notifications, newest first (API key auth)
curl -u apikey:$OPENPROJECT_API_KEY \
  -G 'https://example.openproject.com/api/v3/notifications' \
  --data-urlencode 'filters=[{"readIAN":{"operator":"=","values":["f"]}}]' \
  --data-urlencode 'sortBy=[["id","desc"]]' \
  --data-urlencode 'pageSize=50' \
  --data-urlencode 'offset=1'
```
```
# List only @mention + assigned notifications in project 11
curl -u apikey:$OPENPROJECT_API_KEY \
  -G 'https://example.openproject.com/api/v3/notifications' \
  --data-urlencode 'filters=[{"reason":{"operator":"=","values":["mentioned","assigned"]}},{"project":{"operator":"=","values":["11"]}}]'
```
```
# Notifications for a specific work package (id 77)
curl -u apikey:$OPENPROJECT_API_KEY \
  -G 'https://example.openproject.com/api/v3/notifications' \
  --data-urlencode 'filters=[{"resourceId":{"operator":"=","values":["77"]}},{"resourceType":{"operator":"=","values":["WorkPackage"]}}]'
```
```
# Group unread by project
curl -u apikey:$OPENPROJECT_API_KEY \
  -G 'https://example.openproject.com/api/v3/notifications' \
  --data-urlencode 'filters=[{"readIAN":{"operator":"=","values":["f"]}}]' \
  --data-urlencode 'groupBy=project'
```
```
# Get one notification
curl -u apikey:$OPENPROJECT_API_KEY \
  'https://example.openproject.com/api/v3/notifications/1'
```
```
# Mark one as read (empty body, expect 204)
curl -u apikey:$OPENPROJECT_API_KEY -X POST \
  'https://example.openproject.com/api/v3/notifications/1/read_ian'
```
```
# Mark one as unread
curl -u apikey:$OPENPROJECT_API_KEY -X POST \
  'https://example.openproject.com/api/v3/notifications/1/unread_ian'
```
```
# Mark ALL as read (no filter -> everything)
curl -u apikey:$OPENPROJECT_API_KEY -X POST \
  'https://example.openproject.com/api/v3/notifications/read_ian'
```
```
# Mark all 'mentioned' notifications as read (filters go in the query string)
curl -u apikey:$OPENPROJECT_API_KEY -X POST -G \
  'https://example.openproject.com/api/v3/notifications/read_ian' \
  --data-urlencode 'filters=[{"reason":{"operator":"=","values":["mentioned"]}}]'
```
```
# Example single Notification resource (response of GET /notifications/1)
{
  "_type": "Notification",
  "id": 1,
  "readIAN": false,
  "reason": "mentioned",
  "createdAt": "2022-04-05T14:38:28.881Z",
  "updatedAt": "2022-04-06T09:03:24.591Z",
  "_embedded": {
    "actor":    {"_type": "User",        "id": 13, "name": "Darth Nihilus"},
    "project":  {"_type": "Project",     "id": 11, "name": "Jedi Remnant Locator"},
    "activity": {"_type": "Activity::Comment", "id": 180, "version": 3},
    "resource": {"_type": "WorkPackage", "id": 77, "subject": "Educate Visas Marr"}
  },
  "_links": {
    "self":      {"href": "/api/v3/notifications/1"},
    "readIAN":   {"href": "/api/v3/notifications/1/read_ian",   "method": "post"},
    "actor":     {"href": "/api/v3/users/13",        "title": "Darth Nihilus"},
    "project":   {"href": "/api/v3/projects/11",     "title": "Jedi Remnant Locator"},
    "activity":  {"href": "/api/v3/activities/180"},
    "resource":  {"href": "/api/v3/work_packages/77", "title": "Educate Visas Marr"}
  }
}
# Note: when read, the readIAN link is replaced by an unreadIAN link.
```
```
# Example Collection envelope (response of GET /notifications)
{
  "_type": "Collection",
  "total": 2,
  "count": 2,
  "pageSize": 20,
  "offset": 1,
  "_embedded": {
    "elements": [ /* Notification objects */ ],
    "detailsSchemas": [ /* schemas for details rendering */ ]
  },
  "_links": {
    "self":       {"href": "/api/v3/notifications?..."},
    "jumpTo":     {"href": "/api/v3/notifications?offset={offset}&...", "templated": true},
    "changeSize": {"href": "/api/v3/notifications?pageSize={size}&...", "templated": true}
  }
}
```

## Open questions (verify live)
- Confirm against the live instance whether the reason enum on your OpenProject version includes all of {mentioned, assigned, responsible, watched, subscribed, commented, created, prioritized, processed, dateAlert, scheduled} — the set has grown across releases (dateAlert/date alerts added in 12.x+). Fetch /api/v3/notifications and inspect distinct reason values, or check the queries filter schema.
- Verify the exact readIAN filter value encoding on your version: docs use "t"/"f" strings; confirm the instance also accepts them (some boolean filters historically accepted true/false). Test both against a live endpoint.
- Confirm whether mark-all read_ian/unread_ian truly return 204 with no body on your version (documented as 204) vs 200 with a Collection — behavior has been stable but worth a smoke test.
- Confirm the precise `groups` array shape when groupBy=reason|project (fields like value, count, _links) against the live instance, as the docs summarize rather than fully specify it.
- Check whether pagination for very large notification sets is capped by a server maxPageSize (common OpenProject setting) so the CLI must page rather than request a huge pageSize.
- Verify the resourceType filter accepts values beyond "WorkPackage" on your instance (e.g. news, wiki) and the exact class-name strings expected.


---

# AREA: Wiki pages, Attachments/file uploads, and File storages (Nextcloud/OneDrive file_links) — OpenProject API v3 (HAL+JSON)

**Auth:** Same auth as the rest of API v3: HTTP Basic with username `apikey` + the API token, or OAuth2 bearer. Per-operation permissions differ sharply: (1) Attachments: creating on a work package needs `edit work package` or `add work package`; containerless POST /api/v3/attachments needs any of edit/add work package, edit messages, or edit wiki pages in some project; deleting needs edit on the container (or being the author for containerless); wiki-page attachments need `edit wiki page`. (2) File links: GET list/single needs `view file links` (plus `view work package`); POST create and DELETE need `manage file links`. (3) Storages: GET needs `view file links`; POST/PATCH/DELETE storages and POST oauth_client_credentials require global `admin`. (4) prepare_upload (direct upload to Nextcloud/OneDrive) requires an Enterprise token in addition to `manage file links` — returns 500 MissingEnterpriseToken on Community edition. Per-user OAuth authorization to the storage is also required before file_links resolve (authorizationState must be Connected), independent of the API token.

## Endpoints

### GET /api/v3/wiki_pages/{id}
Retrieve a single wiki page. This is the ONLY wiki endpoint in v3.
- **req:** Path param id (integer). No filters, no body. There is NO collection endpoint (no GET /api/v3/wiki_pages and no GET /api/v3/projects/{id}/wiki_pages), and NO POST/PATCH/DELETE. You cannot create, edit, list, or delete wiki pages, and you cannot read or write the page BODY/TEXT via v3.
- **res:** WikiPage model is a documented STUB: only fields are id and title. _embedded.project and _links {self, project, attachments, addAttachment(method:post)}. No text/Formattable content field is exposed at all. 404 if not visible (needs 'view wiki page').

### POST /api/v3/work_packages/{id}/attachments
Upload/attach a file to a work package.
- **req:** Content-Type: multipart/form-data with EXACTLY two parts. Part 1 name=`metadata`, Content-Type application/json, body a single JSON object with required `fileName` and optional `description` (string; server treats description as Formattable). Part 2 name=`file`, Content-Type should match the file MIME type, body = raw bytes; a `filename` in that part's Content-Disposition is required by the parser but IGNORED (the metadata.fileName wins). Omitting either part -> 400 InvalidRequestBody. Omitting fileName or oversized file -> 422 PropertyConstraintViolation.
- **res:** 200 OK with an Attachment resource (see GET /api/v3/attachments/{id}).

### GET /api/v3/work_packages/{id}/attachments
List attachments belonging to a work package.
- **req:** Path param id. Returns a HAL Collection.
- **res:** 200 with _type Collection, total, count, _embedded.elements[] of Attachment. 404 if work package not visible.

### POST /api/v3/attachments
Containerless (a.k.a. prepared/claim-later) upload — create an attachment with no container, then attach it to a resource later.
- **req:** Same multipart/form-data shape as the work-package variant (metadata + file parts). Upload and later claim MUST be done by the same user. To claim: reference the returned attachment's self link in the target resource's _links.attachments on a create/update (e.g. include it when POSTing a new work package), or the resource's addAttachment. Once claimed it cannot be re-claimed.
- **res:** 200 with an Attachment whose _links.container is initially absent/null until claimed.

### GET /api/v3/attachments/{id}
Fetch a single attachment's metadata.
- **req:** Path param id.
- **res:** 200 Attachment: id, fileName, fileSize, description(Formattable: format/raw/html), status(enum), contentType, digest{algorithm,hash} (md5), createdAt. _links: self, container, author, downloadLocation (required), delete, and (when remote storage) staticDownloadLocation. status enum = uploaded | prepared | scanned | quarantined | rescan (virus-scan/direct-upload lifecycle).

### GET /api/v3/attachments/{id}/content
Download the raw file bytes.
- **req:** Do NOT hardcode this path. Read the attachment's _links.downloadLocation.href (may be a remote pre-signed S3/AWS URL when OpenProject uses external fog storage) and follow it; the static path /api/v3/attachments/{id}/content appears as staticDownloadLocation only for local storage. Expect a 302/redirect to remote storage.
- **res:** Binary file stream (or redirect to remote URL).

### DELETE /api/v3/attachments/{id}
Permanently delete an attachment.
- **req:** Path param id. No body. Needs edit on the container (or author for containerless).
- **res:** 204 No Content (empty body).

### POST /api/v3/wiki_pages/{id}/attachments
Attach a file to a wiki page (works even though wiki CRUD is unsupported).
- **req:** Same multipart metadata+file shape. Needs `edit wiki page`. Also POST /api/v3/activities/{id}/attachments, /api/v3/meetings/{id}/attachments, /api/v3/posts/{id}/attachments exist with the same shape.
- **res:** 200 Attachment.

### POST /api/v3/work_packages/{id}/file_links
Link one or more external storage files (Nextcloud/OneDrive) to a work package — the Nextcloud integration core operation.
- **req:** application/json (NOT multipart). Bulk insert, up to 20 elements, validated atomically (any invalid -> nothing created). Body: {"_type":"Collection","_embedded":{"elements":[{"originData":{"id":"<storage file id, REQUIRED, string>","name":"<REQUIRED>","mimeType":"image/png","size":433765,"createdAt":"...","lastModifiedAt":"...","createdByName":"...","lastModifiedByName":"..."},"_links":{"storageUrl":{"href":"https://host/"}}}]}}. Only originData.id and originData.name are mandatory; rest SHOULD be provided. The storage may be given either as _links.storageUrl.href (the storage host URL) OR _links.storage.href = /api/v3/storages/{id}. Empty mimeType = unknown; to link a FOLDER use mimeType `application/x-op-directory`. Idempotent: an existing link matching (originData.id, work package, storage) is returned unchanged rather than duplicated. Perm: manage file links.
- **res:** 201 with a FileLink Collection. 400 invalid body; 403 MissingPermission (manage file links); 404 wp not visible; 422 PropertyConstraintViolation (e.g. storage URL not registered on server).

### GET /api/v3/work_packages/{id}/file_links
List a work package's file links.
- **req:** Optional query `filters` (JSON) supporting only `storage`, e.g. filters=[{"storage":{"operator":"=","values":["42"]}}]. SIDE EFFECT: for each link the server does a live call to the storage origin to refresh metadata and the user's permission status — can be slow / can surface Error status per link.
- **res:** 200 FileLink Collection. Each FileLink: id, _type FileLink, createdAt, updatedAt, originData{...}, _embedded.storage, _links{self, storage, container, delete, staticOriginDownload(/api/v3/file_links/{id}/download), staticOriginOpen(/api/v3/file_links/{id}/open), permission status urn ViewAllowed|ViewNotAllowed|NotFound|Error}.

### GET /api/v3/file_links/{id}
Get a single file link.
- **req:** Path param id.
- **res:** 200 FileLink read model; 404 if not visible.

### DELETE /api/v3/file_links/{id}
Remove a file link (does not delete the file on the storage).
- **req:** Path param id, no body. Perm: manage file links.
- **res:** 200 OK.

### GET /api/v3/file_links/{id}/download
Get a direct download URL for the linked file.
- **req:** Path param id.
- **res:** 303 redirect (Location header) to the storage download URL.

### GET /api/v3/file_links/{id}/open
Get an 'open in storage' URL for the linked file.
- **req:** Path param id; optional query `location` to open the containing folder location.
- **res:** 303 redirect to the storage web UI URL.

### GET /api/v3/storages
List configured file storages.
- **req:** No required params. Tag is 'File links'.
- **res:** 200 Storage Collection. 400 on invalid filter.

### POST /api/v3/storages
Register a new storage (Nextcloud/OneDrive). Admin only.
- **req:** application/json StorageWriteModel. Required: _links.origin.href (storage host URL) and _links.type.href (urn:openproject-org:api:v3:storages:Nextcloud or :OneDrive). Optional: name, applicationPassword (Nextcloud only; string enables auto-managed project folders, null disables), _links.authenticationMethod.href (urn ...:authenticationMethod:TwoWayOAuth2 [default] or :OAuth2SSO), storageAudience/tokenExchangeScope (Nextcloud SSO). Side effect: OpenProject auto-creates a confidential OAuth2 PROVIDER application; the returned oauth client id and SECRET are shown ONLY on this response (secret hidden forever after).
- **res:** 201 StorageReadModel including the freshly created oauthApplication credentials in _embedded.

### GET /api/v3/storages/{id}
Get a storage; also probes live connection state.
- **req:** Path param id. Perm: view file links. SIDE EFFECT: opens a live connection to the origin to compute authorizationState.
- **res:** 200 StorageReadModel: id, name, configured(bool), createdAt/updatedAt, hasApplicationPassword (Nextcloud), tenantId/driveId (OneDrive), forbiddenFileNameCharacters. _links: self, type(urn Nextcloud|OneDrive), authenticationMethod(urn TwoWayOAuth2|OAuth2SSO), origin, open, authorizationState (urn ...authorization:Connected | FailedAuthorization | Error), authorize (present when FailedAuthorization — start OAuth cycle), oauthApplication & oauthClientCredentials (admin only).

### PATCH /api/v3/storages/{id}
Update a storage. Admin only.
- **req:** application/json StorageWriteModel (same fields as POST). Cannot change server-generated OAuth application data.
- **res:** 200 StorageReadModel.

### DELETE /api/v3/storages/{id}
Delete a storage and all dependents. Admin only.
- **req:** Path param id. Cascades: deletes the created oauth application, client, and ALL file links in this storage.
- **res:** 204 No Content.

### POST /api/v3/storages/{id}/oauth_client_credentials
Set the OAuth2 CLIENT credentials so OpenProject can act as an OAuth2 client against the external provider (e.g. the Nextcloud OAuth app). Admin only.
- **req:** application/json oauth_client_credentials_write_model (clientId, clientSecret). Calling again REPLACES existing credentials. This is step 2 of Nextcloud OAuth wiring after POST /storages.
- **res:** 201 StorageReadModel.

### GET /api/v3/storages/{id}/files
Browse files/folders in the storage (for building a file picker before creating file_links).
- **req:** Optional query `parent` = a directory file id; omit for document root, `/` for root on some providers. Non-directory parent -> 400.
- **res:** 200 StorageFiles collection (files + directories with ids used as originData.id when linking).

### POST /api/v3/storages/{id}/files/prepare_upload
Prepare a direct (credential-less) upload of a NEW file into the storage. Enterprise only.
- **req:** application/json {projectId(int, required), fileName(string, required), parent(string, required; use '/' for root)}. Perm: manage file links.
- **res:** 201 UploadLink: _type UploadLink, _links.destination.href = the direct upload URL the client then PUTs the bytes to (self link is a placeholder urn, one-time). 400 if parent is not a directory; 500 MissingEnterpriseToken on Community edition; 500 OutboundRequest:NotFound if the storage rejects.

### GET /api/v3/storages/{id}/open
Get a URL to open the storage in its web UI.
- **req:** Path param id.
- **res:** 303 redirect to storage web UI.

### GET /api/v3/project_storages
List project<->storage links (which storages are enabled in which projects).
- **req:** Optional query `filters` (JSON) supporting project_id, storage_id, storage_url, e.g. filters=[{"project_id":{"operator":"=","values":["42"]}},{"storage_id":{"operator":"=","values":["1337"]}}]. NOTE: use the PLURAL path /api/v3/project_storages (the response self links confirm this) even though the source YAML header comment mislabels it /api/v3/project_storage/{id}.
- **res:** 200 ProjectStorage collection.

### GET /api/v3/project_storages/{id}
Get a single project storage link.
- **req:** Path param id. Perm: view file links.
- **res:** 200 ProjectStorage: id, projectFolderMode (inactive | manual | automatic), createdAt/updatedAt, _links {self, creator, storage, project, projectFolder(StorageFile, only when mode manual/automatic), open, openWithConnectionEnsured(deprecated)}.

## Gotchas
- WIKI IS EFFECTIVELY UNAVAILABLE in v3: only GET /api/v3/wiki_pages/{id} exists, and the WikiPage model is an explicit STUB exposing just id + title. There is NO list endpoint, NO create/update/delete, and crucially NO way to read or write the wiki page body/markdown text. A CLI that needs wiki content must either scrape the HTML UI, use the wiki page ATTACHMENTS endpoint only, or accept that wiki is read-only-metadata. Do not promise wiki editing.
- Attachment upload is multipart/form-data with exactly two named parts `metadata` (application/json) and `file` (raw). The per-part Content-Disposition filename on the `file` part is required by the parser but ignored — the real name comes from metadata.fileName. Sending JSON in the body instead of multipart -> 400.
- Attachment create returns 200 (not 201). file_links create returns 201. storage create/oauth_client_credentials/prepare_upload return 201. Attachment/file_link/storage DELETE return 204 (storage), 200 (file_link), or 204 (attachment) respectively — status codes are inconsistent across resources, check each.
- Downloads: never hardcode /api/v3/attachments/{id}/content. Read _links.downloadLocation; with external (S3/fog) attachment storage it is a remote pre-signed URL and you must follow the redirect. staticDownloadLocation is only present for local storage.
- file_links create is idempotent on (originData.id, work package, storage): re-posting an existing link returns the existing one unchanged — you cannot use it to update metadata. To link a FOLDER, originData.mimeType MUST be application/x-op-directory.
- GET file_links and GET storages/{id} both make live outbound calls to the storage origin as a side effect (to refresh metadata / compute authorizationState). These can be slow or return per-link Error/ViewNotAllowed status; handle timeouts and partial-permission states.
- Direct upload to a storage (prepare_upload) and OneDrive support require an Enterprise token — Community edition returns 500 MissingEnterpriseToken. file_links themselves (linking existing files) work on Community.
- Storage OAuth secret is shown ONCE: the oauth client secret in the POST /api/v3/storages response is never retrievable again. A CLI must capture and store it at creation time.
- Registering a storage does NOT enable it in a project. The v3 API only exposes GET for project_storages (no documented POST/PATCH/DELETE), so linking a storage to a project + choosing project folder mode is done in the admin/project UI, not via API.
- filters query param is a URL-encoded JSON array of single-key objects: [{"<field>":{"operator":"=","values":["<id>"]}}]. file_links supports only the `storage` filter; project_storages supports project_id, storage_id, storage_url.
- Before file_links resolve for a user, that user must complete the per-user OAuth authorization to the storage (authorizationState must become Connected). If FailedAuthorization, the storage exposes an `authorize` link to start the OAuth cycle; until then links return ViewNotAllowed/Error.

## Examples
```
# Upload a file to a work package (multipart, two parts)
curl -u apikey:$OP_TOKEN -X POST \
  https://op.example.com/api/v3/work_packages/1234/attachments \
  -F 'metadata={"fileName":"report.pdf","description":{"raw":"Q3 report"}};type=application/json' \
  -F 'file=@/local/path/report.pdf;type=application/pdf'
```
```
# Containerless upload, then claim on work-package creation
curl -u apikey:$OP_TOKEN -X POST https://op.example.com/api/v3/attachments \
  -F 'metadata={"fileName":"logo.png"};type=application/json' \
  -F 'file=@logo.png;type=image/png'
# -> note returned _links.self.href (e.g. /api/v3/attachments/55), reference it in the new WP body under _links.attachments
```
```
# Download following the HAL link (handles remote storage redirect)
DL=$(curl -s -u apikey:$OP_TOKEN https://op.example.com/api/v3/attachments/55 | jq -r '._links.downloadLocation.href')
curl -L -u apikey:$OP_TOKEN "https://op.example.com$DL" -o out.bin
```
```
# Link a Nextcloud file to a work package (bulk collection body)
curl -u apikey:$OP_TOKEN -X POST \
  -H 'Content-Type: application/json' \
  https://op.example.com/api/v3/work_packages/1234/file_links \
  -d '{"_type":"Collection","_embedded":{"elements":[{"originData":{"id":"5503","name":"logo.png","mimeType":"image/png"},"_links":{"storage":{"href":"/api/v3/storages/42"}}}]}}'
```
```
# List a WP's file links filtered by storage id
curl -u apikey:$OP_TOKEN -G https://op.example.com/api/v3/work_packages/1234/file_links \
  --data-urlencode 'filters=[{"storage":{"operator":"=","values":["42"]}}]'
```
```
# Register a Nextcloud storage (admin) — capture the one-time oauth secret
curl -u apikey:$OP_TOKEN -X POST -H 'Content-Type: application/json' \
  https://op.example.com/api/v3/storages \
  -d '{"name":"Team NC","_links":{"origin":{"href":"https://nextcloud.example.com"},"type":{"href":"urn:openproject-org:api:v3:storages:Nextcloud"}}}'
```
```
# Set OpenProject's OAuth2 client credentials against the storage (admin)
curl -u apikey:$OP_TOKEN -X POST -H 'Content-Type: application/json' \
  https://op.example.com/api/v3/storages/42/oauth_client_credentials \
  -d '{"clientId":"<from-nextcloud>","clientSecret":"<from-nextcloud>"}'
```
```
# Prepare a direct upload into a storage (Enterprise only)
curl -u apikey:$OP_TOKEN -X POST -H 'Content-Type: application/json' \
  https://op.example.com/api/v3/storages/42/files/prepare_upload \
  -d '{"projectId":11,"fileName":"newfile.txt","parent":"/"}'
# -> 201 { _type: UploadLink, _links: { destination: { href: <PUT bytes here> } } }
```

## Open questions (verify live)
- Confirm the exact project_storages route on a live instance: the source YAML header comments say /api/v3/project_storage/{id} (singular) but the example self links and collection use /api/v3/project_storages (plural). Test GET /api/v3/project_storages and /api/v3/project_storages/{id} against the target version.
- Verify whether ANY write operation for project_storages exists on the running version (linking a storage to a project). v3 docs only expose GET; if a POST/PATCH/DELETE /api/v3/project_storages exists it is undocumented — otherwise project<->storage linking must be done in the UI.
- Confirm the multipart `metadata.description` shape accepted by the running server: docs show plain string in some places and a Formattable object elsewhere; test whether description must be a string or {"raw":"..."}.
- Confirm behavior of attachment `status` values (prepared/scanned/quarantined/rescan) on the target instance — these depend on whether antivirus scanning and remote/direct-upload attachment storage are configured; a plain Docker instance may only ever return `uploaded`.
- Confirm the exact oauth_client_credentials_write_model field names (clientId/clientSecret) against the live schema — fetch /api/v3/storages/{id}/oauth_client_credentials or the oauth_client_credentials_write_model.yml if precise field casing matters.
- Verify Enterprise-token gating for prepare_upload and OneDrive on the specific edition being targeted; on Community, plan for 500 MissingEnterpriseToken and restrict the CLI to link-existing-file flows.
- Check pagination params on the collection endpoints (storages, file_links, project_storages) — standard v3 offset/pageSize likely apply but were not shown in these specs; confirm _embedded.elements/total/count and whether pageSize is honored.


---

# AREA: Costs, budgets & reporting for invoicing (per person / per project) in OpenProject API v3

**Auth:** All endpoints use the standard API v3 auth: HTTP Basic with username `apikey` and the user's API token as password (`curl -u apikey:TOKEN`), or OAuth2 / session cookie. Authorization is per-project and permission-gated, which matters a lot here: (1) `GET /api/v3/time_entries` requires `view_time_entries` (or `view_own_time_entries`) in the projects concerned. (2) Budgets need `view_budgets`. (3) Cost entries need `view_cost_entries` or `view_own_cost_entries` and the project's Costs module enabled (else 404). (4) MONEY visibility on work packages is gated separately: `laborCosts` needs `view_time_entries` + (`view_hourly_rates` or `view_own_hourly_rate`); `materialCosts`/`costsByType` need cost-entry perms + `view_cost_rates`; `overallCosts` needs both. A token whose user lacks the rate-view permissions will simply not see the cost properties in the WorkPackage payload (they are omitted, not zeroed). For invoicing across all users, use an admin/PM token that holds `view_time_entries` and `view_hourly_rates` (not just the "own" variants) in every billable project.

## Endpoints

### GET /api/v3/time_entries
THE primary endpoint for invoicing. List/filter time bookings; group client-side by user + project + month to get billable hours.
- **req:** Query params: `filters` (URL-encoded JSON array), `offset` (1-based PAGE number, default 1), `pageSize` (default per instance, typically 20; max configurable ~100-200), `sortBy` (e.g. [["spent_on","asc"]]). Filter keys (snake_case identifiers): `spent_on` (date filter, supports operator `<>d` between two ISO dates — ideal for a month range; also `=d`, `>=`/`<=` variants), `user_id`, `project_id`, `activity_id`, `entity_type` (values ["WorkPackage"] or ["Meeting"]), `entity_id`, `ongoing`, `created_at`, `updated_at`. NOTE: legacy `work_package_id` filter is gone — filter by work package via entity_type=WorkPackage + entity_id. No auth-side lockVersion needed for reads.
- **res:** HAL OffsetPaginatedCollection: top-level `total`, `count`, `pageSize`, `offset`, `_links.self/nextByOffset/prevByOffset/changeSize/jumpTo/createTimeEntry`, and `_embedded.elements[]` of TimeEntry. Each TimeEntry: `id`, `hours` (ISO8601 duration string e.g. "PT8H30M"), `spentOn` (date), `comment` (formattable, plain), `ongoing`, `createdAt`, `updatedAt`, optional `startTime`/`endTime`; `_links.user`, `_links.project`, `_links.activity`, `_links.entity` (+ deprecated `_links.workPackage`). CRITICAL: NO monetary/cost/rate field is rendered here. Collection has NO sums — you must sum `hours` client-side. Paginate until offset*pageSize >= total.

### POST /api/v3/time_entries
Create a time entry (log time).
- **req:** JSON body with properties + `_links`. Required: `hours` (ISO8601 e.g. "PT4H"), `spentOn` ("2026-07-01"), `_links.project` OR `_links.entity` (WorkPackage/Meeting; project is derived from entity), `_links.activity` (/api/v3/time_entries/activities/{id}). Optional: `_links.user` (defaults to current user; setting another user needs permission), `comment` as {"raw":"..."}. Use GET /api/v3/time_entries/form or /api/v3/time_entries/schema to discover writable/required fields.
- **res:** 201 with the created TimeEntry representer (same shape as list element). No lockVersion involved.

### GET|PATCH|DELETE /api/v3/time_entries/{id}
Show / update / delete a single time entry.
- **req:** PATCH takes a partial TimeEntry JSON (same shape as POST). TimeEntry has NO optimistic-locking lockVersion (unlike WorkPackages) — do not send lockVersion. Update/delete gated by UpdateContract (own vs others' entries).
- **res:** TimeEntry representer; the representer advertises `_links.updateImmediately` (PATCH), `_links.update` (POST to form), `_links.delete` when allowed.

### GET /api/v3/time_entries/activities
Lookup time-entry activity IDs (e.g. Development, Management) needed as the `activity` link when creating entries and useful to segment billable vs non-billable.
- **req:** Also `/api/v3/time_entries/activities/{id}` for one. No filters needed.
- **res:** Collection of TimeEntriesActivity: id, name, position, default, _links.self.

### GET /api/v3/work_packages/{id}
The ONLY way to read computed MONEY out of API v3. When Costs module is enabled and the token has rate-view perms, the WorkPackage payload includes cost aggregates.
- **req:** Standard WP GET. Cost fields appear conditionally on permissions (see auth_summary). You can also list many at once via GET /api/v3/work_packages?filters=... (filter by project, and there is a `spentOn`/`spent_on`-style is not on WP; filter by project/assignee/updatedAt instead).
- **res:** Adds (permission-gated): `spentTime` (ISO8601 duration, total logged hours on the WP), `laborCosts`, `materialCosts`, `overallCosts` — all rendered as LOCALE-FORMATTED CURRENCY STRINGS via number_to_currency (e.g. "$1,200.00" / "1.200,00 €"), NOT numeric; `costsByType` (embedded summarized units by cost type); `_links.budget`. These are per-work-package aggregates ACROSS ALL USERS — they do NOT break down per person, and the numeric value must be parsed out of the formatted string.

### GET /api/v3/budgets/{id}
Retrieve a single budget. Effectively a stub.
- **req:** Path id integer > 0. Requires `view_budgets`. 404 if Costs module disabled on the budget's project.
- **res:** Very limited representer: `id`, `subject` only, plus `_links.self`, `_links.staticPath` (HTML path), and attachments. NO monetary amounts (planned/labor/material budget totals are NOT exposed). Read-only — no POST/PATCH/DELETE.

### GET /api/v3/projects/{id}/budgets
List budgets defined in a project.
- **req:** Requires `view_budgets` on the project.
- **res:** HAL collection with `_embedded.elements[]` of Budget (each only id+subject as above), `total`, `count`.

### GET /api/v3/cost_entries/{id}
Retrieve a single (material/unit) cost entry from the Costs module.
- **req:** Requires `view_cost_entries`, or `view_own_cost_entries` if it is the caller's own entry. There is NO top-level collection endpoint (no `GET /api/v3/cost_entries` list).
- **res:** CostEntry representer: `id`, `spentUnits` (numeric units), `spentOn`, `createdAt`, `updatedAt`; `_links.project`, `_links.user`, `_links.costType`, `_links.entity` (+ deprecated `_links.workPackage`). CRITICAL: NO money amount (the entry's `costs`/`overridden_costs` monetary value is NOT rendered).

### GET /api/v3/work_packages/{id}/cost_entries
List the cost (unit) entries booked on a specific work package.
- **req:** Requires `view_cost_entries`/`view_own_cost_entries` on the WP's project.
- **res:** HAL collection of CostEntry (units only, no money), with `total`/`count`.

### GET /api/v3/work_packages/{id}/summarized_costs_by_type
Aggregated unit totals per cost type for one work package.
- **req:** Requires cost-entry view permission.
- **res:** Collection of AggregatedCostEntry: each has `spentUnits` and `_links.costType`. Units only — still no money value.

### GET /api/v3/cost_types/{id}
Lookup a cost type (unit definitions).
- **req:** Requires cost-entry view perms in any project. No collection endpoint — only by id.
- **res:** CostType representer: `id`, `name`, `unit`, `unitPlural`, `isDefault`. NO rate/price is exposed.

## Gotchas
- MONEY IS NOT IN time_entries OR cost_entries. Neither the TimeEntry nor the CostEntry representer renders any monetary amount or rate. Time entries give hours only; cost entries give units only. Do not expect a `costs` field there.
- HourlyRate is NOT in API v3. There is no endpoint to read a user's hourly rate (per user / per project / historical rate periods). The HourlyRate model exists only in the DB/Rails. Confirmed by the OpenProject community (topic 13912) and by the absence of any HourlyRate representer/endpoint in source. The `view_hourly_rates` permission exists, but only gates the already-computed `laborCosts` currency string on work packages.
- The Cost Reports / reporting module (the UI cost report query builder, CostQuery) has ZERO API v3 endpoints (verified: no OpenProjectAPI mounts and no CostQuery classes under lib/api). It is Rails/UI-only. You cannot drive cost reports over REST.
- The only computed money the API exposes is WorkPackage.laborCosts / materialCosts / overallCosts / costsByType and WorkPackage.spentTime — and (a) they are permission-gated and simply OMITTED if the token lacks view_hourly_rates/view_cost_rates, (b) they are LOCALE-FORMATTED CURRENCY STRINGS (number_to_currency), not numbers, so you must parse them, and (c) they are per-work-package totals across ALL users, giving NO per-person split.
- Budgets are read-only and near-empty: only id + subject. No planned amount, no labor/material budget, no spent-vs-planned. No create/update via API.
- No top-level cost_entries collection: you can only GET a cost entry by id or list them per work package. There is no month/user filter for cost entries in the API.
- `hours` and `spentTime` are ISO8601 durations (e.g. "PT8H30M"), not decimals — parse with a duration parser and convert to decimal hours before billing math.
- `offset` in pagination is a 1-based PAGE NUMBER, not a row offset. Loop pages while offset*pageSize < total. The time_entries collection has no `sums`, so aggregate client-side.
- Filters must be a URL-encoded JSON array; each element is {"<key>":{"operator":"<code>","values":[...]}}. Multiple filters are AND-ed. For a month use spent_on with operator `<>d` and two ISO dates: values ["2026-07-01","2026-07-31"]. Values are always strings/arrays of strings.
- Time-entry filter keys are snake_case (`spent_on`, `user_id`, `project_id`, `activity_id`, `entity_type`, `entity_id`) — do NOT use the camelCase work-package filter names here. The legacy `work_package_id` filter was removed; use entity_type=WorkPackage + entity_id.
- TimeEntry has no lockVersion/optimistic locking (only WorkPackages do). Don't send lockVersion on PATCH /api/v3/time_entries/{id}.
- Costs module must be enabled per project or budget/cost endpoints 404. Check the project's enabled modules first.
- The `workPackage` link on time/cost entries is deprecated in favor of `entity` (which can be a WorkPackage or a Meeting). Read `_links.entity`, but keep `_links.workPackage` as a fallback for older instances.

## Examples
```
# Billable hours for ONE user in July 2026 (group/sum the returned hours client-side)
FILTERS='[{"spent_on":{"operator":"<>d","values":["2026-07-01","2026-07-31"]}},{"user_id":{"operator":"=","values":["3"]}}]'
curl -u apikey:YOUR_TOKEN -G 'https://op.example.com/api/v3/time_entries' \
  --data-urlencode "filters=$FILTERS" \
  --data-urlencode 'pageSize=200' \
  --data-urlencode 'offset=1' \
  --data-urlencode 'sortBy=[["spent_on","asc"]]'
```
```
# All time entries for a project in a month (then group by _links.user client-side)
FILTERS='[{"spent_on":{"operator":"<>d","values":["2026-07-01","2026-07-31"]}},{"project_id":{"operator":"=","values":["5"]}}]'
curl -u apikey:YOUR_TOKEN -G 'https://op.example.com/api/v3/time_entries' \
  --data-urlencode "filters=$FILTERS" --data-urlencode 'pageSize=200'
```
```
# URL-encoded filter form actually sent on the wire (spent_on month + user):
# /api/v3/time_entries?filters=%5B%7B%22spent_on%22%3A%7B%22operator%22%3A%22%3C%3Ed%22%2C%22values%22%3A%5B%222026-07-01%22%2C%222026-07-31%22%5D%7D%7D%2C%7B%22user_id%22%3A%7B%22operator%22%3A%22%3D%22%2C%22values%22%3A%5B%223%22%5D%7D%7D%5D&pageSize=200
```
```
# One element of _embedded.elements[] (note: hours is a duration, no money):
{
  "_type": "TimeEntry",
  "id": 42,
  "hours": "PT8H",
  "spentOn": "2026-07-03",
  "comment": { "format": "plain", "raw": "Feature work", "html": "Feature work" },
  "_links": {
    "self": { "href": "/api/v3/time_entries/42" },
    "project": { "href": "/api/v3/projects/5", "title": "Acme Website" },
    "user": { "href": "/api/v3/users/3", "title": "Jane Dev" },
    "activity": { "href": "/api/v3/time_entries/activities/1", "title": "Development" },
    "entity": { "href": "/api/v3/work_packages/77", "title": "Login page" }
  }
}
```
```
# Create a time entry (POST /api/v3/time_entries)
curl -u apikey:YOUR_TOKEN -H 'Content-Type: application/json' \
  -X POST 'https://op.example.com/api/v3/time_entries' -d '{
    "spentOn": "2026-07-03",
    "hours": "PT4H",
    "comment": { "raw": "Implementation work" },
    "_links": {
      "project":  { "href": "/api/v3/projects/5" },
      "entity":   { "href": "/api/v3/work_packages/77" },
      "user":     { "href": "/api/v3/users/3" },
      "activity": { "href": "/api/v3/time_entries/activities/1" }
    }
  }'
```
```
# Read computed money for a work package (only source of $ in API v3; needs view_hourly_rates)
curl -u apikey:YOUR_TOKEN 'https://op.example.com/api/v3/work_packages/77'
# -> payload includes when permitted:
#   "spentTime": "PT40H", "laborCosts": "$4,000.00", "materialCosts": "$0.00",
#   "overallCosts": "$4,000.00", plus _links.budget and embedded costsByType.
# NOTE: these are per-WP totals across all users and are locale-formatted strings.
```
```
# Recommended CLI aggregation (pseudocode) — hours from API, rates from local config:
#   entries = paginate(GET /api/v3/time_entries, filters=[spent_on <>d month, project_id?])
#   for e in entries:
#       key = (e._links.user.href, e._links.project.href)
#       agg[key].hours += iso8601_to_hours(e.hours)
#   for (user, project), row in agg:
#       rate = rate_table[(user, project)]   # maintained in CLI config/DB, NOT from API
#       row.amount = row.hours * rate
# Produces per-person, per-project billable totals for the invoice.
```

## Open questions (verify live)
- Confirm max allowed `pageSize` on the target instance (default cap is instance-configurable; commonly 100-200). If capped low, expect many pages for a busy month.
- Verify on the live instance whether `laborCosts`/`overallCosts` currency strings use the instance locale/currency you expect, and settle on a robust parser (strip currency symbol + thousands separators; handle both "1,200.00" and "1.200,00").
- Confirm the exact required-vs-optional set for POST /api/v3/time_entries on your version by GETting /api/v3/time_entries/schema (activity may be required or default to the project's default activity; user defaults to caller).
- Confirm whether the instance still renders the deprecated `_links.workPackage` on time/cost entries or only `_links.entity` (version-dependent), so the CLI reads the right field.
- Decide the source of truth for hourly rates since the API cannot supply them: a CLI-side rate table (user x project x effective date) vs. direct read-only DB access to the `rates`/`hourly_rates` tables vs. exporting the cost report from the UI. If historical/period-based rates matter, a rate table with effective-date ranges is needed to match OpenProject's own behavior.
- Verify whether your billable/non-billable distinction maps cleanly onto TimeEntry activities (or a custom field on time entries), so filtering/segmentation for invoices is correct.
- Check whether time-entry custom fields exist on the instance (the representer injects them dynamically) in case invoice metadata is stored there.


---

# COMPLETENESS CRITIQUE

# Completeness Critique: OpenProject API v3 Research

## 0. Scope gaps — entire required areas are MISSING or truncated
The CLI brief names 11 areas; research covers ~8. Absent or unusable:
- **Wiki** — zero research. Critical unknown: API v3 historically had NO write support for wiki pages (GET `/api/v3/wiki_pages/{id}` only, create/update via API was unsupported for years). Must verify whether POST/PATCH wiki even exists on the target version — this may be a hard blocker for the wiki feature.
- **Attachments / Nextcloud** — zero research, yet the prompt explicitly names multipart attachments as a top pitfall. Missing: the multipart POST flow (`metadata` JSON part + `file` part), `/api/v3/work_packages/{id}/attachments`, `/api/v3/attachments/{id}`, `/attachments/{id}/content` download, the **direct-upload** (prepare→upload→finalize) path for large files, and the Nextcloud **storages / file_links** endpoints (`/api/v3/work_packages/{id}/file_links`, `/api/v3/storages`). This is the biggest hole.
- **Per-person cost reporting** — only *time* entries are covered. **Cost** entries, cost types, budgets, and **hourly rates** are not researched. Per-person cost is impossible without rates, and API v3 coverage of the costs module is thin — verify whether cost_entries/rates are exposed at all.
- **Notifications** — the JSON is **truncated mid-sentence** ("Collection GET/mark-all endpoints…"). No usable endpoints (`GET /api/v3/notifications`, mark read/unread, mark-all-read, `readIAN` filter, reasons) survived. Treat as not delivered.

## 1. Contradictions between areas
- **Per-project WP endpoints: deprecated vs. recommended.** The Work Packages area says `/api/v3/projects/{id}/work_packages[/form]` are DEPRECATED (prefer global + project filter). The Custom Fields area *recommends and uses those exact deprecated paths* for create/form. Pick one; align examples.
- **Default-filter trap stated in only one area.** Search area: omitting `filters` injects `status=open`, so you must send `filters=[]` for all statuses. The Work Packages list area documents `filters` with no such warning — a dev reading only that area will "lose" closed WPs.
- **`available_responsibles`.** Assignees area: definitively removed in 14.0, use `available_assignees` for both. WP area: "some versions also expose `/available_responsibles`." Reconcile to the 14.0 statement (version-guarded).
- **available_assignees location.** Assignees area centers on project-level `/api/v3/projects/{id}/available_assignees`; WP area cites per-WP `/api/v3/work_packages/{id}/available_assignees`. Both exist but serve different scopes — the research never says which to use when. Clarify: project-level for create, WP-level when a WP already exists.
- **Project schema endpoint mismatch.** Projects area lists only `/api/v3/projects/schema` (global, deprecated → `/workspaces/schema`). Custom Fields area asserts a **per-project** `/api/v3/projects/{id}/schema` for discovering project CFs — this endpoint is not corroborated and may not exist; project-attribute discovery is normally via the project **form** endpoint. Verify before relying on it.

## 2. Missing endpoints/fields a CLI genuinely needs
- **Name→id resolution lists are undocumented.** Payloads require `_links` to `/api/v3/statuses/{id}`, `/types/{id}`, `/priorities/{id}`, `/versions/{id}`, categories — but the **list** endpoints to discover those ids are never given: `GET /api/v3/statuses`, `/api/v3/types` (and `/api/v3/projects/{id}/types`), `/api/v3/priorities`, `/api/v3/projects/{id}/versions`, `/api/v3/projects/{id}/categories`. Without these the CLI can't turn user-supplied names into hrefs.
- **Time/cost aggregation.** `time_entries` has **no groupBy/showSums** (unlike work_packages queries) — per-person/per-project totals must be summed client-side, and `hours` must be parsed from ISO-8601 durations to add. Not stated; reporting design depends on it.
- **Versions endpoint** — referenced as a CF/WP link target but never documented (`GET /api/v3/projects/{id}/versions`, `/api/v3/versions/{id}`).
- **Attachment/file-link endpoints** (see §0).
- **Global error envelope + 429 rate limiting** — no coverage of the standard `Error`/`ErrorCollection` shape parsing beyond ad-hoc notes, and no mention of rate limits/retry.
- **DELETE for comments** — flagged as unknown; the CLI's "delete comment" verb may be unimplementable via API.

## 3. Claims that MUST be verified against the live instance first
- **Auth viability**: `apiv3_enable_basic_auth=true`, personal-API-token creation enabled, and whether the instance forces login (anonymous fallback vs 401). Any of these can break `apikey:` Basic auth entirely — verify with `GET /users/me` at startup.
- **Filter key casing** (camelCase `assignee/createdAt/customField5` vs snake_case `assigned_to/created_at`) — explicitly uncertain, and it **differs by endpoint**: `time_entries` filters are snake_case (`user_id`, `project_id`, `entity_type`) with **no `work_package_id`**, while WP filters are camelCase. Pull exact names from `/api/v3/queries/schema` and `/time_entries/schema`; don't assume uniformity.
- **customFieldN ids/types** — instance-specific; discover via schema/form. The N is the DB record id, not an index.
- **`lockVersion` increment-by-1 and the 409-retry pattern** — self-labeled "model-knowledge (unverified)." Verify actual increment behavior and 409 body.
- **`me` as a filter value** for user_id/assignee/author/watcher — used in examples but unconfirmed; else resolve numeric id via `/users/me`.
- **`description.format`** (markdown vs textile) — read from schema, don't hardcode.
- **time_entry `_links.entity` vs `_links.project` requiredness** — dev schema vs published docs disagree; test project-only logging.
- **Activities pagination** — whether `/work_packages/{id}/activities` honors offset/pageSize or dumps all.
- **available_assignees returns Groups** — some versions return Users only (affects group-assignment feature).
- **projects/workspaces path split** (`/projects/{id}/queries/*` vs `/workspaces/{id}/*`, `/projects/schema` vs `/workspaces/schema`, `available_assignees` alias) — version-dependent; probe both.
- **Max/default pageSize** — repeatedly unknown; needed to size batched pulls.
- **`/api/v3/projects/{id}/schema`** existence (§1).

## 4. Highest-probability implementation pitfalls
- **lockVersion is WP-only and asymmetric.** Required in the PATCH body for work packages (409 on stale). **Not used** by projects, users, memberships, groups, roles, time_entries, or activities/comments — and **not** by WP sub-writes (watchers POST, relations POST). Over-applying it (e.g., sending it on a time-entry or project PATCH) or omitting it on WP PATCH are both easy bugs.
- **HAL `_links` placement is inconsistent across write bodies** — the top trap:
  - Resource refs (project/type/status/priority/assignee/responsible/parent/category/version, and reference-type custom fields) go under `_links` as `{"href":…}`; scalars (subject, dates, `percentageDone`, `estimatedTime`, scalar CFs) at root.
  - **Exceptions to memorize**: watcher add = `{"user":{"href":…}}` (root key `user`, NOT under `_links`); relation = `type` scalar at root + `_links.to`; membership `roles` = **array** under `_links` that **replaces** the whole set; group `members` = array that **replaces**; clearing a link = `{"href":null}`, clearing a multi-list = `[]`; long-text/Formattable CFs write `{"raw":…}` not a bare string.
- **Filter encoding.** URL-encoded JSON **array of single-key objects**, AND-only (OR only within one field's `values`), **values always arrays of strings** (even ids/bools: `"7"`, `"t"`), no-arg operators need `values:null`. `filters=[]` disables the default open-status filter. **Stored queries use a different shape** (HAL `QueryFilterInstance` with `_links.filter/operator/values`) than the compact query-param form — mixing them fails silently.
- **Multipart attachments (unresearched, will bite).** Upload is `multipart/form-data` with a JSON `metadata` part (`{"fileName":…, "description":…}`) plus the binary `file` part — NOT a JSON body. Large files may require the direct-upload prepare/finalize dance. This must be researched before the attachments verb is built; it is the pitfall most likely to stall implementation.

**Also latent:** ISO-8601 duration handling (`estimatedTime`, time-entry `hours` — decimals rejected; must convert 2.5→`PT2H30M` both ways); pagination `offset` is a 1-based **page**, not a row offset (consistent across areas — good, but easy to misread).