# auth_oauth — Architecture Brief

> Module: `auth_oauth` · Category: Hidden/Tools · Depends: `base` · `web` · `base_setup` · `auth_signup` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/auth_oauth.facts.json` · Frontend: `doc/revres/frontend/auth_oauth.frontend.json`

## 1. Summary

`auth_oauth` is **IT identity & access infrastructure** — it adds OAuth2 federated
single-sign-on ("Log in with Google / Microsoft Azure AD / Facebook / Odoo.com / Okta")
to the Odoo login. Enabled providers render as buttons on the standard login page; a
click redirects the browser to the external identity provider (IdP), which on consent
returns an access token to `/auth_oauth/signin`. Odoo then **validates that token
server-to-server against the IdP**, maps the external subject to a local `res.users`
(or provisions a new one via `auth_signup`), and finalizes the session. It owns **no
business object of its own**: 1 real model (`auth.oauth.provider`, pure per-IdP config)
plus 4 fields grafted onto `res.users`, **3 routes**, ~469 Python LOC. It is *not*
`auto_install`, but once installed it sits beneath the web login every module relies on.

## 2. Structure (evidence)

- **Models:** `auth.oauth.provider` (10 fields: `client_id`, `auth_endpoint`,
  `scope`, `validation_endpoint`, `data_endpoint`, `enabled`, `css_class`, `body`,
  `sequence`) — the only real model; plus extensions of `res.users`
  (`oauth_provider_id`, `oauth_uid`, `oauth_access_token` `groups=NO_ACCESS`,
  `has_oauth_access_token`), `res.config.settings` (Google quick-config), and
  `ir.config_parameter` (seeds `provider_openerp.client_id` from `database.uuid`).
- **Routes (3):** `/auth_oauth/signin` (public — OAuth callback), `/auth_oauth/oea`
  (public — Odoo.com Account shortcut, `no_user_creation`), and a `/web/login` override
  that injects provider buttons + `oauth_error` messaging.
- **Security:** 1 access rule (`auth.oauth.provider` read/write to `base.group_system`
  only), 0 record rules, 0 groups. Identity-uniqueness enforced by a SQL constraint
  `unique(oauth_provider_id, oauth_uid)`.
- **Views:** 1 form + 1 list (provider admin) + the `res.config.settings` page. The
  login-page UI is a QWeb template inheriting `web.login_oauth`.

## 3. Frontend (gap #3) & Integrations (gap #7)

Near-zero client footprint: **0 JS files, 0 OWL components, 0 registry adds, 0
services, 0 patches**. The only static asset is `static/src/scss/auth_oauth.scss`
(provider-button icon styling — `.o_auth_oauth_provider_icon`,
`.o_google_provider` / `.o_facebook_provider` / `.o_odoo_provider`) in the
`web.assets_frontend` bundle (=1), plus the server-rendered QWeb template `providers`
(inherits `web.login_oauth`) that `t-foreach`-es enabled providers into login buttons.
The whole "Log in with Google/Azure/etc." UI is **server-rendered**, not a custom OWL
widget. Integrations (gap #7): **2 outbound HTTP call sites** (the `requests` SDK) in
`models/res_users.py._auth_oauth_rpc` — `GET validation_endpoint` and `GET
data_endpoint` against external IdPs (Google, Facebook Graph, Odoo.com, or any custom
OIDC provider). `uses_api_keys: true` reflects the per-provider `client_id` credential.
`endpoints: []` because targets are admin-configured in `auth.oauth.provider` records,
not hardcoded.

## 4. Behavior (beyond metadata)

- **Provider config** (`auth.oauth.provider`): stores one IdP's OAuth2 wiring
  (`client_id`, `auth_endpoint`, `scope` default `openid profile email`,
  `validation_endpoint`, optional `data_endpoint`, button `body`/`css_class`). Seed data
  ships Odoo.com, Google and Facebook providers, **none enabled by default**; admin must
  set `enabled` + `client_id`. Only `base.group_system` may edit. (code-read)
- **Login-page injection + state CSRF** (`OAuthLogin.web_login` / `list_providers`):
  builds `auth_link = auth_endpoint?response_type=token&client_id=…&redirect_uri={root}/auth_oauth/signin&scope=…&state={json}`
  (implicit flow, token in URL fragment). `get_state` packs `d`=db, `p`=provider, `r`=redirect,
  `t`=signup token — the round-trip/CSRF binding the callback trusts. (code-read)
- **Callback + token validation** (`/auth_oauth/signin` → `auth_oauth` →
  `_auth_oauth_validate`): `@fragment_to_query_string` exposes the token; a
  `requests.get` to `validation_endpoint` (Bearer header or `access_token` param, 10s
  timeout) + optional `data_endpoint` validates it at the IdP, then unifies the subject
  by popping `sub` / `id` / `user_id`; missing subject → `AccessDenied`. The audience
  (Confused-Deputy) check is intentionally **not** enforced (TODO comment). (code-read)
- **Match / signup-on-first-login** (`_auth_oauth_signin` + `_generate_signup_values`):
  searches `(oauth_uid, provider)`; on hit writes the new token and returns the login; on
  miss provisions a new user via `auth_signup.signup` (login/email/name from the validated
  profile), unless `no_user_creation`. The controller `cr.commit()`s so the new user is
  visible to the separate `session.authenticate` transaction. (code-read)
- **Token-as-credential & session binding** (`_check_credentials(type='oauth_token')` +
  `_get_session_token_fields`): super (password/apikey) is tried first; the OAuth branch
  matches the stored `oauth_access_token` and returns `auth_method='oauth'`. The token is
  `NO_ACCESS`/`prefetch=False`; adding it to the session-token fields means
  `remove_oauth_access_token` (or rotation) **invalidates the federated session**. (code-read)

## 5. IT architecture

- **Application:** OAuth2 single-sign-on layered on the `web` / `auth_signup` login flow.
- **Software services:** `/auth_oauth/signin` (callback), `/auth_oauth/oea` (Odoo.com
  shortcut), `/web/login` override (provider buttons).
- **Data objects:** `auth.oauth.provider`; `res.users` (`oauth_provider_id`, `oauth_uid`,
  `oauth_access_token`); `res.config.settings`; `ir.config_parameter`.
- **Information flows:** login → `list_providers` → `auth_link` → IdP; callback → IdP →
  `_auth_oauth_validate` (`requests.get(validation_endpoint)`); match/provision →
  `_auth_oauth_signin` → existing login | `auth_signup.signup`; session →
  `authenticate(type=oauth_token)`; side-effect: token in `_get_session_token_fields`.

## 6. Business architecture

- **Capabilities (inferred):** federated SSO / external identity login; IdP configuration
  & onboarding; OAuth2 token validation; external-to-local identity mapping; JIT account
  provisioning; OAuth token lifecycle / federated-session revocation.
- **Value streams (inferred):** Configure-Provider (admin enables IdP → button appears);
  SSO-Login-to-Session (click → IdP consent → token callback → validate → match/provision
  → finalized session).
- **Information concepts (auto):** `auth.oauth.provider`, `res.users.oauth_uid`,
  `oauth_provider_id`, `oauth_access_token` (NO_ACCESS), OAuth `state` token.
- **Organization/Products (auto):** none (no own groups, no `product.*`).
- **Policies (inferred):** provider config to `base.group_system` only;
  `unique(provider, oauth_uid)`; token must be IdP-validated before any session; signup
  gated by `auth_signup` mode + state token; token-as-session (clear/rotate → logout).
- **Metrics (inferred):** count of enabled providers; count of users with
  `oauth_provider_id`; `oauth_error` redirects on the login page.
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** IT identity & access infrastructure (Porter support activity;
  Stabell & Fjeldstad "support"). It owns no business object — its one real model is pure
  per-IdP configuration, everything else extends `res.users`/config. It creates no
  document chain and holds no customer/order/product/ledger data; its sole job is to let
  users authenticate with an **external** identity provider to the login every module
  sits behind. Hence not chain/shop/network.
- **APQC: 8.0 Manage Information Technology.** This is the "identity & access management /
  external system integration" capability — a concrete running access-control runtime
  (OAuth2 callback controller, server-to-server token validation, identity mapping, JIT
  provisioning, federated-session binding). **11.0 "Manage Enterprise Risk, Compliance,
  …"** was considered (SSO touches account-security governance) but rejected: 11.0 is the
  governance layer (control frameworks, audits, policy), whereas `auth_oauth` is the
  technical *implementation* IT builds and operates — squarely 8.0. Mirrors the sibling
  `auth_totp` and `web` records.

## 8. Fit-to-Standard

- **Standard:** OAuth2 implicit-flow SSO wired into the web/`auth_signup` login page;
  configurable providers (auth/validation/data endpoints, `client_id`, `scope`, button
  label) with Odoo.com/Google/Facebook seeds (none enabled by default); server-to-server
  token validation (Bearer header or query param); subject-key unification
  (`sub`/`id`/`user_id`) + `unique(provider, oauth_uid)` mapping; JIT provisioning via
  `auth_signup`; `/auth_oauth/oea` Odoo.com shortcut; token bound into session-token
  fields (removal/rotation revokes); one-click Google enablement from Settings.
- **Typical fits:** corporate Google Workspace login out of the box; add Azure AD (Entra),
  Okta or any OIDC IdP via an `auth.oauth.provider` record; self-service portal onboarding
  via "Sign up with Google"; centralize revocation at the external IdP.
- **Common gaps:** implicit `token` flow only (no out-of-box Authorization-Code+PKCE);
  audience/Confused-Deputy check intentionally **not** enforced (TODO); no IdP-claim →
  Odoo-group mapping and no SCIM de-provisioning; no SAML (separate add-on) / no
  refresh-token handling; provider setup (redirect_uri registration, `client_id`) is
  manual beyond Google.
- **Drive hints:** `env['auth.oauth.provider'].search_read([], ['name','enabled','client_id','validation_endpoint'])`;
  `env.ref('auth_oauth.provider_google').write({'enabled': True, 'client_id': '…'})`;
  `env['res.users'].search_read([('oauth_provider_id','!=',False)], ['login','oauth_uid'])`;
  `curl -i http://localhost:8069/web/login` (provider buttons render);
  `curl -i 'http://localhost:8069/auth_oauth/signin?state=%7B%7D'` (→ `/web/login?oauth_error=…`).

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/res_users.py`, `models/auth_oauth.py`, `models/res_config_settings.py`,
`models/ir_config_parameter.py`, `controllers/main.py`, `data/auth_oauth_data.xml`,
`views/auth_oauth_templates.xml`. Odoo 19.0.*
