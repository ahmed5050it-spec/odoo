# auth_totp — Architecture Brief

> Module: `auth_totp` · Category: Extra Tools · Depends: `web` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/auth_totp.facts.json` · Frontend: `doc/revres/frontend/auth_totp.frontend.json`

## 1. Summary

`auth_totp` is **IT security infrastructure** — it adds time-based one-time-password
(TOTP, RFC 6238) two-factor authentication to the Odoo login. After a password is
accepted, an enrolled user is held at a `pre_uid` state and challenged for a 6-digit
authenticator-app code before the session is finalized; an optional "remember this
browser" trusted-device cookie can skip the prompt for a configurable period. It owns
**no business object of its own**: 3 tiny models (a transient enrolment wizard, a
hashed trusted-device token reusing `res.users.apikeys`, and a rate-limit ledger) plus
4 fields grafted onto `res.users`, **1 public route**, ~824 Python LOC. It is
`auto_install: true` and depends only on `web`, so it sits beneath every other module.

## 2. Structure (evidence)

- **Models:** `auth.totp.rate.limit.log` (throttle ledger), `auth_totp.device`
  (`_inherit res.users.apikeys`, `_auto=False` — the trusted-device token),
  `auth_totp.wizard` (transient enrolment), plus an extension of `res.users` adding
  `totp_secret` (`groups=NO_ACCESS`), `totp_last_counter`, `totp_enabled`,
  `totp_trusted_device_ids`.
- **Routes (1):** `/web/login/totp` — public HTTP, GET renders the code form / checks
  the trusted-device cookie, POST verifies the code.
- **Security:** 3 access rules, **4 record rules**, 0 groups. Users see only their own
  devices/wizard (`[('user_id','=',user.id)]`); public users are blocked
  (`[(0,'=',1)]`); `base.group_system` may view devices to revoke; disable action
  bound to `base.group_erp_manager`.
- **Views:** 2 forms only (the 2FA section on the user form + the wizard dialog). No
  list/kanban — the entire UX is server-rendered forms + a QWeb login template.

## 3. Frontend (gap #3) & Integrations (gap #7)

Near-zero client footprint: **0 JS files, 0 OWL components, 0 registry adds, 0
services, 0 patches**. The only static asset is `static/src/scss/res_users_view_form.scss`
(one rule, `.o_auth_2fa_btn`), plus the QWeb login template `auth_totp.auth_totp_form`
and JS browser tests. Bundles touched: `web.assets_backend`=1, `web.assets_tests`=1.
The 2FA enable/disable UI is form views + a wizard dialog, **not** a custom OWL
component. Integrations (gap #7): **no outbound HTTP, no SDK imports, 0 external
endpoints**; `uses_api_keys: true` reflects that the trusted-device token reuses the
internal `res.users.apikeys` hashed-secret machinery, not any external service.

## 4. Behavior (beyond metadata)

- **Secret enrolment** (`action_totp_enable_wizard` → `_totp_try_setting`): mints a
  160-bit `os.urandom` secret, builds an `otpauth://totp/...?algorithm=SHA1&digits=6&period=30`
  QR via the `qrcode` lib, and on a verified code writes `totp_secret` through a raw
  `_inverse_token` UPDATE (bypassing ORM cache), then refreshes the session token so
  the user is not logged out. (code-read)
- **Login 2FA challenge** (`_check_credentials(type='totp')`, `_mfa_url='/web/login/totp'`):
  `controllers/home.web_totp` b32-decodes the secret and calls `TOTP(key).match(token)`;
  a miss raises `AccessDenied("…double-check the 6-digit code")`, a replay
  (`match <= totp_last_counter`) raises `AccessDenied("…use the latest 6-digit code")`,
  and only success calls `request.session.finalize(env)`. Enabling TOTP flips
  `_rpc_api_keys_only()` True (password RPC disabled). (code-read)
- **Trusted-device cookie** (`auth_totp.device._generate('browser', …)`): stores only
  `KEY_CRYPT_CONTEXT.hash(token)` (pbkdf2_sha512) + an 8-hex index; the plaintext is the
  httponly `SameSite=Lax` `td_id` cookie (default 90 days). Re-verified by
  `_check_apikey_credentials` via a timing-safe `KEY_CRYPT_CONTEXT.verify` (the `consteq`
  equivalent). Revoked on disable, `change_password`, and `revoke_all_devices`. (code-read)
