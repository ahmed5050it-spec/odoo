# microsoft_calendar (Outlook Calendar) — Architecture Brief

> Module `microsoft_calendar`, display name **"Outlook Calendar"** (`odoo/addons/microsoft_calendar/`).
> A two-way synchronization connector that keeps Odoo's calendar in step with a user's
> Outlook / Microsoft 365 calendar over OAuth2 + the **Microsoft Graph** REST API. `depends =
> [microsoft_account, calendar]`. It owns no real business object: one sync-state mixin
> (`microsoft.calendar.sync`), a reset wizard, and token/state extensions on `res.users` /
> `res.users.settings`; it extends `calendar.event` and `calendar.recurrence`. 2 routes,
> ~7.0k Python LOC. `application = false`, `auto_install = false`. This is integration
> plumbing on top of the `calendar` capability — the sibling of `google_calendar` — not a
> capability of its own.

## 1. Role & Classification

- **value_model: support** (Stabell & Fjeldstad). Calendar-sync integration infrastructure
  extending `calendar`; it transforms nothing and produces no sellable output. Its job is to
  bridge an existing capability to an external SaaS — a firm-infrastructure / support function.
- **activity_class: support.**
- **apqc_category: 8.0 Manage Information Technology.** The module's reason to exist is
  external-system integration (gap #7 — it talks to `graph.microsoft.com` and
  `login.microsoftonline.com`), OAuth credential lifecycle, and cross-system data
  reconciliation: IT-management concerns.
- **Why this departs from the parent/baseline.** `calendar` is classified **13.0 Develop and
  Manage Business Capabilities** (it owns the scheduling capability); the auto-architect baseline
  for this module inherited 13.0. This child owns the IT plumbing that integrates that capability
  with a third party, which is exactly **8.0**. 13.0 was rejected (nothing here develops a new
  capability — it operates an external interface); 9.0 Acquire/Manage Assets was rejected (no
  physical/IT asset, only an API connection). Matches the `google_calendar` sibling.

## 2. IT Architecture

- **Application:** microsoft_calendar — Outlook / Microsoft 365 two-way sync connector.
- **Software services (routes):** 2. `/microsoft_calendar/sync_data` (jsonrpc, auth=user) triggers
  a sync and returns a status (`need_config_from_admin` / `need_auth` / `need_refresh` /
  `no_new_event_from_microsoft` / …) plus an auth URL; `/microsoft_account/authentication`
  (http, auth=public, from `microsoft_account`) is the OAuth2 redirect callback.
- **Data objects:** `microsoft.calendar.sync` (AbstractModel mixin), `calendar.event` /
  `calendar.recurrence` (extended with `microsoft_id` / `ms_universal_event_id` / `need_sync_m`),
  `microsoft.calendar.account.reset`.
- **Information flows:** outbound Odoo→`graph.microsoft.com` (insert/patch/delete/answer events,
  *after_commit*); inbound `calendarView/delta` (`$deltatoken`) + `events/{id}/instances`→Odoo;
  OAuth code→`login.microsoftonline.com` token endpoint→tokens on `res.users`; cron every 12h
  iterates connected users; Teams videocall link ⇄ `videocall_location`.

## 3. Data Model (the ERM)

| _name | role | #fields | key relations |
|-------|------|---------|---------------|
| `microsoft.calendar.sync` | AbstractModel **mixin** (sync state) | 4 | — (`microsoft_id`, `ms_universal_event_id`, `need_sync_m`, `active`) |
| `calendar.event` | extension, inherits the mixin | +1 | `recurrence_id`→`calendar.recurrence`, `user_id`→`res.users` |
| `calendar.recurrence` | extension, inherits the mixin | +1 | `calendar_event_ids`→`calendar.event` |
| `microsoft.calendar.account.reset` | TransientModel wizard | 3 | `user_id`→`res.users` |
| `res.users` | extension (OAuth token store) | +3 | `microsoft_calendar_rtoken`/`token`/`token_validity` |
| `res.users.settings` | extension (sync state) | +3 | `sync_token` + `synchronization_stopped` + `last_sync_date` |

- The central abstraction is the **`microsoft.calendar.sync` mixin**: it grafts two ids
  (`microsoft_id`, the per-calendar event id used as the API path; `ms_universal_event_id`, the
  cross-calendar `iCalUId` used to match the same event between users/recurrences) plus
  `need_sync_m` onto both events and recurrences, so the same insert/patch/delete machinery serves
  both. Unlike `google_calendar`, the **OAuth tokens live on `res.users`** (not `res.users.settings`);
  only the sync token + flags are mirrored via `related` into `res.users.settings`.
- Field distribution is attribute-heavy and tiny (mostly Char/Boolean/Datetime tokens + flags);
  the module's weight is in *behavior* (~7.0k LOC), not in its schema.

## 4. Behavior & Surfaces

- **OAuth2 token flow (code-read).** Consent URL built for scope
  `offline_access openid Calendars.ReadWrite` with `access_type=offline` against
  `login.microsoftonline.com/.../oauth2/v2.0/authorize` (to obtain a refresh_token); the callback
  POSTs the code to the v2.0/token endpoint for access+refresh tokens, stored on `res.users`
  (group `base.group_system`, blacklisted from session_info). Expired access tokens are lazily
  refreshed; a 400/401 invalid-grant wipes the tokens and raises a `UserError`.
