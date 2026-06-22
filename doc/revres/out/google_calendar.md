# google_calendar (Google Calendar) — Architecture Brief

> Module `google_calendar`, display name **"Google Calendar"** (`odoo/addons/google_calendar/`).
> A two-way synchronization connector that keeps Odoo's calendar in step with a user's
> Google Calendar over OAuth2 + the Google Calendar v3 REST API. `depends = [google_account,
> calendar]`. It owns no real business object: one sync-state mixin (`google.calendar.sync`),
> a reset wizard, and token/state extensions on `res.users` / `res.users.settings`; it
> extends `calendar.event` and `calendar.recurrence`. 2 routes, ~6.0k Python LOC.
> `application = false`, `auto_install = false`. This is integration plumbing on top of the
> `calendar` capability — not a capability of its own.

## 1. Role & Classification

- **value_model: support** (Stabell & Fjeldstad). Calendar-sync integration infrastructure
  extending `calendar`; it transforms nothing and produces no sellable output. Its job is to
  bridge an existing capability to an external SaaS — a firm-infrastructure / support function.
- **activity_class: support.**
- **apqc_category: 8.0 Manage Information Technology.** The module's reason to exist is
  external-system integration (gap #7 — it talks to `googleapis.com` and `accounts.google.com`),
  OAuth credential lifecycle, and cross-system data reconciliation: IT-management concerns.
- **Why this departs from the parent.** `calendar` is classified **13.0 Develop and Manage
  Business Capabilities** (it owns the scheduling capability). This child owns the IT plumbing
  that integrates that capability with a third party, which is exactly **8.0**. 13.0 was
  rejected (nothing here develops a new capability — it operates an external interface); 9.0
  Acquire/Manage Assets was rejected (no physical/IT asset, only an API connection).

## 2. IT Architecture

- **Application:** google_calendar — Google Calendar two-way sync connector.
- **Software services (routes):** 2. `/google_calendar/sync_data` (jsonrpc, auth=user) triggers
  a sync and returns a status (`need_config_from_admin` / `need_auth` / `need_refresh` / …) plus
  an auth URL; `/google_account/authentication` (http, auth=public, from `google_account`) is the
  OAuth2 redirect callback.
- **Data objects:** `google.calendar.sync` (AbstractModel mixin), `calendar.event` /
  `calendar.recurrence` (extended with `google_id` / `need_sync`), `google.calendar.account.reset`.
- **Information flows:** outbound Odoo→`www.googleapis.com` (insert/patch/delete events,
  *after_commit*); inbound `events.list` (syncToken delta)→Odoo; OAuth code→
  `accounts.google.com` token endpoint→tokens on `res.users.settings`; cron every 12h iterates
  connected users.

## 3. Data Model (the ERM)

| _name | role | #fields | key relations |
|-------|------|---------|---------------|
| `google.calendar.sync` | AbstractModel **mixin** (sync state) | 3 | — (`google_id`, `need_sync`, `active`) |
| `calendar.event` | extension, inherits the mixin | +3 | `recurrence_id`→`calendar.recurrence`, `user_id`→`res.users` |
| `calendar.recurrence` | extension, inherits the mixin | +0 | `calendar_event_ids`→`calendar.event` |
| `google.calendar.account.reset` | TransientModel wizard | 3 | `user_id`→`res.users` |
| `res.users.settings` | extension (token store) | +6 | OAuth `rtoken`/`token`/`token_validity` + `sync_token` |

- The central abstraction is the **`google.calendar.sync` mixin**: it grafts `google_id` +
  `need_sync` onto both events and recurrences, so the same insert/patch/delete machinery serves
  both. `res.users` mirrors the token fields via `related` into `res.users.settings`.
- Field distribution is attribute-heavy and tiny (mostly Char/Boolean/Datetime tokens + flags);
  the module's weight is in *behavior* (~6.0k LOC), not in its schema.

## 4. Behavior & Surfaces

- **OAuth2 token flow (code-read).** Consent URL built for scope
  `https://www.googleapis.com/auth/calendar` with `access_type=offline` + `approval_prompt=force`
  (to obtain a refresh_token); the callback POSTs the code to `accounts.google.com/o/oauth2/token`
  for access+refresh tokens, stored on `res.users.settings` (group `base.group_system`, blacklisted
  from session_info). Expired access tokens are lazily refreshed; invalid_grant wipes the tokens.
- **Two-way sync (code-read).** `res.users._sync_google_calendar` pulls remote events, runs
  `_sync_google2odoo` (create/update/cancel Odoo records, **last-updated-wins** via `gevent.updated`
  vs `write_date`), then `_sync_odoo2google` (insert/patch/delete to v3, ≤200 records/txn). Deleting
  an Odoo event **archives** it so the deletion can propagate.
- **Deferred writes (code-read).** `@after_commit` fires the Google HTTP call only after the Odoo
  transaction commits (fresh cursor), preventing duplicate creation on rollback; 400/403 errors set
  `need_sync=False` and post a note to the event chatter.
- **Delta sync, no webhook (code-read).** `google_calendar_sync_token` (Google `nextSyncToken`) drives
  incremental pulls; first run does a full sync windowed to ±`range_days` (default 365); a 410
  `fullSyncRequired` raises `InvalidSyncToken` → full resync. Driven by cron `ir_cron_sync_all_cals`
  (every 12h) + the on-demand route — there is no Google push/watch channel.
- **External integration (gap #7, static).** Hand-rolled `requests` client to two allow-listed Google
  hosts; admin supplies `google_calendar_client_id` (public) + `client_secret` (ir.config_parameter,
  masked in logs). No vendored SDK.
- **Frontend:** 3 JS files, no OWL components; patches the calendar view
  (`AttendeeCalendarController/Model/CommonPopover.prototype`) to surface the Google connect/sync UX.
- **Security posture:** 1 access rule (reset wizard → `base.group_system`); 0 record rules, 0 new
  groups. Authorization gated by `base.group_erp_manager` + configured credentials.

## 5. Value-Configuration Classification

Support. `depends = [google_account, calendar]`, no document chain, no sellable output. It mediates
between Odoo and an external calendar service — but as **infrastructure for one capability**, not as a
multi-party marketplace, so it is "support", not "network". Primary-vs-support role: **support** (it
enables the calendar capability to interoperate).

## 6. APQC PCF Hint

**8.0 Manage Information Technology** — develop/manage IT integration and data interoperability with an
external service (OAuth2 + REST sync). Deliberately distinct from the parent's 13.0 (which owns the
scheduling capability itself).

## 7. How to Drive It

Use the **run-odoo** skill (`odoo shell`):

```python
env['res.users'].browse(uid)._get_google_sync_status()    # sync_active | sync_paused | sync_stopped
env['calendar.event']._check_any_records_to_sync()         # pending Odoo -> Google work
env['res.users']._sync_all_google_calendar()               # the 12h cron entry point (all connected users)
```

Route: `curl` jsonrpc `/google_calendar/sync_data` with `{model: 'calendar.event'}` (auth=user) →
returns `status` (`need_config_from_admin` / `need_auth` / `need_refresh` / `no_new_event_from_google`).
External endpoint exercised: `https://www.googleapis.com/calendar/v3/calendars/primary/events`.

## 8. Open Questions

- Precedence/edge cases when the Google organizer is a non-syncing Odoo user vs a non-Odoo email
  (`extendedProperties` shared-vs-private branch in `_google_values`).
- How `_is_google_insertion_blocked` + `_get_event_user` decide *whose* token sends an event whose
  organizer differs from the editor.
- Whether `_handle_allday_recurrences_edge_case` fully prevents duplicate Google events across every
  recurrence path.

---
*Provenance: `extract_module.py` + `extract_frontend.py` facts (`facts/google_calendar.facts.json`,
`frontend/google_calendar.frontend.json`); behavioral notes from code-read of `models/google_sync.py`,
`models/res_users.py`, `models/calendar.py`, `controllers/main.py`, `utils/google_calendar.py`,
`google_account/models/google_service.py`. Odoo 19.0.*
