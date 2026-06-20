# auth_passkey — Architecture Brief

> Module: `auth_passkey` · Category: Hidden/Tools · Depends: `base_setup`, `web` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/auth_passkey.facts.json` · Frontend: `doc/revres/frontend/auth_passkey.frontend.json`

## 1. Summary

`auth_passkey` is **IT security / identity-and-access infrastructure** — it adds
**WebAuthn/FIDO2 passwordless login** to Odoo. A user registers a passkey held in a
platform authenticator (Touch ID / Windows Hello / Android) or a roaming security key
(YubiKey); thereafter they log in by signing a server-issued challenge instead of typing
a password. The same machinery backs **step-up re-authentication** (the identity-check
dialog). It owns **no business object of its own**: 1 persistent model (`auth.passkey.key`,
the FIDO2 credential), 1 transient registration wizard, plus a One2many + auth hooks
grafted onto `res.users` and a `webauthn` method added to `res.users.identitycheck`. It
is `auto_install: true` and depends only on `base_setup`/`web`, so it sits beneath every
other module. Notably, the **private key never reaches the server** — only the public
key, credential id, and a sign counter are stored.

## 2. Structure (evidence)

- **Models:** `auth.passkey.key` (the credential: `name`, `credential_identifier`,
  `public_key`, `sign_count`, `create_uid` — the last three `groups='base.group_system'`);
  `auth.passkey.key.create` (TransientModel — the registration ceremony wizard); plus an
  extension of `res.users` adding `auth_passkey_key_ids` (One2many) + `_login`/
  `_check_credentials`/`_get_session_token` hooks; and `res.users.identitycheck` gaining a
  `webauthn` `auth_method`.
- **Routes (1):** `/auth/passkey/start-auth` — **public jsonrpc**, issues a one-shot
  WebAuthn authentication challenge for `navigator.credentials.get`.
- **Security:** 5 access rules, **3 record rules**, 0 groups. Users manage only their own
  passkeys (`create_uid` scoping); the raw credential material is `base.group_system`-only.
- **Views:** 2 forms + 1 kanban (the passkey list on the user form, the create/rename
  dialogs). No list/search/graph — the UX is form/kanban + browser-side ceremony JS.

## 3. Frontend (gap #3) & Integrations (gap #7)

Client-heavy by necessity (the WebAuthn ceremony runs in the browser): **3 JS files, 0
OWL components proper, 3 registry adds, 0 services, 0 patches**, plus
`static/src/lib/simplewebauthn.js` (the SimpleWebAuthn helper wrapping
`navigator.credentials`). The registry adds are the `public.interactions:auth_passkey.passkey_login`
login Interaction and two view-registry `FormController` overrides
(`auth_passkey_key_create_view_form`, `auth_passkey_identity_check_view_form`). Bundles:
`web.assets_backend`=3, `web.assets_frontend`=2, `web.assets_tests`=1. Integrations
(gap #7): **no outbound HTTP, no SDK imports, `uses_api_keys: false`**; the only flagged
"files" are the in-tree vendored `_vendor/webauthn/.../verify_*_response.py` (the FIDO2
relying-party library shipped inside the module — **no external python dependency**).

## 4. Behavior (beyond metadata)

- **Credential record** (`auth.passkey.key`): `credential_identifier` (base64url, UNIQUE),
  COSE `public_key`, monotonic `sign_count` — all `group_system`-only. `public_key` is a
  pseudo-field: declared `compute`/`inverse` but actually stored in a raw `varchar` column
  added in `init()` via `ALTER TABLE`, read/written with hand-written SQL (invisible to the
  ORM cache). The private key never touches the server. `unlink()` audit-logs every
  deletion with login/id/REMOTE_ADDR. (code-read)
- **Registration ceremony** (`action_create_passkey` → `_start_registration` → `make_key`):
  `@check_identity`-guarded. `_start_registration` calls the vendored
  `generate_registration_options(rp_id=<base_url host>, rp_name='Odoo', user_id, user_name,
  resident_key=REQUIRED, user_verification=REQUIRED)` and stashes the challenge in
  `request.session['webauthn_challenge']`. The browser runs `navigator.credentials.create`;
  `make_key` → `_verify_registration_options` pops the challenge and calls
  `verify_registration_response(... require_user_verification=True)`, then writes the
  credential through `res.users.auth_passkey_key_ids` (invalidating the session-token cache)
  + a raw `public_key` UPDATE, and refreshes the session token so the user stays logged in.
  (code-read)
- **Login assertion verification** (`res.users._login` + `_check_credentials(type='webauthn')`):
  the login form carries hidden `type=webauthn`/`webauthn_response`. `_login` resolves the
  user by raw SQL on the credential id (`AccessDenied('Unknown passkey')` if none), then
  `_check_credentials` sudo-finds the passkey and calls `_verify_auth` →
  `verify_authentication_response`. An `InvalidAuthenticationResponse` is re-raised as
  **`AccessDenied` — login is denied until the assertion verifies**. On success it advances
  `sign_count` (clone detection) and returns `{uid, auth_method:'passkey', mfa:'skip'}` — so
  a passkey login **bypasses the TOTP MFA challenge** (the passkey is the strong factor).
  (code-read)
- **Vendored WebAuthn lib + one-shot challenge** (`_vendor/webauthn`,
  `_get_session_challenge`): the whole FIDO2 relying-party stack is in-tree (no external
  dep). `_get_session_challenge()` **pops** (consumes) the session challenge and raises
  `AccessDenied('Cannot find a challenge for this session')` if absent — every ceremony binds
  to exactly one freshly-issued challenge; `rp_id`/origin are pinned to `get_base_url()`.
  (code-read)
- **Frontend ceremony** (static, gap #3): `passkey_login.js` Interaction →
  `/auth/passkey/start-auth` rpc → `navigator.credentials.get` → submit `oe_login_form`;
  `auth_passkey_key_create_form_view.js` `FormController` intercepts `make_key` →
  `navigator.credentials.create`; `auth_passkey_identity_check_form_view.js` runs the
  assertion for `webauthn` re-auth. The ceremony is browser-side; the server only issues
  challenges and verifies responses. (static)

## 5. IT architecture

- **Application:** WebAuthn/FIDO2 passwordless authentication layered on the `web` login flow.
- **Software services:** `/auth/passkey/start-auth` (public jsonrpc — one-shot challenge).
- **Data objects:** `auth.passkey.key`, `auth.passkey.key.create`.
- **Information flows:** enrol → `_start_registration` → `navigator.credentials.create` →
  `make_key`/`_verify_registration_options` → `auth.passkey.key` (+ session-token refresh);
  login → `start-auth` → `navigator.credentials.get` → `_login` → `_check_credentials` →
  `_verify_auth` → `{auth_method:passkey, mfa:skip}` | `AccessDenied`; re-auth →
  `res.users.identitycheck(webauthn)` → `_check_identity`; replay-defense → `sign_count`
  advance per assertion.

## 6. Business architecture

- **Capabilities (inferred):** passwordless auth; passkey registration/provisioning; login
  assertion verification; passkey re-authentication; credential lifecycle (rename/delete/
  list); authenticator clone/replay detection.
- **Value streams (inferred):** Enrol-to-Passwordless (identity check → registration
  challenge → create credential → verify attestation → stored passkey); Assert-to-Session
  (click login → challenge → sign → server verifies → finalized session, MFA skipped).
- **Information concepts (auto):** `auth.passkey.key` (FIDO2 credential), the registration
  wizard, `res.users.auth_passkey_key_ids`, the one-shot `webauthn_challenge`.
- **Organization/Products (auto):** none (no own groups, no `product.*`).
- **Policies (inferred):** own-record-only access + `group_system`-only credential material;
  `user_verification`/`resident_key` REQUIRED (true passwordless); one-shot popped challenge;
  monotonic `sign_count`; `@check_identity` step-up on create/delete/re-auth.
- **Metrics (inferred):** users with ≥1 passkey (adoption); passkeys-per-user + `sign_count`
  progression; audit log of create/delete/denied-delete events.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** Identity & access hardening (Porter support activity; Stabell &
  Fjeldstad "support"). It creates no document chain and holds no customer/order/product/
  ledger data — its only job is to add a passwordless authentication factor to the login
  that **every** module sits behind (`auto_install=true`, depends only on `base_setup`/`web`).
  Hence not chain/shop/network.
- **APQC: 8.0 Manage Information Technology.** This is the "develop and manage IT security,
  privacy and data protection / identity & access management" capability — a concrete running
  access-control mechanism (in-tree FIDO2/WebAuthn relying-party crypto, a public challenge
  endpoint, an assertion-verifying login hook, credential lifecycle). **11.0 "Manage
  Enterprise Risk, Compliance, …"** was considered (passwordless/phishing-resistant auth
  mitigates account-takeover risk and supports compliance), but rejected: 11.0 is the
  governance layer (risk registers, control frameworks, audits), whereas `auth_passkey` is the
  technical *implementation* IT builds and operates — squarely 8.0. Mirrors the sibling
  `auth_totp` record (passkeys are the WebAuthn factor `auth_totp` defers to) and the `web` record.

## 8. Fit-to-Standard

- **Standard:** WebAuthn/FIDO2 passwordless login (resident/discoverable credentials,
  user-verification required) wired into the web login; self-service registration via an
  identity-checked attestation ceremony with `verify_registration_response`; assertion
  verification (`verify_authentication_response`) that denies until verified and returns
  `mfa:'skip'`; passkey step-up re-auth via `res.users.identitycheck`; replay/clone detection
  via `sign_count`; credential lifecycle (kanban list, rename, audited self-delete,
  system-only raw material); in-tree vendored WebAuthn lib + SimpleWebAuthn browser helper;
  one-shot host-pinned challenge protocol.
- **Typical fits:** log in with platform authenticators or roaming security keys out of the
  box; phishing-resistant passwordless as a stronger alternative to TOTP (passkey satisfies
  MFA); passkey re-authentication for sensitive actions; self-service multi-passkey management.
- **Common gaps:** no org-wide "require a passkey for group X" toggle; no lost-passkey
  recovery flow (password/TOTP/admin reset remain the path); no attestation-policy /
  authenticator allow-lists; no built-in rate-limiting on `/auth/passkey/start-auth` (unlike
  `auth_totp`'s ledger); `rp_id`/origin pinned to `base_url` (multi-domain/proxy needs correct
  `web.base.url`).
- **Drive hints:** `env['res.users'].browse(2).auth_passkey_key_ids.mapped('name')`;
  `env['auth.passkey.key'].sudo().search_read([], ['name','credential_identifier','sign_count'], limit=5)`;
  `curl -s -X POST .../auth/passkey/start-auth -d '{"jsonrpc":"2.0","method":"call","params":{}}'`
  (fetch a live challenge); `grep -n 'mfa' models/res_users.py` (confirm `mfa:'skip'`).

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/auth_passkey_key.py`, `models/res_users.py`, `models/res_users_identitycheck.py`,
`controllers/main.py`, and `static/src/interactions/passkey_login.js` +
`static/src/views/*.js`. Odoo 19.0.*