- **HOTP/TOTP core** (`models/totp.py`): pure stdlib (no `pyotp`). `hotp` does
  `hmac.new(secret, struct.pack('>Q', counter), sha1)`, applies RFC 4226 dynamic
  truncation, mods `10**6`. `match` scans a ±30s counter window and returns the counter
  (stored as `totp_last_counter` to block replay). (code-read)
- **Rate limiting** (`_totp_rate_limit`): caps `code_check` at 5/hr and `send_email`
  at 5/hr per user/IP via `auth.totp.rate.limit.log`, purged on success. (code-read)

## 5. IT architecture

- **Application:** TOTP two-factor authentication layered on the `web` login flow.
- **Software services:** `/web/login/totp` (public — challenge form + trusted-device check).
- **Data objects:** `auth.totp.rate.limit.log`, `auth_totp.device`, `auth_totp.wizard`.
- **Information flows:** enrol → `_totp_try_setting` → `res.users.totp_secret`; challenge
  → `_mfa_url` → `web_totp` → `_check_credentials` → `session.finalize`; trust →
  `device._generate('browser')` → `td_id` cookie; throttle → `rate.limit.log`; side-effect
  `totp_enabled` → `_rpc_api_keys_only()`.

## 6. Business architecture

- **Capabilities (inferred):** TOTP second factor; secret enrolment & QR provisioning;
  replay-protected login challenge; trusted-device management; auth rate-limiting;
  administrative 2FA revocation.
- **Value streams (inferred):** Enrol-to-Protected (enable → scan → verify → hardened);
  Login-to-Session (password → TOTP challenge → verify → finalized session).
- **Information concepts (auto):** rate-limit log, trusted device, enrolment wizard,
  `res.users.totp_secret`, `td_id` cookie.
- **Organization/Products (auto):** none (no own groups, no `product.*`).
- **Policies (inferred):** own-record-only access; 5 checks/hr + 5 mails/hr; one-time-use
  per 30s step; disable restricted to self / `group_erp_manager` / system.
- **Metrics (inferred):** rate-limit rows per user/IP; audit log (enable/disable/SUCCESS|FAIL|REUSE);
  count of `totp_enabled` users.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** Identity & access hardening (Porter support activity;
  Stabell & Fjeldstad "support"). It creates no document chain and holds no
  customer/order/product/ledger data — its only job is to add a second authentication
  factor to the login that **every** module sits behind (`auto_install=true`, depends
  only on `web`). Hence not chain/shop/network.
- **APQC: 8.0 Manage Information Technology.** This is the "manage IT security / identity
  & access management" capability — a concrete running access-control mechanism
  (TOTP/HOTP crypto, MFA controller, trusted-device cookies, brute-force throttling).
  **11.0 "Manage Enterprise Risk, Compliance, …"** was considered (2FA mitigates
  account-takeover risk and supports compliance), but rejected: 11.0 is the governance
  layer (risk registers, control frameworks, audits), whereas `auth_totp` is the
  technical *implementation* IT builds and operates — squarely 8.0. Mirrors the sibling
  `auth_*` modules and the `web` record.

## 8. Fit-to-Standard

- **Standard:** RFC 6238 authenticator-app 2FA (in-tree SHA1/6/30, Google-Authenticator
  otpauth QR); login MFA challenge via `_mfa_type`/`_mfa_url` + `/web/login/totp`; replay
  protection + ±30s skew; trusted-device httponly cookie (pbkdf2-hashed token, 90-day
  default via `auth_totp.trusted_device_age`); per-user/IP rate limiting; self-service
  enable/disable + admin revoke; auto API-key-only RPC; full audit logging.
- **Typical fits:** mandate 2FA for admins out of the box; self-enrol with any standard
  authenticator app; reduce prompt fatigue with trusted-device opt-out; tune device
  lifetime via the system parameter.
- **Common gaps:** no org-wide "require 2FA for group X" toggle out of the box; email-OTP
  lives in `auth_totp_mail`; fixed algorithm (no digits/period UI); no SMS/WebAuthn here
  (`auth_passkey`); no backup-codes recovery (admin disable is the reset path).
- **Drive hints:** `env['res.users'].browse(2)._mfa_type()`;
  `from odoo.addons.auth_totp.models.totp import TOTP; TOTP(base64.b32decode(secret)).match(code)`;
  `env['auth.totp.rate.limit.log'].search_read([], ['user_id','ip','limit_type'], limit=5)`;
  `curl -i http://localhost:8069/web/login/totp` (303 → /web/login without a pre_uid session).

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/res_users.py`, `models/totp.py`, `models/auth_totp.py`, `controllers/home.py`,
`wizard/auth_totp_wizard.py`. Odoo 19.0.*
