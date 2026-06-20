# auth_signup — Architecture Brief

> Module: `auth_signup` · Category: Hidden/Tools · Depends: `base_setup` · `mail` · `web` · `auto_install: true`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/auth_signup.facts.json` · Frontend: `doc/revres/frontend/auth_signup.frontend.json`

## 1. Summary

`auth_signup` is **IT identity & access infrastructure** — it adds self-service
**signup**, admin **invitation**, and **password-reset** to the Odoo login, all driven
by an emailed **signed token**. It owns **no model of its own** (0 new models): it grafts
`signup_type` onto `res.partner`, a computed `state` (Invited/Confirmed) plus the whole
signup/reset lifecycle onto `res.users`, three settings onto `res.config.settings`, and
config injection onto `ir.http`. Its job is to turn a token into an activated `res.users`
(a clone of the portal template user) and to reset passwords — beneath the `web` login
that every other module relies on. **4 routes** (2 public), ~960 Python LOC, `auto_install`.

## 2. Structure (evidence)

- **Models (all extensions):** `res.partner` (+`signup_type` Char `group_erp_manager`,
  token methods), `res.users` (+`state` computed Selection, `signup`/`reset` lifecycle,
  16 methods), `res.config.settings` (+`auth_signup_reset_password`,
  `auth_signup_uninvited` b2b/b2c, `auth_signup_template_user_id`), `ir.http`.
- **Routes (4):** `/web/signup` (public), `/web/reset_password` (public), `/web/login`
  override (injects `signup_enabled`/`reset_password_enabled` + post-signup redirect), and
  a `/base_setup/data` json override (`resend_invitation`).
- **Security:** **0** access rules, **0** record rules, **0** groups — pure mechanism.
- **Views:** 2 form + 1 list (`res.users`/settings); signup/reset/login forms are QWeb
  templates (`views/auth_signup_login_templates.xml`). Mail templates: `set_password_email`,
  `portal_set_password_email`, `reset_password_email`, `mail_template_user_signup_account_created`,
  `mail_template_data_unregistered_users`; one `ir.cron` reminder.

## 3. Frontend (gap #3) & Integrations (gap #7)

Near-zero client footprint: **1 JS file, 0 OWL components, 0 services, 0 patches, 1
registry add**. The single asset is one public **Interaction**
(`static/src/interactions/signup.js`) registered as `public.interactions:auth_signup.signup`,
bound to `.oe_signup_form, .oe_reset_password_form`; on submit it merely disables the
submit button and adds a loading spinner (`addLoadingEffect`) to prevent double-submit.
Loaded via `web.assets_frontend` (=1). The signup/reset/login forms themselves are
**server-rendered** QWeb — there is no SPA/OWL widget. Integrations (gap #7): **none** —
`http_call_sites: 0`, no SDK imports, `uses_api_keys: false`, `endpoints: []`. All
mail goes through the standard `mail` outbound stack, not a third-party API.

## 4. Behavior (beyond metadata)

- **Signed, self-invalidating token** (`res.partner._generate_signup_token` /
  `_get_partner_from_token`): no DB token column — the token is `tools.hash_sign('signup',
  [partner.id, user_ids, login_date, signup_type])`. Verification re-checks all four, so the
  token **invalidates the moment the user logs in** (login_date in payload). Expiry is
  per-type: `reset` 4h, `signup` 144h (ICP-tunable). `signup_prepare`/`signup_cancel` just
  set/clear `signup_type` (cancel also fires on user archive/delete). (code-read)
- **Token-driven creation/activation** (`res.users.signup` → `_create_user_from_template`):
  three modes by token — (a) token + no user ⇒ create user for the partner; (b) token +
  existing user ⇒ password set/reset (`_notify_inviter` bus-pings on first internal
  activation); (c) no token ⇒ external user. Creation always **copies
  `base.template_portal_user_id`** (inherits its groups/company) in a savepoint; the token
  is consumed (`signup_type=False`) first; a copy failure → `SignupError`. (code-read)
- **b2b/b2c gate** (`_get_signup_invitation_scope`): uninvited self-registration only when
  ICP `auth_signup.invitation_scope == 'b2c'`, else `SignupError('Signup is not allowed for
  uninvited users')`. `/web/signup` 404s unless a token or `signup_enabled`. An invitation
  token **bypasses** the gate; open signup needs an admin to flip the scope. (code-read)
- **Invitation/reset email + auto-invite** (`_action_reset_password`, `create()` override):
  picks per-audience templates (`set_password_email` internal / `portal_set_password_email`
  portal / `reset_password_email`). Critically, `res.users.create()` is overridden to
  **auto-invite** — any new user with an email is immediately emailed a signup-activation
  link (unless `no_reset_password`); delivery failure rolls back via `signup_cancel`. A
  daily `ir.cron` reminds inviters about users still in state `new`. (code-read)
- **Public token→session flow** (`/web/signup`, `/web/reset_password`): shared
  `get_auth_signup_qcontext` reads the token (params or session) and pre-fills name/login/
  email via `_signup_retrieve_info`. POST `/web/signup` → `signup()` → `cr.commit()` →
  `session.authenticate` (MFA drops to the public user); a confirmation mail is sent.
  `/web/reset_password` sets a password (token) or emails a link (login). Responses carry
  SAMEORIGIN + frame-ancestors CSP and captcha guards. (code-read)
- **Frontend (static):** one submit-guard Interaction only; forms are server-rendered QWeb,
  no OWL/services/patches. (static)

## 5. IT architecture

- **Application:** token-based signup / invitation / password-reset on the web login + mail.
- **Software services:** `/web/signup`, `/web/reset_password`, `/web/login` override,
  `/base_setup/data` override.
- **Data objects:** `res.partner` (signup_type + token machinery), `res.users` (state +
  lifecycle), `res.config.settings` (scope/reset/template user), `ir.http`.
- **Information flows:** invite → `_action_reset_password` → mail template; token →
  `hash_sign([id, user_ids, login_date, type])`; signup → `signup()` →
  `_create_user_from_template` (copy template_portal_user) → `cr.commit` → `authenticate`;
  gate → `_get_signup_invitation_scope` (b2b/b2c); cron reminder to inviters.

## 6. Business architecture

- **Capabilities (inferred):** self-service signup; admin invitation/provisioning;
  password reset & set-password; signup-token lifecycle; invitation-scope governance;
  unregistered-user reminder.
- **Value streams (inferred):** Invite-to-Active (create → activation email → set password →
  session, `new`→`active`); Forgot-Password-to-Reset; Open-Signup-to-Account (b2c).
- **Information concepts (auto):** `signup_type`, the signed signup token, `res.users.state`,
  invitation scope (b2b/b2c ICP), the template portal user.
- **Organization/Products (auto):** none (no own groups, no `product.*`).
- **Policies (inferred):** uninvited-signup needs b2c; tokens self-invalidate on login
  (4h/144h); new users clone the template portal user; auto-invite on user create;
  routes 404 without token/flag + framing/CSP/captcha.
- **Metrics (inferred):** users in state `new`; token TTL + scope settings; reminder volume.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** IT identity & access infrastructure (Porter support; Stabell &
  Fjeldstad "support"). It owns **no business object** — 0 new models, 0 groups/ACLs;
  everything extends `res.partner`/`res.users`/config. Its sole job is account provisioning
  and credential bootstrap beneath the web login. No document chain, no customer/order/
  product/ledger data — hence not chain/shop/network.
- **APQC: 8.0 Manage Information Technology.** The identity-and-access-management capability
  — account provisioning, invitation, and password-reset as a running runtime (public
  `/web/signup` + `/web/reset_password`, HMAC-signed self-invalidating tokens, b2b/b2c
  gating, template-user cloning, invitation/reset mail). **11.0 "Manage Enterprise Risk,
  Compliance…"** was considered (account lifecycle touches security governance) but rejected:
  11.0 is the governance layer, whereas `auth_signup` is the technical mechanism IT builds —
  squarely 8.0. Mirrors siblings `auth_oauth`, `auth_totp`, `web` (all 8.0 / support).

## 8. Fit-to-Standard

- **Standard:** public signup/reset wired into the web login; HMAC-signed tokens
  (self-invalidate on login, reset 4h / signup 144h, ICP-tunable); three `signup()` modes
  (new invited / set-reset existing / open external); b2b/b2c invitation-scope gate;
  auto-invitation on backend user create (per-audience templates); new accounts cloned from
  the portal template user; `state` Invited/Confirmed + daily reminder cron; reset by
  login/email; confirmation mail; captcha + framing/CSP hardening.
- **Typical fits:** invite employees/portal customers to self-set their password; enable
  open b2c portal signup; standard forgot-password reset; serve as the JIT-provisioning
  backend for `auth_oauth`/federation add-ons.
- **Common gaps:** no domain-allowlist/email-verification beyond b2b/b2c; new users are a
  fixed clone of one template (no per-channel role mapping); token TTL + scope are global
  ICPs, not per-campaign; no rate-limiting beyond captcha and a hard-coded 5-day reminder;
  no multi-step onboarding/approval (single-form, immediate activation subject to MFA).
- **Drive hints:**
  `env['ir.config_parameter'].sudo().set_param('auth_signup.invitation_scope', 'b2c')` (open signup);
  `env['ir.config_parameter'].sudo().get_param('auth_signup.signup.validity.hours')` (token TTL);
  `p.signup_prepare(); p._generate_signup_token()` (mint a token);
  `env['res.users'].search_count([('state','=','new')])` (never-activated invites);
  `curl -i http://localhost:8069/web/signup` (404 without token/b2c);
  `curl -i http://localhost:8069/web/reset_password` (reset form).

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/res_partner.py`, `models/res_users.py`, `controllers/main.py`,
`data/mail_template_data.xml`, `static/src/interactions/signup.js`. Odoo 19.0.*
