# auth_timeout — Architecture Brief

> Module: `auth_timeout` · Category: Hidden/Tools · Depends: `auth_totp`, `auth_totp_mail`, `auth_passkey`, `bus` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/auth_timeout.facts.json` · Frontend: `doc/revres/frontend/auth_timeout.frontend.json`

## 1. Summary

`auth_timeout` is **IT security infrastructure** — it expires idle and long-lived web
sessions and forces the user to re-confirm their identity (or fully log in again). It
hangs entirely off the request dispatcher: on every authenticated request `ir.http`
compares the current time against two configurable thresholds — a hard **maximum
session age** (`lock_timeout` vs the session's `create_time`) and an **inactivity
period** (`lock_timeout_inactivity` vs a `identity-check-next` deadline). A breached age
raises `SessionExpiredException` (full re-login); a breached inactivity raises the
module's `CheckIdentityException`, which pops a screen-lock dialog asking for password /
TOTP / passkey, optionally with MFA step-up. It owns **no business object** (`models: 0`):
all behaviour is grafted onto `ir.http`, `ir.websocket`, `res.groups`, `res.users` and
`auth_totp.device`, plus transient HTTP-session keys. ~1229 Python LOC, **5 routes**,
`auto_install: false`.

## 2. Structure (evidence)

- **Models (0 own; 5 `_inherit`):** `ir.http` (the dispatch gate), `ir.websocket`
  (presence-driven inactivity stamping), `res.groups` (**12 fields** — the timeout
  configuration), `res.users` (timeout resolvers), `auth_totp.device` (age capping).
- **Routes (5; 3 real + re-routes):** `/auth-timeout/check-identity` (HTTP page),
  `/auth-timeout/session/check-identity` (jsonrpc — receive the re-auth form),
  `/auth-timeout/send-totp-mail-code` (jsonrpc — email-OTP), plus a re-routed
  `/web/webclient/load_menus` (`check_identity=False`, exempting the bare `fetch`).
- **Security:** 0 access rules, 0 record rules, 0 groups — policy is expressed as
  **fields on `res.groups`**, not as ACLs.
- **Views:** none (the group timeout config UI ships as inherited form views; the only
  client surface is the OWL screen-lock dialog).

## 3. Frontend (gap #3) & Integrations (gap #7)

Client footprint is a small OWL surface: **1 JS file, 1 QWeb template, 2 OWL components**
(`CheckIdentityDialog`, `CheckIdentityForm`), **3 registry adds** —
`error_handlers:checkIdentityErrorHandler` (catches `CheckIdentityException` over rpc and
pops the dialog instead of erroring), `public_components:auth_timeout.check_identity_form`
(the standalone page), and `services:check_identity`. Bundles touched:
`web.assets_backend`=1, `web.assets_frontend`=2, `web.assets_tests`=1. The web client also
reads `lock_timeout_inactivity` injected into `session_info`/`get_frontend_session_info`
to run the inactivity countdown locally. Integrations (gap #7): **no outbound HTTP, no
SDK imports, 0 external endpoints, `uses_api_keys: false`** — purely internal.

## 4. Behavior (beyond metadata)

- **Dispatch gate** (`ir.http._authenticate` → `_must_check_identity`): after
  `super()._authenticate`, for any `auth='user'` route it resolves the user's timeouts and
  walks two thresholds — `lock_timeout` vs session `create_time`, `lock_timeout_inactivity`
  vs `identity-check-next`. A breached age returns `{logout:True}` → `SessionExpiredException`
  (redirect to `/web/login`); breached inactivity returns `{check_identity:True}` →
  `CheckIdentityException` (a `SessionExpiredException` subclass, DEBUG loglevel) unless the
  route set `check_identity=False`. **Expiry is lazy** — enforced on the next request, not
  by a background job. (code-read)
- **Activity stamping** (`ir.http._set_session_inactivity` ← `ir.websocket`): inactivity is
  tracked via the **bus websocket presence channel**, not an HTTP last-seen timestamp.
  `_update_mail_presence` forwards the JS-reported `inactivity_period`; when inactive it
  writes `session['identity-check-next'] = now + timeout - inactivity_period` and persists
  via `root.session_store.save` (websocket requests don't auto-save). `_on_websocket_closed`
  forces it (`force=True`) so closing the last tab arms the deadline immediately. (code-read)
- **Configurable timeouts** (`res.groups` + `_get_lock_timeouts`): timeouts are **per access
  group, not per user and not a single system parameter** — `lock_timeout`,
  `lock_timeout_mfa`, `lock_timeout_inactivity`, `lock_timeout_inactivity_mfa` (minutes).
  The `@ormcache('self._ids')` resolver folds all implied groups into the **shortest**
  timeout per type as `(seconds, requires_mfa)` tuples; `create/write/unlink` clear the cache
  on change. UI defaults: 1 day + MFA for session age, 15 min no-MFA for inactivity. (code-read)
- **Re-auth completion** (`_check_identity` + `_handle_error`): HTTP errors redirect to the
  `/auth-timeout/check-identity` page; rpc errors surface as the dialog. With no credential it
  returns `_get_auth_methods` (webauthn/totp/totp_mail/password); with one it runs
  `_check_credentials`, optionally steps up to a second factor (`identity-check-1fa`), and on
  success pops `identity-check-next` + stamps `identity-check-last`. `auth_totp.device` age is
  capped to the shortest MFA session timeout so "remember me" can't outlive policy. (code-read)
- **Frontend (static):** `CheckIdentityDialog`/`CheckIdentityForm`, a `check_identity` service,
  the `checkIdentityErrorHandler`, and a public-component registration for the standalone page;
  1 JS + 1 QWeb template across the backend/frontend/tests bundles. (static)

## 5. IT architecture

- **Application:** session inactivity / max-age timeout layered on the web request dispatch.
- **Software services:** `/auth-timeout/check-identity` (page), `/auth-timeout/session/check-identity`
  (jsonrpc re-auth), `/auth-timeout/send-totp-mail-code` (jsonrpc email-OTP), `/web/webclient/load_menus`
  (re-routed exempt).
- **Data objects:** none — behaviour lives in `ir.http`/`ir.websocket`/`res.groups`/`res.users`
  extensions and transient session keys.
- **Information flows:** stamp (presence → `_set_session_inactivity` → `identity-check-next`);
  gate (every request → `_must_check_identity`); logout (`SessionExpiredException` → `/web/login`);
  lock (`CheckIdentityException` → page/dialog); re-auth (`_check_identity` → `_check_credentials`
  + MFA step-up); config (`res.groups` → `_get_lock_timeouts` ormcache → `session_info`).

## 6. Business architecture

- **Capabilities (inferred):** inactivity timeout (auto screen-lock); max session age / forced
  re-login; lazy identity re-confirmation; step-up MFA re-auth; group-scoped policy config;
  presence-driven inactivity tracking; trusted-device age capping.
- **Value streams (inferred):** Idle-to-Locked (presence → deadline → next request → dialog →
  re-auth); Aged-to-Relogin (`create_time` exceeded → redirect → full login); Policy-to-Enforcement
  (admin sets group timeout → cache rebuilt → members gated).
- **Information concepts (auto):** `res.groups` timeout policy; session deadline keys
  (`create_time`, `identity-check-next/last/1fa`); resolved per-user `(seconds, mfa)` tuples.
- **Organization/Products (auto):** none.
- **Policies (inferred):** group-scoped, **shortest-wins**; two independent thresholds (age vs
  idle); each may require MFA; lazy at-dispatch enforcement; per-route `check_identity=False`
  opt-out; trusted-device lifetime capped to session policy.
- **Metrics (inferred):** groups with timeouts configured; `CheckIdentityException`/
  `SessionExpiredException` frequency; shortest effective timeout per user.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** Session-lifecycle hardening (Porter support activity; Stabell &
  Fjeldstad "support"). It owns **no business object** (`models: 0` — pure extensions + session
  keys), creates no document chain, and holds no customer/order/product/ledger data. Its only job
  is to expire idle/long-lived sessions across the platform every module sits behind. Hence not
  chain/shop/network.
- **APQC: 8.0 Manage Information Technology.** This is the "Develop and manage IT security,
  privacy and data protection" / identity & access management capability — the concrete build/run
  of an access control (inactivity + max-age timeout, MFA step-up, group-scoped policy) wired into
  the dispatcher. **11.0 "Manage Enterprise Risk, Compliance, …"** was considered (auto-lock
  supports unattended-session mandates) but rejected: 11.0 is the governance layer (risk registers,
  control frameworks, audits), whereas `auth_timeout` is the technical *implementation* IT operates.
  No row exists in `apqc_odoo_map.tsv` (it enumerates primary chain/shop activities only); aligned
  with the sibling `auth_totp` record (8.0/support).

## 8. Fit-to-Standard

- **Standard:** inactivity timeout (auto screen-lock) after a configurable idle period; maximum
  session age forcing full re-login; optional MFA step-up reusing `auth_totp`/`auth_totp_mail`/
  `auth_passkey` factors; group-scoped policy with shortest-applicable resolution; presence-driven
  tracking over the bus websocket with immediate arming on tab/connection close; screen-lock OWL
  dialog (rpc) + server-rendered page (plain HTTP); trusted-device age capped to the MFA timeout;
  per-route `check_identity=False` opt-out.
- **Typical fits:** lock unattended back-office sessions after N idle minutes; force a daily
  re-login on sensitive groups (1-day default + MFA); require a second factor on admin-group
  timeout; stricter timeouts for admin/finance groups (shortest-wins).
- **Common gaps:** per-group only (no per-user / global system-parameter timeout); lazy enforcement
  (an idle tab locks only on its next request); idle detection depends on websocket presence; no
  built-in audit log/report of lock & forced-logout events; no per-user timeout UI.
- **Drive hints:** `env['res.users'].browse(2)._get_lock_timeouts()`; set `group_system.lock_timeout_inactivity=1`
  then read `_get_lock_timeout_inactivity()`; `env['ir.http']._must_check_identity()` in a request
  context; `curl -i .../auth-timeout/check-identity`; idle a backend tab past the timeout → screen-lock.