- **Two-way sync (code-read).** `res.users._sync_microsoft_calendar` pulls remote changes, runs
  `_sync_microsoft2odoo` (create/update/cancel Odoo records, **last-modified-wins** via
  `lastModifiedDateTime` vs `write_date`), then `_sync_odoo2microsoft` (insert/patch/delete to
  Graph). Deleting/cancelling reconciles both sides; `_check_old_event_update_required` guards
  against re-mailing old events on sub-second drift.
- **Deferred writes (code-read).** `@after_commit` fires the Graph HTTP call only after the Odoo
  transaction commits (fresh cursor), preventing duplicate creation on rollback; the insert writes
  back `microsoft_id` + `iCalUId` and clears `need_sync_m`; a failed patch/delete keeps
  `need_sync_m` set for retry. Request timeout via `microsoft_calendar.graph_timeout` (default 5s).
- **Delta sync, no webhook (code-read).** `microsoft_calendar_sync_token` (Graph `$deltatoken`)
  drives incremental `calendarView/delta` pulls; occurrences are re-fetched per `seriesMaster` via
  `/instances` for their `iCalUId`; first run does a full sync windowed to ±`range_days`
  (default 365); a 410 `fullSyncRequired`/`SyncStateNotFound` raises `InvalidSyncToken` → full
  resync. Driven by cron `ir_cron_sync_all_cals` (every 12h) + the on-demand route — no push/watch
  channel. **Outlook anti-spam guard:** recurrence create/update/delete is forbidden from Odoo
  while sync is active (`_forbid_recurrence_creation`/`_forbid_recurrence_update`) — must be done
  in Outlook.
- **External integration (gap #7, static).** Hand-rolled `requests` client to two allow-listed
  Microsoft hosts; admin supplies `cal_microsoft_client_id` (public) + `client_secret`
  (ir.config_parameter, never returned in clear). Videocall links provisioned via **Microsoft Teams**
  (`isOnlineMeeting` / `teamsForBusiness` / `teams.microsoft.com`). No vendored SDK.
- **Frontend:** 3 JS files, no OWL components; patches the calendar view
  (`AttendeeCalendarController/Model/CommonPopover.prototype`) to surface the Outlook connect/sync UX.
- **Security posture:** 1 access rule (reset wizard → `base.group_system`); 0 record rules, 0 new
  groups. Authorization gated by `base.group_erp_manager` + configured credentials.

## 5. Value-Configuration Classification

Support. `depends = [microsoft_account, calendar]`, no document chain, no sellable output. It mediates
between Odoo and an external calendar service — but as **infrastructure for one capability**, not as a
multi-party marketplace, so it is "support", not "network". Primary-vs-support role: **support** (it
enables the calendar capability to interoperate with Microsoft 365).

## 6. APQC PCF Hint

**8.0 Manage Information Technology** — develop/manage IT integration and data interoperability with an
external service (OAuth2 + Microsoft Graph REST sync). Deliberately distinct from the parent's 13.0
(which owns the scheduling capability itself), and identical to the `google_calendar` sibling.

## 7. How to Drive It

Use the **run-odoo** skill (`odoo shell`):

```python
env['res.users'].browse(uid)._get_microsoft_sync_status()       # sync_active | sync_paused | sync_stopped
env['res.users'].browse(uid).check_synchronization_status()     # {'microsoft_calendar': 'missing_credentials'|'sync_active'|...}
env['calendar.event']._get_microsoft_records_to_sync(full_sync=True)   # pending Odoo -> Microsoft work
env['res.users']._sync_all_microsoft_calendar()                 # the 12h cron entry point (all connected users)
```

Route: `curl` jsonrpc `/microsoft_calendar/sync_data` with `{model: 'calendar.event'}` (auth=user) →
returns `status` (`need_config_from_admin` / `need_auth` / `need_refresh` / `no_new_event_from_microsoft`).
External endpoint exercised: `https://graph.microsoft.com/v1.0/me/calendarView/delta`.

## 8. Open Questions

- Precedence/edge cases when the Outlook organizer is a non-syncing Odoo user vs a non-Odoo email
  (`_check_organizer_validation` + `_recreate_event_different_organizer` branch).
- How `_is_microsoft_insertion_blocked` + `_get_event_user_m` decide *whose* token sends an event whose
  organizer differs from the editor (an attendee must not insert on behalf of the owner).
- Whether the per-attendee `id` vs `iCalUId` handling in `_microsoft_attendee_answer` /
  `_sync_recurrence_microsoft2odoo` fully prevents duplicate/mismatched Outlook events across every
  recurrence path.

---
*Provenance: `extract_module.py` + `extract_frontend.py` facts (`facts/microsoft_calendar.facts.json`,
`frontend/microsoft_calendar.frontend.json`); behavioral notes from code-read of `models/microsoft_sync.py`,
`models/res_users.py`, `models/calendar.py`, `controllers/main.py`, `utils/microsoft_calendar.py`,
`microsoft_account/models/microsoft_service.py`. Odoo 19.0.*
