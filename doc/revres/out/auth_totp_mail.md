# auth_totp_mail — Architecture Brief

> Module: `auth_totp_mail` · Category: Extra Tools · Depends: `auth_totp`, `mail` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/auth_totp_mail.facts.json` · Frontend: `doc/revres/frontend/auth_totp_mail.frontend.json`

## 1. Summary

`auth_totp_mail` adds an **email-delivered one-time-code second factor** to the Odoo
login, plus **policy-based 2FA enforcement** and **2FA invitation emails**. When an admin
forces 2FA on a user who has **no authenticator app**, the user is held at `pre_uid` after
password auth and emailed a 6-digit code, which they enter on `auth_totp`'s existing TOTP
form. It owns **no business object** — 0 own models, only behaviour grafted onto
`res.users`, `auth_totp.device`, and `res.config.settings` — ~518 py LOC, `auto_install:
true`, sitting beneath every other module. It is the **email-OTP variant** that
`auth_totp`'s base record explicitly defers to it.

## 2. Structure (evidence)

- **Models (0 own + 3 inherit):** `res.users` (14 methods — the `'totp_mail'` MFA branch,
  code generator/sender, invite, security alerts); `auth_totp.device` (revocation alert on
  `unlink`); `res.config.settings` (enforce toggle → `ir.config_parameter 'auth_totp.policy'`).
- **Routes (1):** `/web/login/totp` — **not a new route**; `controllers/home.Home` extends
  `auth_totp`'s `web_totp` (public HTTP, GET/POST), firing **after** `super()` to email the
  OTP on render.
- **Security:** 0 access rules / record rules / groups of its own. The invite server action
  is restricted to `base.group_erp_manager`, the activate-2FA link to `base.group_user`.
  OTP send/check runs `sudo()` during the `pre_uid` phase. `uses_api_keys: true` is
  inherited (`totp_mail` also forces `_rpc_api_keys_only`).
- **Views:** 2 `res.users` form inherits (Invite button; stripped Enable-2FA form) + a
  `res.config.settings` view + a QWeb inherit of `auth_totp.auth_totp_form` (email-code
  text + "Re-send email" button). No new model → no list/search.

## 3. Frontend (gap #3) & Integrations (gap #7)

`frontend_gap3` **present: false** — **0 JS modules, 0 OWL components, 0 registry adds, 0
services, 0 patches**. The only client artifact is `static/tests/totp_flow.js` (a browser
test), so the only bundle touched is `web.assets_tests`=1. The entire UX is
**server-rendered**: QWeb login-form inherits, backend form inherits, and emailed
`mail.template`s. Integrations (gap #7): **no outbound HTTP, no SDK imports, 0 endpoints**;
`uses_api_keys: true` is inherited from `auth_totp` (the trusted-device token reuses the
internal `res.users.apikeys` machinery), not any external service.

## 4. Behavior (beyond metadata)

- **Email-OTP verification (code-read):** `_check_credentials(type='totp_mail')`
  rate-limits `code_check` (5/hr, inherited), then `TOTP(_get_totp_mail_key()).match(token,
  window=3600, timestep=3600)`. There is **no stored secret** — `_get_totp_mail_key` returns
  `hmac(env(su=True), 'auth_totp_mail-code', (id, login, login_date))`, a derived key that
  **self-rotates** on login/credential change. The 3600s window makes one code valid ~1h
  (vs the 30s authenticator window). Success purges both rate-limit counters and returns
  `{uid, auth_method:'totp_mail', mfa:'default'}`; a miss raises
  `AccessDenied("...double-check the 6-digit code")`.
- **Policy-driven enrolment (code-read):** `_mfa_type` extends `auth_totp` — when `super()`
  is `None` (no app-TOTP) it returns `'totp_mail'` if `ir.config_parameter 'auth_totp.policy'`
  is `'all_required'`, or `'employee_required'` **and** `_is_internal()`. `_mfa_url` →
  `'/web/login/totp'`; `_rpc_api_keys_only` is True for `totp_mail` too.
- **Send-by-email flow (code-read):** `controllers/home.web_totp` calls `super()`, then —
  only if 200, `_mfa_type()=='totp_mail'`, and still `pre_uid` — opens a `cr.savepoint()`
  and calls `_send_totp_mail_code()` (rate-limited `send_email`, 5/hr; `UserError` if no
  email). It sends `mail_template_totp_mail_code` (`force_send`, light layout) with
  GeoIP/IP/device/browser context; the template renders `_get_totp_mail_code()` =
  `hotp(key, counter)` with `counter=int(timestamp/3600)`, zero-padded to 6 digits, plus a
  human "~1 hour" expiration. The "Re-send email" button re-POSTs to re-send (still
  rate-limited).
- **Invite/onboarding (code-read):** `action_totp_invite` (erp_manager server action on
  the users list) emails `mail_template_totp_invite` to users without `totp_secret`, then
  toasts the recipients; `get_totp_invite_url` → a `group_user` action opening the stripped
  Enable-2FA form (`auth_totp_mail.res_users_view_form`).
- **Security alerts (code-read):** `write(totp_secret)` → "2FA Activated/Deactivated";
  `authenticate()` → new-device email **only** when `_mfa_type()` is set and the `td_id`
  cookie matches no trusted `auth_totp.device`; `auth_totp.device.unlink` → "Device Removed"
  (grouped per user). All via `_notify_security_setting_update`, with
  `suggest_2fa = (flag and not totp_enabled)`.

## 5. IT architecture

- **Application:** email-OTP second factor + 2FA invite/enforcement layered on `auth_totp`'s
  login flow.
- **Data objects:** inherits on `res.users`, `auth_totp.device`, `res.config.settings`.
- **Key relations:** `res.users → mail.template` (`totp_mail_code`, `totp_invite`);
  `res.config.settings → ir.config_parameter 'auth_totp.policy'`; `auth_totp.device →
  res.users`. The OTP key is **derived** (`hmac(id, login, login_date)`), no secret table.
- **Flows:** challenge `_mfa_type='totp_mail'` → `web_totp` GET → `_send_totp_mail_code`;
  verify POST → `_check_credentials` → `TOTP.match(window=3600)` → `session.finalize`;
  throttle `send_email`/`code_check` 5/hr; enforce via `auth_totp.policy`; invite via
  erp_manager action.

## 6. Business architecture

- **Capabilities (inferred):** email one-time-code factor; policy enforcement; 2FA invite
  email; security-event alerts; reuse of `auth_totp` rate-limiting.
- **Value streams (inferred):** Login-by-Email-OTP (password → `pre_uid` → code emailed →
  entered → `_check_credentials` → session); Enforce-then-Onboard (admin sets policy +
  invite → user enables app-2FA, graduating off email OTP).
- **Information concepts (auto):** `res.users` (behaviour, no new field); the derived
  `totp_mail` OTP (~1h, not persisted); the two `mail.template`s; `ir.config_parameter
  'auth_totp.policy'`.
- **Organization (auto):** `base.group_erp_manager` (invites/enforce), `base.group_user`
  (receives) — no own groups.
- **Policies (inferred):** enforcement scope (employees/all); 5 codes + 5 checks/hr
  (inherited); ~1h validity; key rotation on login change; invite only un-enrolled users.
- **Metrics (inferred):** `auth.totp.rate.limit.log` rows (send_email/code_check); `2FA
  check (mail): SUCCESS|FAIL` audit; policy coverage vs app-`totp_secret` adoption; invites
  sent.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** IT security infrastructure (Porter support activity; Stabell &
  Fjeldstad "support"). It owns no business object and exists solely to add a second
  authentication factor (+ enforcement + invites) to the login every module sits behind
  (`auto_install=true`). Hence not chain/shop/network.
- **APQC: 8.0 Manage Information Technology.** The "manage IT security / identity & access
  management" capability — a concrete running access-control mechanism (email OTP
  generation/verification, MFA challenge wiring, rate-limited delivery, enforcement policy).
  Mirrors its parent `auth_totp` (also 8.0). **11.0 "Manage Enterprise Risk, Compliance,
  …"** was considered (2FA mitigates account-takeover risk) but rejected: 11.0 is the
  governance layer (risk registers, control frameworks), whereas this is the technical
  *implementation* IT builds and operates. Numbering 8.0 = "Manage Information Technology"
  matches the name.

## 8. Fit-to-Standard

- **Standard:** email one-time-code as a fallback second factor; wired into `auth_totp`'s
  gate (`_mfa_type='totp_mail'`, `/web/login/totp`, `_check_credentials`); derived
  (non-stored) HMAC code keyed to id+login+login_date, ~1h validity; rate limiting on send
  and check (5/hr each) with new-device GeoIP/IP/browser context in the email; policy
  enforcement via Settings (`auth_totp.policy`); admin invite email + one-click Enable-2FA;
  security-event alert emails.
- **Typical fits:** forcing 2FA org-wide even for users without an authenticator app;
  bulk-inviting users onto app-2FA; notifying suspicious new-device logins and device
  revocations; tightening login security without SMS/hardware tokens.
- **Common gaps:** email OTP is weaker than app-TOTP (email compromise defeats it — a
  fallback/bridge, not the recommended factor); delivery depends on the mail subsystem;
  ~1h validity is a larger interception window than 30s; coarse two-level policy
  (employees/all); no self-service backup-codes/recovery beyond admin disable.
- **Drive:** `env['ir.config_parameter'].sudo().set_param('auth_totp.policy','all_required');
  env['res.users'].browse(2)._mfa_type()`;
  `env['res.users'].sudo().browse(2)._get_totp_mail_code()` (→ code, "~1 hour");
  `env.ref('auth_totp_mail.mail_template_totp_mail_code')`;
  `curl -i http://localhost:8069/web/login/totp` (redirects to `/web/login` without a
  `pre_uid` session).

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/res_users.py`, `models/auth_totp_device.py`, `models/res_config_settings.py`,
`controllers/home.py`, `data/mail_template_data.xml`, `data/ir_action_data.xml`,
`views/templates.xml`, `views/res_users_views.xml`, plus the `auth_totp` base
(`models/res_users.py`, `models/totp.py`, `controllers/home.py`). Odoo 19.0.*
